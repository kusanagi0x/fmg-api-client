"""Pydantic models for FMG JSON-RPC request/response and system types.

Pure data models — no I/O. Reused by client, session, tasks.
"""

from __future__ import annotations

from enum import IntEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# JSON-RPC transport models
# ---------------------------------------------------------------------------


class JsonRpcRequest(BaseModel):
    """Outgoing JSON-RPC payload to FMG."""

    method: str
    params: list[dict[str, Any]]
    id: int = 1
    session: str | None = None
    verbose: int = 1


class JsonRpcResult(BaseModel):
    """Single result entry inside a JSON-RPC response."""

    status: dict[str, Any] = Field(default_factory=dict)
    data: Any = None
    url: str = ""


class JsonRpcResponse(BaseModel):
    """Incoming JSON-RPC response from FMG."""

    id: int = 1
    result: list[JsonRpcResult] = Field(default_factory=list)

    @property
    def first(self) -> JsonRpcResult:
        """Return the first result entry."""
        return self.result[0] if self.result else JsonRpcResult()

    @property
    def status_code(self) -> int:
        """Return the status code from the first result."""
        return int(self.first.status.get("code", -1))

    @property
    def status_message(self) -> str:
        """Return the status message from the first result."""
        return str(self.first.status.get("message", ""))


# ---------------------------------------------------------------------------
# FMG status codes — semantic mapping
# ---------------------------------------------------------------------------


class FMGStatusCode(IntEnum):
    """Well-known FMG JSON-RPC status codes.

    Negative codes are FMG conventions. Used by the client to map raw
    responses to typed exceptions (NotFoundError, DuplicateError, ...).
    """

    OK = 0
    OBJECT_ALREADY_EXISTS = -6
    OBJECT_NOT_FOUND = -3
    INVALID_URL = -8
    NO_PERMISSION = -11
    WORKSPACE_LOCKED = -20


# ---------------------------------------------------------------------------
# System models
# ---------------------------------------------------------------------------


class SystemStatus(BaseModel, frozen=True):
    """Response from ``GET /sys/status``.

    The ``Version`` field carries the FMG release (e.g. ``"v7.6.5-build..."``);
    :pyattr:`major_minor` extracts ``"7.6"`` for adapter selection.
    """

    model_config = {"populate_by_name": True}

    version: str = Field(default="", alias="Version")
    serial_number: str = Field(default="", alias="Serial Number")
    hostname: str = Field(default="", alias="Hostname")
    build: int = Field(default=0, alias="Build")
    admin_user: str = ""

    @property
    def major_minor(self) -> str:
        """Extract ``"X.Y"`` from version string like ``"v7.6.4"``."""
        v = self.version.lstrip("v")
        parts = v.split(".")
        if len(parts) >= 2:
            return f"{parts[0]}.{parts[1]}"
        return v


_TASK_STATE_STRING_TO_INT = {
    "pending": 0,
    "queued": 0,
    "running": 0,
    "done": 4,
    "success": 4,
    "error": 3,
    "failed": 3,
    "cancelled": 3,
    "canceled": 3,
    "aborted": 3,
}


class TaskStatus(BaseModel, frozen=True):
    """Response from ``GET /task/task/{id}``."""

    id: int = 0
    percent: int = 0
    state: int = Field(default=0, description="4 = done, 3 = error, others = running")
    line: list[dict[str, Any]] = Field(default_factory=list)
    title: str = ""
    num_done: int = 0
    num_err: int = 0
    tot_todo: int = 0

    @field_validator("state", mode="before")
    @classmethod
    def _coerce_state(cls, v: object) -> int:
        # FMG 7.4 returns numeric state codes; FMG 7.6 switched to strings
        # ("pending", "running", "done", "error", ...). Absorb the change at
        # the model boundary so is_done/is_error keep comparing ints.
        if isinstance(v, int):
            return v
        if isinstance(v, str):
            return _TASK_STATE_STRING_TO_INT.get(v.lower(), 0)
        return 0

    @field_validator("line", mode="before")
    @classmethod
    def _coerce_line(cls, v: object) -> list[dict[str, Any]]:
        # FMG 7.6 returns ``"line": None`` for tasks that have not produced
        # per-step output yet; 7.4 returned an empty list. Treat ``None``
        # as "no lines yet" so the model stays comparable across versions.
        if v is None:
            return []
        if isinstance(v, list):
            return v
        return []

    @property
    def is_done(self) -> bool:
        """Task completed (successfully or with errors)."""
        return self.state in (3, 4)

    @property
    def is_error(self) -> bool:
        """Task completed with errors."""
        return self.state == 3 or self.num_err > 0


__all__ = [
    "FMGStatusCode",
    "JsonRpcRequest",
    "JsonRpcResponse",
    "JsonRpcResult",
    "SystemStatus",
    "TaskStatus",
]
