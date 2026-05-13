"""Typed exception hierarchy for FMG JSON-RPC errors.

Each subclass corresponds to a well-known FMG status code (see
:class:`~fmg_api_client.core.models.FMGStatusCode`) or transport-level
condition. Workflow-semantic errors (preflight conflicts, etc.) belong
to the caller's domain, not to this transport layer.
"""

from __future__ import annotations


class FMGError(Exception):
    """Base exception for all FortiManager API errors."""

    def __init__(self, message: str, *, status_code: int = -1, url: str = "") -> None:
        self.status_code = status_code
        self.url = url
        super().__init__(message)


class AuthError(FMGError):
    """Authentication or token failure."""


class LockError(FMGError):
    """Workspace lock acquisition or release failure."""


class NotFoundError(FMGError):
    """Requested object does not exist in FMG."""


class DuplicateError(FMGError):
    """Object already exists in FMG."""


class TaskTimeoutError(FMGError):
    """Task polling exceeded the configured timeout."""

    def __init__(self, message: str, *, task_id: int, elapsed: float) -> None:
        self.task_id = task_id
        self.elapsed = elapsed
        super().__init__(message, status_code=-1)


class VersionError(FMGError):
    """Unsupported FMG version or version-specific feature unavailable."""


__all__ = [
    "AuthError",
    "DuplicateError",
    "FMGError",
    "LockError",
    "NotFoundError",
    "TaskTimeoutError",
    "VersionError",
]
