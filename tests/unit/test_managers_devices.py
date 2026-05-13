"""Tests for ``DeviceManager`` against a recording client."""

from __future__ import annotations

from typing import Any

import pytest

from fmg_api_client import (
    DeviceManager,
    DuplicateError,
    FMG76Adapter,
    NotFoundError,
)


class _RecordingClient:
    """Configurable fake: GETs return canned dicts; raises set per URL."""

    def __init__(
        self,
        *,
        get_responses: dict[str, Any] | None = None,
        get_errors: dict[str, Exception] | None = None,
        add_errors: dict[str, Exception] | None = None,
    ) -> None:
        self.calls: list[tuple[str, str, Any]] = []
        self._get_responses = get_responses or {}
        self._get_errors = get_errors or {}
        self._add_errors = add_errors or {}

    async def get(self, url: str, **params: Any) -> Any:
        del params
        self.calls.append(("get", url, None))
        if url in self._get_errors:
            raise self._get_errors[url]
        return self._get_responses.get(url)

    async def add(self, url: str, data: dict[str, Any]) -> Any:
        self.calls.append(("add", url, data))
        if url in self._add_errors:
            raise self._add_errors[url]
        return {}

    async def set(self, url: str, data: dict[str, Any]) -> Any:
        self.calls.append(("set", url, data))
        return None

    async def update(self, url: str, data: dict[str, Any]) -> Any:
        self.calls.append(("update", url, data))
        return None

    async def delete(self, url: str, **params: Any) -> Any:
        self.calls.append(("delete", url, params))
        return None

    async def execute(self, url: str, data: dict[str, Any]) -> Any:
        self.calls.append(("execute", url, data))
        return {"status": {"code": 0}}

    async def multiplex(self, requests: list[dict[str, Any]]) -> list[Any]:
        self.calls.append(("multiplex", "", requests))
        return [None] * len(requests)


def _mgr(client: Any) -> DeviceManager:
    return DeviceManager(client, "LAB", adapter=FMG76Adapter())


# ---------- ensure_model_device ----------


@pytest.mark.asyncio
async def test_ensure_model_device_returns_existing_when_present() -> None:
    client = _RecordingClient(
        get_responses={
            "/dvmdb/adom/LAB/device/HQ-MAIN": {"name": "HQ-MAIN", "oid": 42},
        },
    )
    record, created = await _mgr(client).ensure_model_device("HQ-MAIN", "FGVM02TM26000001")
    assert created is False
    assert record == {"name": "HQ-MAIN", "oid": 42}
    # Should NOT have called execute (no create attempt).
    assert not any(m == "execute" for m, _, _ in client.calls)


@pytest.mark.asyncio
async def test_ensure_model_device_creates_when_missing() -> None:
    """First GET returns 404 → execute add → poll succeeds."""
    poll_attempts = {"count": 0}
    created_record = {"name": "NEW", "oid": 99}

    class _PollClient(_RecordingClient):
        async def get(self, url: str, **params: Any) -> Any:
            del params
            self.calls.append(("get", url, None))
            if url == "/dvmdb/adom/LAB/device/NEW":
                # First call: not found. Second call: success.
                poll_attempts["count"] += 1
                if poll_attempts["count"] == 1:
                    raise NotFoundError("nope", status_code=-3, url=url)
                return created_record
            return None

    client = _PollClient()
    record, was_created = await _mgr(client).ensure_model_device(
        "NEW",
        "FGVM02TM26000099",
        os_ver="7.6.5",
        psk="ignored-psk",
    )
    assert was_created is True
    assert record == created_record
    # Verify the execute call carried os_ver=7, mr=6, os_type=fos (7.6 extras).
    execute_calls = [(url, data) for m, url, data in client.calls if m == "execute"]
    assert len(execute_calls) == 1
    url, data = execute_calls[0]
    assert url == "/dvm/cmd/add/device"
    assert data["adom"] == "LAB"
    assert data["device"]["os_ver"] == 7
    assert data["device"]["mr"] == 6
    assert data["device"]["os_type"] == "fos"
    assert data["device"]["psk"] == "ignored-psk"


# ---------- ensure_device_group ----------


@pytest.mark.asyncio
async def test_ensure_device_group_skips_when_already_present() -> None:
    client = _RecordingClient(get_responses={"/dvmdb/adom/LAB/group/hubs": {"name": "hubs"}})
    await _mgr(client).ensure_device_group("hubs")
    # No add call when the group already exists.
    assert not any(m == "add" for m, _, _ in client.calls)


@pytest.mark.asyncio
async def test_ensure_device_group_creates_when_missing() -> None:
    client = _RecordingClient(
        get_errors={
            "/dvmdb/adom/LAB/group/hubs": NotFoundError(
                "nope", status_code=-3, url="/dvmdb/adom/LAB/group/hubs"
            )
        }
    )
    await _mgr(client).ensure_device_group("hubs")
    add_calls = [(url, data) for m, url, data in client.calls if m == "add"]
    assert add_calls == [("/dvmdb/adom/LAB/group", {"name": "hubs", "type": "normal"})]


# ---------- assign_to_group ----------


@pytest.mark.asyncio
async def test_assign_to_group_idempotent_on_duplicate() -> None:
    """DuplicateError swallowed (device already a member)."""
    client = _RecordingClient(
        get_responses={"/dvmdb/adom/LAB/group/hubs": {"name": "hubs"}},
        add_errors={
            "/dvmdb/adom/LAB/group/hubs/object member": DuplicateError(
                "already", status_code=-6, url="/x"
            )
        },
    )
    result = await _mgr(client).assign_to_group("HQ-MAIN", "hubs")
    assert result is None  # signaling skipped


@pytest.mark.asyncio
async def test_assign_to_group_creates_group_first_then_adds_member() -> None:
    client = _RecordingClient(
        get_errors={"/dvmdb/adom/LAB/group/hubs": NotFoundError("nope", status_code=-3, url="/x")}
    )
    await _mgr(client).assign_to_group("HQ-MAIN", "hubs")
    add_urls = [url for m, url, _ in client.calls if m == "add"]
    # Group created, then member added.
    assert add_urls == [
        "/dvmdb/adom/LAB/group",
        "/dvmdb/adom/LAB/group/hubs/object member",
    ]


# ---------- list_group_members ----------


@pytest.mark.asyncio
async def test_list_group_members_filters_metadata_only_response() -> None:
    """Empty groups return their own metadata; we must filter it out."""
    client = _RecordingClient(
        get_responses={
            "/dvmdb/adom/LAB/group/empty/object member": {
                "name": "empty",
                "oid": 1,
                "type": "normal",
            }
        }
    )
    members = await _mgr(client).list_group_members("empty")
    assert members == []  # no real member because no `vdom` field


@pytest.mark.asyncio
async def test_list_group_members_returns_real_members() -> None:
    client = _RecordingClient(
        get_responses={
            "/dvmdb/adom/LAB/group/hubs/object member": [
                {"name": "HQ-MAIN", "vdom": "root"},
                {"name": "HQ-DR", "vdom": "root"},
            ]
        }
    )
    members = await _mgr(client).list_group_members("hubs")
    assert members == ["HQ-MAIN", "HQ-DR"]


# ---------- adapter is required ----------


def test_adapter_required_keyword_only() -> None:
    """No default adapter — bug-class extinction by construction."""
    client = _RecordingClient()
    with pytest.raises(TypeError):
        DeviceManager(client, "LAB")  # type: ignore[call-arg]
