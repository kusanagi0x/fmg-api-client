"""Workspace lock context manager for FMG ADOM operations.

FMG workspace mode requires: lock → batch writes → commit → unlock.
This context manager guarantees unlock even on exception.

DI principle: the ``adapter`` is REQUIRED (no default). A silent default
would let the wrong FMG-version URLs be sent against a workspace that
does not recognise them; making it required forces the caller to be
explicit about which FMG version it targets.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from fmg_api_client.core.exceptions import FMGError, LockError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from fmg_api_client.core.client import FMGClientProtocol
    from fmg_api_client.versions.base import VersionAdapter

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WorkspaceLockState:
    """Current state of the FMG workspace lock for an ADOM."""

    locked: bool
    lock_user: str | None
    lock_time: datetime | None
    raw: dict[str, Any]

    def describe(self) -> str:
        if not self.locked:
            return "free"
        who = self.lock_user or "<unknown user>"
        when = f" since {self.lock_time.isoformat()}" if self.lock_time is not None else ""
        return f"locked by {who}{when}"


class WorkspaceLockContext:
    """Manages workspace lock lifecycle for an ADOM.

    Usage::

        ctx = WorkspaceLockContext(client, adom="root", adapter=FMG76Adapter())
        async with ctx:
            await client.set(...)  # writes batched inside lock
        # auto-commit + unlock on exit
    """

    def __init__(
        self,
        client: FMGClientProtocol,
        adom: str = "root",
        *,
        adapter: VersionAdapter,
        workspace_enabled: bool = True,
    ) -> None:
        self._client = client
        self._adom = adom
        self._workspace_enabled = workspace_enabled
        self._adapter = adapter
        self._locked = False

    @property
    def adom(self) -> str:
        """ADOM this lock manages."""
        return self._adom

    async def get_lock_state(self) -> WorkspaceLockState | None:
        """Read who currently holds the workspace lock on the ADOM.

        Returns ``None`` when the FMG does not expose lockinfo at the URL
        the adapter advertises (``-9`` / ``-3``) or when the call fails
        for any other reason — callers should treat that as "state unknown,
        fall through to normal lock attempt" rather than as "free".
        """
        url = self._adapter.workspace_lockinfo_url(self._adom)
        try:
            data = await self._client.get(url)
        except FMGError as exc:
            if exc.status_code in (-3, -9):
                logger.debug(
                    "Lockinfo not available at %s (FMG %d) — skipping pre-check",
                    url,
                    exc.status_code,
                )
                return None
            logger.warning(
                "Lockinfo read failed at %s (%s) — skipping pre-check",
                url,
                exc,
            )
            return None
        except Exception as exc:
            logger.warning(
                "Lockinfo read failed at %s (%s) — skipping pre-check",
                url,
                exc,
            )
            return None
        return self._parse_lockinfo(data if isinstance(data, dict) else {})

    @staticmethod
    def _parse_lockinfo(data: dict[str, Any]) -> WorkspaceLockState:
        # FMG sometimes wraps the payload in a single-key dict; drill in
        # to the first dict-shaped child only if the top level carries no
        # explicit lock keys. Generic keys like ``name`` are NOT used as a
        # fallback — that field belongs to the ADOM resource and would
        # falsely flag every probe response as "locked".
        lock_keys = ("lock_state", "lock_user", "lock_time", "state")
        payload = data
        if not any(k in payload for k in lock_keys):
            for value in data.values():
                if isinstance(value, dict) and any(k in value for k in lock_keys):
                    payload = value
                    break

        state_raw = payload.get("lock_state", payload.get("state"))
        try:
            state_int = int(state_raw) if state_raw is not None else 0
        except (TypeError, ValueError):
            state_int = 0
        user_raw = payload.get("lock_user")
        user = str(user_raw) if user_raw not in (None, "") else None
        # Canonical FMG signal is ``lock_state == 1``. We don't infer
        # locked-ness from a non-empty ``lock_user`` alone — some FMG
        # versions echo the last holder there even when state==0.
        locked = state_int == 1

        time_raw = payload.get("lock_time")
        lock_time: datetime | None = None
        if isinstance(time_raw, (int, float)) and time_raw > 0:
            try:
                lock_time = datetime.fromtimestamp(float(time_raw), tz=UTC)
            except (OSError, OverflowError, ValueError):
                lock_time = None

        return WorkspaceLockState(
            locked=locked,
            lock_user=user,
            lock_time=lock_time,
            raw=data,
        )

    async def lock(self) -> None:
        """Acquire workspace lock on the ADOM.

        On FMGs where workspace-mode is ``disabled``, the lock endpoint
        returns FMG error ``-9``. ``-9`` is overloaded — it also signals
        removed endpoints, permission denials, and nonexistent ADOMs —
        so we probe ``/dvmdb/adom/{adom}`` to distinguish:

        - ``-9`` + ADOM-probe succeeds → log a loud warning and proceed
          without lock (workspace-off is the most likely interpretation).
        - ``-9`` + probe fails → re-raise :class:`LockError`. Failing fast
          beats writing unprotected to the wrong place.
        - Any other FMG error → :class:`LockError`.

        Operators who know workspace mode is disabled should pass
        ``workspace_enabled=False`` at construction to skip the probe.
        """
        if not self._workspace_enabled:
            logger.debug(
                "Workspace mode disabled — skipping lock for ADOM %s",
                self._adom,
            )
            return

        # Pre-flight: ask FMG who holds the lock right now. If lockinfo
        # is unavailable (older FMG, removed endpoint) ``state`` is None
        # and we fall through to the regular ``add lock`` attempt.
        state = await self.get_lock_state()
        if state is not None and state.locked:
            url = self._adapter.workspace_lockinfo_url(self._adom)
            raise LockError(
                f"ADOM {self._adom} is already {state.describe()}. "
                "Have the holder release the lock or call "
                "`force_unlock()` if you know the lock is stale.",
                status_code=-23,
                url=url,
            )

        url = self._adapter.workspace_lock_url(self._adom)
        try:
            await self._client.execute(url, {})
        except FMGError as exc:
            if exc.status_code == -9:
                await self._downgrade_on_minus9_or_raise(url, exc)
                return
            raise LockError(
                f"Failed to lock ADOM {self._adom}: {exc}",
                status_code=exc.status_code,
                url=url,
            ) from exc
        except Exception as exc:
            raise LockError(
                f"Failed to lock ADOM {self._adom}: {exc}",
                status_code=-20,
                url=url,
            ) from exc
        self._locked = True
        logger.info("Workspace locked: ADOM %s", self._adom)

    async def _downgrade_on_minus9_or_raise(self, lock_url: str, original: FMGError) -> None:
        """Confirm ``-9`` really means "workspace off" before downgrading."""
        adom_url = f"/dvmdb/adom/{self._adom}"
        try:
            await self._client.get(adom_url)
        except Exception as probe_exc:
            raise LockError(
                f"Failed to lock ADOM {self._adom}: FMG returned -9 on "
                f"{lock_url} and the ADOM probe ({adom_url}) also failed "
                f"({probe_exc}). Not treating as workspace-off — the URL "
                "or ADOM may be wrong, or this FMG version removed the "
                "lock endpoint.",
                status_code=-9,
                url=lock_url,
            ) from original
        logger.warning(
            "FMG returned -9 on %s but ADOM %s is reachable — "
            "PROCEEDING WITHOUT WORKSPACE LOCK. Concurrent writers could "
            "interleave with this deployment. Pass workspace_enabled=False "
            "at construction to silence this probe.",
            lock_url,
            self._adom,
        )
        self._workspace_enabled = False

    async def commit(self) -> None:
        """Commit pending changes in the workspace."""
        if not self._workspace_enabled or not self._locked:
            return

        try:
            await self._client.execute(
                self._adapter.workspace_commit_url(self._adom),
                {},
            )
            logger.info("Workspace committed: ADOM %s", self._adom)
        except Exception as exc:
            logger.error("Workspace commit failed for ADOM %s: %s", self._adom, exc)
            raise

    async def force_unlock(self) -> None:
        """Attempt to release the workspace lock without holding it.

        FMG only honours the unlock if the caller's session owns the
        lock. Operators with the right token can clear a dangling lock
        from a crashed worker by calling this once before retrying.
        """
        url = self._adapter.workspace_unlock_url(self._adom)
        await self._client.execute(url, {})
        logger.warning(
            "force_unlock issued against ADOM %s — workspace lock released by external request",
            self._adom,
        )

    async def unlock(self) -> None:
        """Release workspace lock on the ADOM. Always safe to call."""
        if not self._workspace_enabled or not self._locked:
            return

        try:
            await self._client.execute(
                self._adapter.workspace_unlock_url(self._adom),
                {},
            )
            logger.info("Workspace unlocked: ADOM %s", self._adom)
        except Exception as exc:
            logger.warning("Workspace unlock failed for ADOM %s: %s", self._adom, exc)
        finally:
            self._locked = False

    async def __aenter__(self) -> WorkspaceLockContext:
        await self.lock()
        return self

    async def __aexit__(self, *exc: object) -> None:
        if exc[0] is None:
            # No exception — commit then unlock.
            await self.commit()
        else:
            logger.warning(
                "Exception during locked session on ADOM %s — skipping commit",
                self._adom,
            )
        await self.unlock()


@asynccontextmanager
async def workspace_session(
    client: FMGClientProtocol,
    adom: str = "root",
    *,
    adapter: VersionAdapter,
    workspace_enabled: bool = True,
) -> AsyncIterator[WorkspaceLockContext]:
    """Convenience async context manager for workspace operations."""
    ctx = WorkspaceLockContext(
        client,
        adom,
        adapter=adapter,
        workspace_enabled=workspace_enabled,
    )
    async with ctx:
        yield ctx


__all__ = [
    "WorkspaceLockContext",
    "WorkspaceLockState",
    "workspace_session",
]
