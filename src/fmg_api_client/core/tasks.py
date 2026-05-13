"""``TaskTracker`` — async polling for FMG long-running tasks.

FMG returns a ``task_id`` for many operations (install_device, install_policy,
script execute, …). The tracker polls ``/task/task/<id>`` until the task is
done (success or error) or the timeout elapses.

Backoff: starts at 2s, multiplied by 1.5 each iteration, capped at 15s. This
keeps the FMG load reasonable for long installs while staying responsive on
quick ones.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

from fmg_api_client.core.exceptions import TaskTimeoutError
from fmg_api_client.core.models import TaskStatus

if TYPE_CHECKING:
    from fmg_api_client.core.client import FMGClientProtocol

logger = logging.getLogger(__name__)

# Polling defaults
_POLL_INTERVAL = 2.0
_POLL_BACKOFF = 1.5
_POLL_MAX_INTERVAL = 15.0


class TaskTracker:
    """Polls FMG task status until completion or timeout.

    Usage::

        tracker = TaskTracker(client)
        status = await tracker.wait(task_id=42, timeout=300)
        if status.is_error:
            handle_error(status)
    """

    def __init__(
        self,
        client: FMGClientProtocol,
        *,
        poll_interval: float = _POLL_INTERVAL,
        poll_backoff: float = _POLL_BACKOFF,
        poll_max_interval: float = _POLL_MAX_INTERVAL,
    ) -> None:
        self._client = client
        self._poll_interval = poll_interval
        self._poll_backoff = poll_backoff
        self._poll_max_interval = poll_max_interval

    async def wait(self, task_id: int, *, timeout: float = 300.0) -> TaskStatus:
        """Poll ``task_id`` until done or timeout.

        Args:
            task_id: FMG task ID to monitor.
            timeout: Maximum seconds to wait.

        Returns:
            Final :class:`TaskStatus`.

        Raises:
            TaskTimeoutError: If timeout exceeded before task completes.
        """
        start = time.monotonic()
        interval = self._poll_interval

        while True:
            elapsed = time.monotonic() - start
            if elapsed > timeout:
                raise TaskTimeoutError(
                    f"Task {task_id} timed out after {elapsed:.1f}s",
                    task_id=task_id,
                    elapsed=elapsed,
                )

            data = await self._client.get(f"/task/task/{task_id}")
            status = TaskStatus.model_validate(data) if isinstance(data, dict) else TaskStatus()

            logger.debug(
                "Task %d: %d%% (state=%d, done=%d, err=%d)",
                task_id,
                status.percent,
                status.state,
                status.num_done,
                status.num_err,
            )

            if status.is_done:
                if status.is_error:
                    logger.warning(
                        "Task %d completed with errors: %s",
                        task_id,
                        status.line,
                    )
                else:
                    logger.info("Task %d completed successfully", task_id)
                return status

            await asyncio.sleep(interval)
            interval = min(interval * self._poll_backoff, self._poll_max_interval)


__all__ = ["TaskTracker"]
