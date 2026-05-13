"""Tests for the JSON-RPC + system + task models."""

from __future__ import annotations

import pytest

from fmg_api_client import (
    FMGStatusCode,
    JsonRpcResponse,
    JsonRpcResult,
    SystemStatus,
    TaskStatus,
)

# ---------- JsonRpcResponse ----------


def test_json_rpc_response_first_returns_first_result() -> None:
    resp = JsonRpcResponse(
        result=[
            JsonRpcResult(status={"code": 0, "message": "OK"}, data={"x": 1}),
            JsonRpcResult(status={"code": 0, "message": "OK"}, data={"x": 2}),
        ]
    )
    assert resp.first.data == {"x": 1}


def test_json_rpc_response_first_handles_empty() -> None:
    resp = JsonRpcResponse(result=[])
    assert resp.first.data is None
    assert resp.status_code == -1


def test_json_rpc_response_status_code_and_message() -> None:
    resp = JsonRpcResponse(
        result=[
            JsonRpcResult(
                status={"code": -3, "message": "Object does not exist"},
                data=None,
                url="/pm/config/adom/X/...",
            )
        ]
    )
    assert resp.status_code == -3
    assert resp.status_message == "Object does not exist"


# ---------- FMGStatusCode ----------


def test_fmg_status_code_values() -> None:
    assert FMGStatusCode.OK == 0
    assert FMGStatusCode.OBJECT_NOT_FOUND == -3
    assert FMGStatusCode.OBJECT_ALREADY_EXISTS == -6


# ---------- SystemStatus ----------


def test_system_status_major_minor_extracts_x_y() -> None:
    s = SystemStatus.model_validate({"Version": "v7.6.5-build1234", "Hostname": "fmg-lab"})
    assert s.major_minor == "7.6"
    assert s.hostname == "fmg-lab"


def test_system_status_major_minor_handles_no_minor() -> None:
    s = SystemStatus.model_validate({"Version": "8"})
    assert s.major_minor == "8"


def test_system_status_alias_population() -> None:
    s = SystemStatus.model_validate({"Serial Number": "FMG-VM-XYZ", "Version": "v7.4.3"})
    assert s.serial_number == "FMG-VM-XYZ"
    assert s.major_minor == "7.4"


# ---------- TaskStatus ----------


def test_task_status_state_int_passthrough() -> None:
    t = TaskStatus.model_validate({"id": 42, "state": 4, "percent": 100})
    assert t.is_done is True
    assert t.is_error is False


def test_task_status_state_string_done_coerced() -> None:
    t = TaskStatus.model_validate({"id": 42, "state": "done"})
    assert t.is_done is True
    assert t.is_error is False


def test_task_status_state_string_error_coerced() -> None:
    t = TaskStatus.model_validate({"id": 42, "state": "error"})
    assert t.is_done is True
    assert t.is_error is True


def test_task_status_state_string_running_treated_as_in_progress() -> None:
    t = TaskStatus.model_validate({"id": 42, "state": "running", "percent": 30})
    assert t.is_done is False


def test_task_status_line_none_becomes_empty_list() -> None:
    """FMG 7.6 returns ``"line": null`` for tasks without per-step output yet."""
    t = TaskStatus.model_validate({"id": 1, "line": None})
    assert t.line == []


def test_task_status_is_error_via_num_err() -> None:
    """A task can report state==4 (done) but still have errors in num_err."""
    t = TaskStatus.model_validate({"id": 1, "state": 4, "num_err": 2})
    assert t.is_done is True
    assert t.is_error is True


def test_task_status_invalid_state_defaults_to_zero() -> None:
    t = TaskStatus.model_validate({"id": 1, "state": "wat"})
    assert t.state == 0
    assert t.is_done is False


# ---------- TaskStatus parametric ----------


@pytest.mark.parametrize(
    ("raw", "expected_is_done", "expected_is_error"),
    [
        ("pending", False, False),
        ("queued", False, False),
        ("running", False, False),
        ("done", True, False),
        ("success", True, False),
        ("error", True, True),
        ("failed", True, True),
        ("cancelled", True, True),
        ("aborted", True, True),
    ],
)
def test_task_status_string_states_are_classified(
    raw: str, expected_is_done: bool, expected_is_error: bool
) -> None:
    t = TaskStatus.model_validate({"id": 1, "state": raw})
    assert t.is_done is expected_is_done
    assert t.is_error is expected_is_error
