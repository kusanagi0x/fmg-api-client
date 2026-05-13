"""Tests for ``WorkspaceLockContext`` and ``workspace_session``.

Covers:
- Successful lock → commit → unlock sequence (via execute calls).
- ``-9`` graceful downgrade when ADOM is reachable (workspace-off).
- ``-9`` re-raise when the ADOM probe also fails.
- Pre-existing lock detection via lockinfo.
- Exception inside the context skips commit but still unlocks.
- Adapter is REQUIRED (constructor signature).
"""

from __future__ import annotations

from typing import Any

import pytest

from fmg_api_client import (
    FMG76Adapter,
    FMGError,
    LockError,
    WorkspaceLockContext,
    workspace_session,
)


class _RecordingClient:
    """Stub client capturing every call; ``execute`` and ``get`` configurable."""

    def __init__(
        self,
        *,
        get_responses: dict[str, Any] | None = None,
        execute_errors: dict[str, FMGError] | None = None,
        get_errors: dict[str, FMGError] | None = None,
    ) -> None:
        self.calls: list[tuple[str, str, Any]] = []
        self._get_responses = get_responses or {}
        self._execute_errors = execute_errors or {}
        self._get_errors = get_errors or {}

    async def get(self, url: str, **params: Any) -> Any:
        del params
        self.calls.append(("get", url, None))
        if url in self._get_errors:
            raise self._get_errors[url]
        return self._get_responses.get(url, {})

    async def execute(self, url: str, data: dict[str, Any]) -> Any:
        self.calls.append(("execute", url, data))
        if url in self._execute_errors:
            raise self._execute_errors[url]
        return {}

    async def set(self, url: str, data: dict[str, Any]) -> Any:
        self.calls.append(("set", url, data))
        return None

    async def add(self, url: str, data: dict[str, Any]) -> Any:
        self.calls.append(("add", url, data))
        return None

    async def update(self, url: str, data: dict[str, Any]) -> Any:
        self.calls.append(("update", url, data))
        return None

    async def delete(self, url: str, **params: Any) -> Any:
        self.calls.append(("delete", url, params))
        return None

    async def multiplex(self, requests: list[dict[str, Any]]) -> list[Any]:
        self.calls.append(("multiplex", "", requests))
        return [None] * len(requests)


# ---------- happy path ----------


@pytest.mark.asyncio
async def test_locked_session_commits_and_unlocks() -> None:
    client = _RecordingClient()
    async with WorkspaceLockContext(
        client,  # type: ignore[arg-type]
        "X",
        adapter=FMG76Adapter(),
    ):
        pass

    methods = [(m, u) for m, u, _ in client.calls if m == "execute"]
    # lockinfo is read first; lock executed; commit; unlock.
    urls = [u for m, u, _ in client.calls]
    assert "/dvmdb/adom/X/workspace/lockinfo" in urls  # pre-flight probe
    assert ("execute", "/dvmdb/adom/X/workspace/lock") in methods
    assert ("execute", "/dvmdb/adom/X/workspace/commit") in methods
    assert ("execute", "/dvmdb/adom/X/workspace/unlock") in methods


# ---------- workspace_enabled=False ----------


@pytest.mark.asyncio
async def test_workspace_disabled_skips_lock_commit_unlock() -> None:
    client = _RecordingClient()
    async with WorkspaceLockContext(
        client,  # type: ignore[arg-type]
        "X",
        adapter=FMG76Adapter(),
        workspace_enabled=False,
    ):
        pass
    execute_urls = [u for m, u, _ in client.calls if m == "execute"]
    assert execute_urls == []


# ---------- exception path ----------


@pytest.mark.asyncio
async def test_exception_inside_context_skips_commit_but_unlocks() -> None:
    client = _RecordingClient()
    with pytest.raises(RuntimeError):
        async with WorkspaceLockContext(
            client,  # type: ignore[arg-type]
            "X",
            adapter=FMG76Adapter(),
        ):
            raise RuntimeError("boom")

    execute_urls = [u for m, u, _ in client.calls if m == "execute"]
    assert "/dvmdb/adom/X/workspace/commit" not in execute_urls
    assert "/dvmdb/adom/X/workspace/unlock" in execute_urls


# ---------- -9 downgrade ----------


@pytest.mark.asyncio
async def test_minus9_with_reachable_adom_proceeds_without_lock() -> None:
    """FMG returns -9 → ADOM probe succeeds → log warn, continue without lock."""
    client = _RecordingClient(
        get_responses={
            # ADOM probe succeeds.
            "/dvmdb/adom/X": {"name": "X"},
        },
        execute_errors={
            "/dvmdb/adom/X/workspace/lock": FMGError("command invalid", status_code=-9),
        },
        get_errors={
            # lockinfo not exposed (typical when workspace disabled).
            "/dvmdb/adom/X/workspace/lockinfo": FMGError("Object does not exist", status_code=-3),
        },
    )

    async with workspace_session(
        client,  # type: ignore[arg-type]
        "X",
        adapter=FMG76Adapter(),
    ):
        pass

    # No commit / unlock once we downgraded to "no lock".
    execute_urls = [u for m, u, _ in client.calls if m == "execute"]
    assert "/dvmdb/adom/X/workspace/lock" in execute_urls
    assert "/dvmdb/adom/X/workspace/commit" not in execute_urls
    assert "/dvmdb/adom/X/workspace/unlock" not in execute_urls


@pytest.mark.asyncio
async def test_minus9_with_failing_adom_probe_raises() -> None:
    """-9 + ADOM probe also fails → LockError, do NOT proceed."""
    client = _RecordingClient(
        execute_errors={
            "/dvmdb/adom/MISSING/workspace/lock": FMGError("command invalid", status_code=-9),
        },
        get_errors={
            "/dvmdb/adom/MISSING": FMGError("not found", status_code=-3),
            "/dvmdb/adom/MISSING/workspace/lockinfo": FMGError("not found", status_code=-3),
        },
    )

    with pytest.raises(LockError):
        async with workspace_session(
            client,  # type: ignore[arg-type]
            "MISSING",
            adapter=FMG76Adapter(),
        ):
            pass


# ---------- pre-existing lock ----------


@pytest.mark.asyncio
async def test_lockinfo_reports_locked_raises_immediately() -> None:
    """Lockinfo says someone else holds the lock → LockError before lock attempt."""
    client = _RecordingClient(
        get_responses={
            "/dvmdb/adom/X/workspace/lockinfo": {
                "lock_state": 1,
                "lock_user": "alice",
            },
        },
    )

    with pytest.raises(LockError, match="locked by alice"):
        async with WorkspaceLockContext(
            client,  # type: ignore[arg-type]
            "X",
            adapter=FMG76Adapter(),
        ):
            pass

    # Should not have attempted to acquire after seeing locked state.
    execute_urls = [u for m, u, _ in client.calls if m == "execute"]
    assert "/dvmdb/adom/X/workspace/lock" not in execute_urls


# ---------- adapter is required ----------


def test_adapter_is_required_keyword_only() -> None:
    """No default — passing nothing must be a TypeError at construction."""
    client = _RecordingClient()
    with pytest.raises(TypeError):
        WorkspaceLockContext(client, "X")  # type: ignore[call-arg]
