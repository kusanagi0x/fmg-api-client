"""Tests for the remaining managers (install, cli_templates, addresses, services,
policies, blueprints, provisioning).

Each manager is tiny and delegates URL building to the adapter, so the
tests verify URL/payload shape via a recording client. Adapter-required
construction is asserted once per manager class.
"""

from __future__ import annotations

from typing import Any

import pytest

from fmg_api_client import (
    AddressGroupManager,
    AddressManager,
    BlueprintManager,
    CLITemplateGroupManager,
    CLITemplateManager,
    FMG76Adapter,
    InstallManager,
    PolicyPackageManager,
    ProvisioningTemplateManager,
    ServiceGroupManager,
    ServiceManager,
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

    async def execute(self, url: str, data: dict[str, Any]) -> Any:
        self.calls.append(("execute", url, data))
        return {"task": 4242}

    async def multiplex(self, requests: list[dict[str, Any]]) -> list[Any]:
        self.calls.append(("multiplex", "", requests))
        return [None] * len(requests)


def _adapter() -> FMG76Adapter:
    return FMG76Adapter()


# ---------- InstallManager ----------


@pytest.mark.asyncio
async def test_install_device_settings_returns_task_id() -> None:
    client = _RecordingClient()
    mgr = InstallManager(client, "LAB", adapter=_adapter())  # type: ignore[arg-type]

    task_id = await mgr.install_device_settings("HQ-MAIN")
    assert task_id == 4242
    execute_calls = [(url, data) for m, url, data in client.calls if m == "execute"]
    assert execute_calls == [
        (
            "/securityconsole/install/device",
            {
                "adom": "LAB",
                "scope": [{"name": "HQ-MAIN", "vdom": "root"}],
                "flags": ["none"],
            },
        )
    ]


@pytest.mark.asyncio
async def test_install_policy_package_returns_task_id() -> None:
    client = _RecordingClient()
    mgr = InstallManager(client, "LAB", adapter=_adapter())  # type: ignore[arg-type]
    task_id = await mgr.install_policy_package("pkg-1", "HQ-MAIN")
    assert task_id == 4242
    execute_calls = [(url, data) for m, url, data in client.calls if m == "execute"]
    assert execute_calls == [
        (
            "/securityconsole/install/package",
            {
                "adom": "LAB",
                "pkg": "pkg-1",
                "scope": [{"name": "HQ-MAIN", "vdom": "root"}],
                "flags": ["none"],
            },
        )
    ]


@pytest.mark.asyncio
async def test_install_preview_uses_device_field_and_json_flag() -> None:
    client = _RecordingClient()
    mgr = InstallManager(client, "LAB", adapter=_adapter())  # type: ignore[arg-type]
    await mgr.install_preview("HQ-MAIN")
    execute_calls = [(url, data) for m, url, data in client.calls if m == "execute"]
    assert execute_calls == [
        (
            "/securityconsole/install/preview",
            {
                "adom": "LAB",
                "device": [{"name": "HQ-MAIN", "vdom": "root"}],
                "flags": ["json"],
            },
        )
    ]


# ---------- CLITemplateManager ----------


@pytest.mark.asyncio
async def test_cli_template_upsert_targets_versioned_url() -> None:
    client = _RecordingClient()
    mgr = CLITemplateManager(client, "LAB", adapter=_adapter())  # type: ignore[arg-type]
    await mgr.upsert({"name": "00-Mgmt", "script": "config system global\nend\n"})
    set_calls = [(url, data) for m, url, data in client.calls if m == "set"]
    assert set_calls[0][0] == "/pm/config/adom/LAB/obj/cli/template/00-Mgmt"


@pytest.mark.asyncio
async def test_cli_template_group_assign_to_device_group() -> None:
    client = _RecordingClient()
    mgr = CLITemplateGroupManager(  # type: ignore[arg-type]
        client, "LAB", adapter=_adapter()
    )
    await mgr.assign_to_device_group("base-group", "hubs")
    add_calls = [(url, data) for m, url, data in client.calls if m == "add"]
    assert add_calls == [
        (
            "/pm/config/adom/LAB/obj/cli/template-group/base-group/scope member",
            {"name": "hubs", "vdom": "root"},
        )
    ]


# ---------- AddressManager / ServiceManager ----------


@pytest.mark.asyncio
async def test_address_upsert_uses_obj_firewall_address() -> None:
    client = _RecordingClient()
    mgr = AddressManager(client, "LAB", adapter=_adapter())  # type: ignore[arg-type]
    await mgr.upsert({"name": "LAN-A", "subnet": ["10.10.0.0", "255.255.255.0"]})
    set_calls = [url for m, url, _ in client.calls if m == "set"]
    assert set_calls == ["/pm/config/adom/LAB/obj/firewall/address/LAN-A"]


@pytest.mark.asyncio
async def test_address_group_upsert_uses_addrgrp() -> None:
    client = _RecordingClient()
    mgr = AddressGroupManager(client, "LAB", adapter=_adapter())  # type: ignore[arg-type]
    await mgr.upsert({"name": "All-LANs", "member": ["LAN-A", "LAN-B"]})
    set_calls = [url for m, url, _ in client.calls if m == "set"]
    assert set_calls == ["/pm/config/adom/LAB/obj/firewall/addrgrp/All-LANs"]


@pytest.mark.asyncio
async def test_service_managers_use_service_paths() -> None:
    client = _RecordingClient()
    custom = ServiceManager(client, "LAB", adapter=_adapter())  # type: ignore[arg-type]
    grp = ServiceGroupManager(client, "LAB", adapter=_adapter())  # type: ignore[arg-type]
    await custom.upsert({"name": "MY-HTTP"})
    await grp.upsert({"name": "WEB"})
    set_urls = [url for m, url, _ in client.calls if m == "set"]
    assert set_urls == [
        "/pm/config/adom/LAB/obj/firewall/service/custom/MY-HTTP",
        "/pm/config/adom/LAB/obj/firewall/service/group/WEB",
    ]


# ---------- PolicyPackageManager ----------


@pytest.mark.asyncio
async def test_policy_package_upsert_targets_pkg_url() -> None:
    client = _RecordingClient()
    mgr = PolicyPackageManager(client, "LAB", adapter=_adapter())  # type: ignore[arg-type]
    await mgr.upsert({"name": "default"})
    set_calls = [(url, data) for m, url, data in client.calls if m == "set"]
    assert set_calls == [("/pm/pkg/adom/LAB/default", {"name": "default"})]


@pytest.mark.asyncio
async def test_policy_package_upsert_rule_uses_policyid_in_url() -> None:
    client = _RecordingClient()
    mgr = PolicyPackageManager(client, "LAB", adapter=_adapter())  # type: ignore[arg-type]
    await mgr.upsert_rule(
        "default",
        {"policyid": 1, "name": "allow-all", "action": 1},
    )
    set_calls = [(url, data) for m, url, data in client.calls if m == "set"]
    assert set_calls == [
        (
            "/pm/config/adom/LAB/pkg/default/firewall/policy/1",
            {"policyid": 1, "name": "allow-all", "action": 1},
        )
    ]


@pytest.mark.asyncio
async def test_policy_package_add_scope_member() -> None:
    client = _RecordingClient()
    mgr = PolicyPackageManager(client, "LAB", adapter=_adapter())  # type: ignore[arg-type]
    await mgr.add_scope_member("default", "hubs")
    add_calls = [(url, data) for m, url, data in client.calls if m == "add"]
    assert add_calls == [
        (
            "/pm/pkg/adom/LAB/default/scope member",
            {"name": "hubs", "vdom": "root"},
        )
    ]


# ---------- BlueprintManager ----------


@pytest.mark.asyncio
async def test_blueprint_upsert_targets_blueprint_url() -> None:
    client = _RecordingClient()
    mgr = BlueprintManager(client, "LAB", adapter=_adapter())  # type: ignore[arg-type]
    await mgr.upsert({"name": "bp-1"})
    set_calls = [url for m, url, _ in client.calls if m == "set"]
    assert set_calls == ["/pm/config/adom/LAB/obj/fmg/device/blueprint/bp-1"]


# ---------- ProvisioningTemplateManager ----------


@pytest.mark.asyncio
async def test_provisioning_upsert_injects_type_field() -> None:
    """FMG 7.6 requires ``type: <slug>`` in the body — manager auto-injects."""
    client = _RecordingClient()
    mgr = ProvisioningTemplateManager(  # type: ignore[arg-type]
        client, "LAB", adapter=_adapter(), slug="wanprof"
    )
    await mgr.upsert({"name": "sdwan-hub"})  # no `type` provided
    set_calls = [(url, data) for m, url, data in client.calls if m == "set"]
    assert set_calls == [
        ("/pm/wanprof/adom/LAB/sdwan-hub", {"name": "sdwan-hub", "type": "wanprof"})
    ]


@pytest.mark.asyncio
async def test_provisioning_upsert_respects_explicit_type() -> None:
    """If caller already set ``type``, manager doesn't overwrite."""
    client = _RecordingClient()
    mgr = ProvisioningTemplateManager(  # type: ignore[arg-type]
        client, "LAB", adapter=_adapter(), slug="devprof"
    )
    await mgr.upsert({"name": "dp", "type": "devprof", "extra": 1})
    set_calls = [(url, data) for m, url, data in client.calls if m == "set"]
    assert set_calls == [
        ("/pm/devprof/adom/LAB/dp", {"name": "dp", "type": "devprof", "extra": 1})
    ]


# ---------- adapter required everywhere ----------


@pytest.mark.parametrize(
    "cls",
    [
        InstallManager,
        CLITemplateManager,
        CLITemplateGroupManager,
        AddressManager,
        AddressGroupManager,
        ServiceManager,
        ServiceGroupManager,
        PolicyPackageManager,
        BlueprintManager,
    ],
)
def test_managers_require_adapter(cls: type) -> None:
    """No defaults — every manager refuses construction without ``adapter``."""
    with pytest.raises(TypeError):
        cls(_RecordingClient(), "LAB")  # type: ignore[call-arg]


def test_provisioning_manager_requires_adapter_and_slug() -> None:
    with pytest.raises(TypeError):
        ProvisioningTemplateManager(_RecordingClient(), "LAB")  # type: ignore[call-arg]
