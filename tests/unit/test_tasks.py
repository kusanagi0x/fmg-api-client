"""Tests for ``TaskTracker`` polling loop."""

from __future__ import annotations

from typing import Any

import pytest

from fmg_api_client import TaskStatus, TaskTimeoutError, TaskTracker


class _FakeClient:
    """In-memory client that replays a queued list of task responses."""

    def __init__(self, queue: list[dict[str, Any]]) -> None:
        self._queue = list(queue)
        self.calls = 0

    async def get(self, url: str, **params: Any) -> Any:
        del url, params
        self.calls += 1
        if not self._queue:
            return {"id": 1, "state": 4, "percent": 100}
        return self._queue.pop(0)


@pytest.mark.asyncio
async def test_wait_returns_done_status_immediately() -> None:
    fake = _FakeClient([{"id": 1, "state": 4, "percent": 100}])
    tracker = TaskTracker(
        fake,  # type: ignore[arg-type]
        poll_interval=0.0,
        poll_max_interval=0.0,
    )
    status = await tracker.wait(1, timeout=5.0)
    assert isinstance(status, TaskStatus)
    assert status.is_done is True
    assert status.is_error is False
    assert fake.calls == 1


@pytest.mark.asyncio
async def test_wait_polls_until_done() -> None:
    fake = _FakeClient(
        [
            {"id": 1, "state": "running", "percent": 10},
            {"id": 1, "state": "running", "percent": 50},
            {"id": 1, "state": "done", "percent": 100},
        ]
    )
    tracker = TaskTracker(
        fake,  # type: ignore[arg-type]
        poll_interval=0.0,
        poll_max_interval=0.0,
    )
    status = await tracker.wait(1, timeout=5.0)
    assert status.is_done is True
    assert fake.calls == 3


@pytest.mark.asyncio
async def test_wait_returns_error_status() -> None:
    fake = _FakeClient([{"id": 1, "state": "error", "num_err": 2, "line": []}])
    tracker = TaskTracker(
        fake,  # type: ignore[arg-type]
        poll_interval=0.0,
        poll_max_interval=0.0,
    )
    status = await tracker.wait(1, timeout=5.0)
    assert status.is_done is True
    assert status.is_error is True


@pytest.mark.asyncio
async def test_wait_raises_timeout_when_task_never_finishes() -> None:
    fake = _FakeClient(
        [
            {"id": 1, "state": "running", "percent": 10},
        ]
        * 1000  # plenty so we never hit "done" before timeout
    )
    tracker = TaskTracker(
        fake,  # type: ignore[arg-type]
        poll_interval=0.0,
        poll_max_interval=0.0,
    )
    with pytest.raises(TaskTimeoutError) as ei:
        await tracker.wait(1, timeout=0.0)  # immediate timeout
    assert ei.value.task_id == 1
