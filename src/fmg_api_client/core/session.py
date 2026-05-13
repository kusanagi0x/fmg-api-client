"""Session management for FMG: API token (Bearer) and user/pass login.

A :class:`SessionManager` carries the auth state for a single FMG host.
The :class:`FMGClient` uses it to authenticate the underlying ``httpx``
client and inject the session token into JSON-RPC payloads when needed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from fmg_api_client.core.exceptions import AuthError
from fmg_api_client.core.models import JsonRpcResponse

logger = logging.getLogger(__name__)


@dataclass
class SessionManager:
    """Manages FMG authentication lifecycle.

    Prefers API token (Bearer header) when ``api_token`` is set.
    Falls back to user/pass login which yields a session token stored
    on the manager and injected into subsequent JSON-RPC payloads.
    """

    host: str
    api_token: str | None = None
    username: str | None = None
    password: str | None = None
    verify_ssl: bool = True

    _session_token: str | None = field(default=None, init=False, repr=False)

    @property
    def is_token_auth(self) -> bool:
        """Whether using API token authentication."""
        return self.api_token is not None

    @property
    def session_token(self) -> str | None:
        """Current session token (from login or API token)."""
        return self._session_token

    @property
    def base_url(self) -> str:
        """JSON-RPC endpoint URL."""
        return f"https://{self.host}/jsonrpc"

    def auth_headers(self) -> dict[str, str]:
        """Return HTTP headers for authentication."""
        if self.api_token:
            return {"Authorization": f"Bearer {self.api_token}"}
        return {}

    def inject_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Inject session token into JSON-RPC payload (user/pass auth only)."""
        if self._session_token and not self.is_token_auth:
            payload["session"] = self._session_token
        return payload

    async def login(self, client: httpx.AsyncClient) -> None:
        """Authenticate with FMG using user/pass and store session token."""
        if self.is_token_auth:
            logger.debug("Using API token auth — skipping login")
            return

        if not self.username or not self.password:
            raise AuthError("No API token or username/password provided")

        payload = {
            "method": "exec",
            "params": [
                {
                    "url": "/sys/login/user",
                    "data": {"user": self.username, "passwd": self.password},
                }
            ],
            "id": 1,
        }
        resp = await client.post(self.base_url, json=payload)
        resp.raise_for_status()

        rpc_resp = JsonRpcResponse.model_validate(resp.json())
        if rpc_resp.status_code != 0:
            raise AuthError(
                f"Login failed: {rpc_resp.status_message}",
                status_code=rpc_resp.status_code,
            )

        session = resp.json().get("session")
        if not session:
            raise AuthError("Login succeeded but no session token returned")

        self._session_token = session
        logger.info("Logged in to FMG %s as %s", self.host, self.username)

    async def logout(self, client: httpx.AsyncClient) -> None:
        """End the FMG session (user/pass auth only)."""
        if self.is_token_auth or not self._session_token:
            return

        payload = {
            "method": "exec",
            "params": [{"url": "/sys/logout"}],
            "session": self._session_token,
            "id": 1,
        }
        try:
            await client.post(self.base_url, json=payload)
            logger.info("Logged out from FMG %s", self.host)
        except httpx.HTTPError:
            logger.warning("Logout request failed — session may persist on FMG")
        finally:
            self._session_token = None


__all__ = ["SessionManager"]
