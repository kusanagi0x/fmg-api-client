"""``FMGClient`` — async JSON-RPC transport for FortiManager.

The single chokepoint for all FMG HTTP exchange. Domain managers receive
an :class:`FMGClient` (or a stub implementing :class:`FMGClientProtocol`)
and call its CRUD verbs (``get`` / ``add`` / ``set`` / ``update`` /
``delete`` / ``execute`` / ``multiplex``).

Transport-level retries with jittered exponential backoff are built in
for transient HTTP/network failures. FMG application-level errors are
mapped to typed exceptions (:class:`NotFoundError`, :class:`DuplicateError`,
:class:`AuthError`, :class:`FMGError`) at :meth:`_check_status`.
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

import httpx

from fmg_api_client.core.exceptions import (
    AuthError,
    DuplicateError,
    FMGError,
    NotFoundError,
)
from fmg_api_client.core.models import (
    FMGStatusCode,
    JsonRpcResponse,
    SystemStatus,
)

if TYPE_CHECKING:
    from fmg_api_client.core.session import SessionManager

logger = logging.getLogger(__name__)

# Default retry config
_MAX_RETRIES = 3
_BACKOFF_BASE = 1.0
_BACKOFF_MAX = 10.0
# +/-30% jitter — avoids thundering-herd when many workers retry in lock-step.
_BACKOFF_JITTER = 0.3
# HTTP status codes that indicate a transient server-side problem and are
# safe to retry. 408/429 are retriable per RFC; 5xx are retriable for the
# idempotent JSON-RPC verbs we use (add/set/update/get/delete/exec).
_RETRIABLE_HTTP = frozenset({408, 429, 500, 502, 503, 504})
# Transport-level exceptions we treat as retriable. Anything else either
# lands here transitively (TimeoutException covers ConnectTimeout etc.)
# or surfaces as a permanent failure.
_RETRIABLE_EXC: tuple[type[Exception], ...] = (
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.RemoteProtocolError,
    httpx.PoolTimeout,
    httpx.ReadError,
    httpx.WriteError,
)


@runtime_checkable
class FMGClientProtocol(Protocol):
    """Structural protocol the managers depend on.

    Any object with these async methods (and matching signatures) is
    accepted — the production client and any test stub both implement it.
    """

    async def get(self, url: str, **params: Any) -> Any: ...
    async def add(self, url: str, data: dict[str, Any]) -> Any: ...
    async def set(self, url: str, data: dict[str, Any]) -> Any: ...
    async def update(self, url: str, data: dict[str, Any]) -> Any: ...
    async def delete(self, url: str, **params: Any) -> Any: ...
    async def execute(self, url: str, data: dict[str, Any]) -> Any: ...
    async def multiplex(self, requests: list[dict[str, Any]]) -> list[Any]: ...


class FMGClient:
    """Async JSON-RPC client for FortiManager.

    Lifecycle: ``connect()`` (or ``async with``) opens the HTTP session,
    authenticates, and fetches ``/sys/status`` to populate
    :pyattr:`system_status`. ``disconnect()`` (or context exit) closes it.
    """

    def __init__(
        self,
        session_mgr: SessionManager,
        *,
        timeout: float = 120.0,
        connect_timeout: float = 10.0,
        max_retries: int = _MAX_RETRIES,
    ) -> None:
        # ``connect_timeout`` is kept small so an unreachable FMG (VM off,
        # network partition) fails the TCP handshake in seconds instead of
        # hanging the worker. ``timeout`` governs read/write for the
        # long-running FMG calls (task polling, installs).
        self._session_mgr = session_mgr
        self._timeout = timeout
        self._connect_timeout = connect_timeout
        self._max_retries = max_retries
        self._http: httpx.AsyncClient | None = None
        self._request_id = 0
        self._system_status: SystemStatus | None = None

    @property
    def system_status(self) -> SystemStatus | None:
        """Cached system status from ``connect()``."""
        return self._system_status

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> SystemStatus:
        """Open HTTP connection, authenticate, and fetch system status."""
        self._http = httpx.AsyncClient(
            verify=self._session_mgr.verify_ssl,
            timeout=httpx.Timeout(
                connect=self._connect_timeout,
                read=self._timeout,
                write=self._timeout,
                pool=self._connect_timeout,
            ),
            headers=self._session_mgr.auth_headers(),
        )
        await self._session_mgr.login(self._http)

        # Fetch system status to detect FMG version (used by adapter factory).
        data = await self.get("/sys/status")
        self._system_status = SystemStatus.model_validate(data)
        logger.info(
            "Connected to FMG %s (version %s, SN %s)",
            self._session_mgr.host,
            self._system_status.version,
            self._system_status.serial_number,
        )
        return self._system_status

    async def disconnect(self) -> None:
        """Logout and close HTTP connection."""
        if self._http:
            await self._session_mgr.logout(self._http)
            await self._http.aclose()
            self._http = None

    async def __aenter__(self) -> FMGClient:
        await self.connect()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.disconnect()

    # ------------------------------------------------------------------
    # Low-level JSON-RPC call
    # ------------------------------------------------------------------

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    @staticmethod
    def _sleep_for(attempt: int) -> float:
        """Backoff delay for ``attempt`` (1-indexed) with +/-30% jitter."""
        base: float = min(_BACKOFF_BASE * (2 ** (attempt - 1)), _BACKOFF_MAX)
        # Symmetric jitter so half the time we back off less, half more —
        # lets a cluster desynchronise even from a cold start. ``random``
        # types as Any in mypy strict, so explicit float() pins the return.
        jitter: float = float(random.uniform(-_BACKOFF_JITTER, _BACKOFF_JITTER))
        delay: float = base * (1.0 + jitter)
        return max(0.0, delay)

    async def _post_payload(self, payload: dict[str, Any]) -> JsonRpcResponse:
        """POST a JSON-RPC payload with transport-level retries.

        Single chokepoint shared by :meth:`_call` (single-op) and
        :meth:`multiplex` (N-op) so every outbound call benefits from the
        same retry + error handling — no fast path skips them.
        """
        if not self._http:
            raise FMGError("Client not connected — call connect() first")

        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                resp = await self._http.post(self._session_mgr.base_url, json=payload)
                # Retry transient server-side codes before raising.
                if resp.status_code in _RETRIABLE_HTTP:
                    last_error = httpx.HTTPStatusError(
                        f"transient HTTP {resp.status_code}",
                        request=resp.request,
                        response=resp,
                    )
                    if attempt < self._max_retries:
                        wait = self._sleep_for(attempt)
                        logger.warning(
                            "FMG returned HTTP %d (attempt %d/%d), retrying in %.1fs",
                            resp.status_code,
                            attempt,
                            self._max_retries,
                            wait,
                        )
                        await asyncio.sleep(wait)
                        continue
                    # Out of retries — fall through to raise_for_status so
                    # the exception type matches legacy callers.
                resp.raise_for_status()
                return JsonRpcResponse.model_validate(resp.json())

            except _RETRIABLE_EXC as exc:
                last_error = exc
                if attempt < self._max_retries:
                    wait = self._sleep_for(attempt)
                    logger.warning(
                        "FMG request failed (attempt %d/%d), retrying in %.1fs: %s",
                        attempt,
                        self._max_retries,
                        wait,
                        exc,
                    )
                    await asyncio.sleep(wait)
                    continue
            except httpx.HTTPStatusError as exc:
                raise FMGError(
                    f"HTTP {exc.response.status_code}: {exc.response.text}",
                    status_code=exc.response.status_code,
                ) from exc

        raise FMGError(f"Request failed after {self._max_retries} retries") from last_error

    async def _call(
        self,
        method: str,
        params: list[dict[str, Any]],
    ) -> JsonRpcResponse:
        """Execute a single JSON-RPC call with retry and error mapping."""
        payload: dict[str, Any] = {
            "method": method,
            "params": params,
            "id": self._next_id(),
            "verbose": 1,
        }
        payload = self._session_mgr.inject_session(payload)

        rpc_resp = await self._post_payload(payload)
        self._check_status(rpc_resp, params)
        return rpc_resp

    @staticmethod
    def _check_status(resp: JsonRpcResponse, params: list[dict[str, Any]]) -> None:
        """Map FMG status codes to typed exceptions."""
        code = resp.status_code
        msg = resp.status_message
        url = params[0].get("url", "") if params else ""

        if code == FMGStatusCode.OK:
            return
        if code == FMGStatusCode.OBJECT_NOT_FOUND:
            raise NotFoundError(f"Not found: {url} — {msg}", status_code=code, url=url)
        if code == FMGStatusCode.OBJECT_ALREADY_EXISTS:
            raise DuplicateError(f"Already exists: {url} — {msg}", status_code=code, url=url)
        if code == FMGStatusCode.NO_PERMISSION:
            raise AuthError(f"No permission: {url} — {msg}", status_code=code, url=url)

        raise FMGError(f"FMG error {code}: {url} — {msg}", status_code=code, url=url)

    # ------------------------------------------------------------------
    # CRUD helpers
    # ------------------------------------------------------------------

    async def get(self, url: str, **params: Any) -> Any:
        """GET (read) an object from FMG."""
        p: dict[str, Any] = {"url": url}
        p.update(params)
        resp = await self._call("get", [p])
        return resp.first.data

    async def add(self, url: str, data: dict[str, Any]) -> Any:
        """ADD (create) an object in FMG."""
        resp = await self._call("add", [{"url": url, "data": data}])
        return resp.first.data

    async def set(self, url: str, data: dict[str, Any]) -> Any:
        """SET (upsert) an object in FMG — idempotent."""
        resp = await self._call("set", [{"url": url, "data": data}])
        return resp.first.data

    async def update(self, url: str, data: dict[str, Any]) -> Any:
        """UPDATE an existing object in FMG."""
        resp = await self._call("update", [{"url": url, "data": data}])
        return resp.first.data

    async def delete(self, url: str, **params: Any) -> Any:
        """DELETE an object from FMG."""
        p: dict[str, Any] = {"url": url}
        p.update(params)
        resp = await self._call("delete", [p])
        return resp.first.data

    async def execute(self, url: str, data: dict[str, Any]) -> Any:
        """EXEC an action on FMG (e.g., install, script run)."""
        resp = await self._call("exec", [{"url": url, "data": data}])
        return resp.first.data

    async def multiplex(self, requests: list[dict[str, Any]]) -> list[Any]:
        """Send multiple params in a single JSON-RPC ``set`` call.

        Each entry in ``requests`` is a params dict (``url`` + optional
        ``data``). Returns a list of data results in the same order.

        Per-sub-request status codes are NOT translated into typed
        exceptions (there is no single ``url`` to attribute the failure
        to) — callers should inspect raw results when they need to tell
        partial from total failure.
        """
        if not requests:
            return []

        payload: dict[str, Any] = {
            "method": "set",
            "params": requests,
            "id": self._next_id(),
            "verbose": 1,
        }
        payload = self._session_mgr.inject_session(payload)

        rpc_resp = await self._post_payload(payload)
        return [r.data for r in rpc_resp.result]


__all__ = ["FMGClient", "FMGClientProtocol"]
