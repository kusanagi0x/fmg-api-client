"""Tests for the exception hierarchy."""

from __future__ import annotations

import pytest

from fmg_api_client import (
    AuthError,
    DuplicateError,
    FMGError,
    LockError,
    NotFoundError,
    TaskTimeoutError,
    VersionError,
)


def test_fmg_error_carries_code_and_url() -> None:
    e = FMGError("boom", status_code=-3, url="/x")
    assert e.status_code == -3
    assert e.url == "/x"
    assert str(e) == "boom"


def test_subclasses_inherit_from_fmg_error() -> None:
    for cls in (
        AuthError,
        LockError,
        NotFoundError,
        DuplicateError,
        VersionError,
    ):
        assert issubclass(cls, FMGError)


def test_task_timeout_error_carries_context() -> None:
    e = TaskTimeoutError("timed out", task_id=42, elapsed=305.5)
    assert e.task_id == 42
    assert e.elapsed == pytest.approx(305.5)
    assert e.status_code == -1


def test_subclass_can_be_caught_as_fmg_error() -> None:
    """Catching FMGError should match all transport-layer errors."""
    with pytest.raises(FMGError):
        raise NotFoundError("nope", status_code=-3, url="/y")
