"""Tests for ``MetafieldManager``.

Critical assertions — each guards a real-world FMG behaviour:
- Signature ``set_per_device(device_name, {var: value})`` so a single
  call can set several variables on one device in one transaction.
- Adapter-driven payload uses ``value`` on 7.6, ``local-value`` on 7.4.
- Writes target the **collection** URL (no ``/<device>`` suffix); FMG
  matches by ``_scope`` and ``set`` is the idempotent upsert.
"""

from __future__ import annotations

from typing import Any

import pytest

from fmg_api_client import (
    FMG74Adapter,
    FMG76Adapter,
    MetafieldManager,
)


class _RecordingClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, Any]] = []

    async def get(self, url: str, **params: Any) -> Any:
        del params
        self.calls.append(("get", url, None))
        return None

    async def set(self, url: str, data: dict[str, Any]) -> Any:
        self.calls.append(("set", url, data))
        return {"name": data.get("name")}

    async def add(self, url: str, data: dict[str, Any]) -> Any:
        self.calls.append(("add", url, data))
        return None

    async def update(self, url: str, data: dict[str, Any]) -> Any:
        self.calls.append(("update", url, data))
        return None

    async def delete(self, url: str, **params: Any) -> Any:
        self.calls.append(("delete", url, params))
        return None

    async def execute(self, url: str, data: dict[str, Any]) -> Any:
        self.calls.append(("execute", url, data))
        return None

    async def multiplex(self, requests: list[dict[str, Any]]) -> list[Any]:
        self.calls.append(("multiplex", "", requests))
        return [None] * len(requests)


# ---------- set_per_device on 7.6 ----------


@pytest.mark.asyncio
async def test_set_per_device_uses_collection_url_and_value_field_on_76() -> None:
    client = _RecordingClient()
    mgr = MetafieldManager(client, "LAB", adapter=FMG76Adapter())  # type: ignore[arg-type]

    await mgr.set_per_device(
        "HQ-MAIN",
        {"INET1_ip": "198.51.100.1", "hostname": "HQ-MAIN"},
    )

    set_calls = [(url, data) for m, url, data in client.calls if m == "set"]
    assert len(set_calls) == 2
    assert set_calls[0] == (
        "/pm/config/adom/LAB/obj/fmg/variable/INET1_ip/dynamic_mapping",
        {
            "_scope": [{"name": "HQ-MAIN", "vdom": "root"}],
            "value": "198.51.100.1",
        },
    )
    assert set_calls[1] == (
        "/pm/config/adom/LAB/obj/fmg/variable/hostname/dynamic_mapping",
        {
            "_scope": [{"name": "HQ-MAIN", "vdom": "root"}],
            "value": "HQ-MAIN",
        },
    )


# ---------- set_per_device on 7.4 ----------


@pytest.mark.asyncio
async def test_set_per_device_uses_local_value_field_on_74() -> None:
    client = _RecordingClient()
    mgr = MetafieldManager(client, "LAB", adapter=FMG74Adapter())  # type: ignore[arg-type]

    await mgr.set_per_device("HQ-MAIN", {"INET1_ip": "198.51.100.1"})

    set_calls = [(url, data) for m, url, data in client.calls if m == "set"]
    # 7.4 uses obj/dynamic/variable, payload field is local-value.
    assert set_calls == [
        (
            "/pm/config/adom/LAB/obj/dynamic/variable/INET1_ip/dynamic_mapping",
            {
                "_scope": [{"name": "HQ-MAIN", "vdom": "root"}],
                "local-value": "198.51.100.1",
            },
        )
    ]


# ---------- set_per_device with custom vdom ----------


@pytest.mark.asyncio
async def test_set_per_device_respects_custom_vdom() -> None:
    client = _RecordingClient()
    mgr = MetafieldManager(client, "LAB", adapter=FMG76Adapter())  # type: ignore[arg-type]

    await mgr.set_per_device("dev1", {"X": "y"}, vdom="customer-vdom")

    set_calls = [data for m, _, data in client.calls if m == "set"]
    assert set_calls[0]["_scope"] == [{"name": "dev1", "vdom": "customer-vdom"}]


# ---------- create_if_missing ----------


@pytest.mark.asyncio
async def test_create_if_missing_uses_value_field_on_76() -> None:
    client = _RecordingClient()
    mgr = MetafieldManager(client, "LAB", adapter=FMG76Adapter())  # type: ignore[arg-type]
    await mgr.create_if_missing("INET1_ip", "default-203")
    set_calls = [(url, data) for m, url, data in client.calls if m == "set"]
    assert set_calls == [
        (
            "/pm/config/adom/LAB/obj/fmg/variable",
            {"name": "INET1_ip", "value": "default-203"},
        )
    ]


@pytest.mark.asyncio
async def test_create_if_missing_uses_default_value_field_on_74() -> None:
    client = _RecordingClient()
    mgr = MetafieldManager(client, "LAB", adapter=FMG74Adapter())  # type: ignore[arg-type]
    await mgr.create_if_missing("INET1_ip", "default-203")
    set_calls = [(url, data) for m, url, data in client.calls if m == "set"]
    assert set_calls == [
        (
            "/pm/config/adom/LAB/obj/dynamic/variable",
            {"name": "INET1_ip", "default-value": "default-203"},
        )
    ]


# ---------- ensure_variables ----------


@pytest.mark.asyncio
async def test_ensure_variables_creates_unique_sorted() -> None:
    client = _RecordingClient()
    mgr = MetafieldManager(client, "LAB", adapter=FMG76Adapter())  # type: ignore[arg-type]
    await mgr.ensure_variables(["b", "a", "b", "c"])
    set_payloads = [data for m, _, data in client.calls if m == "set"]
    names = [p["name"] for p in set_payloads]
    assert names == ["a", "b", "c"]


# ---------- adapter required ----------


def test_metafield_manager_requires_adapter() -> None:
    """Adapter is keyword-required — no silent default can mis-target a version."""
    client = _RecordingClient()
    with pytest.raises(TypeError):
        MetafieldManager(client, "LAB")  # type: ignore[call-arg]
