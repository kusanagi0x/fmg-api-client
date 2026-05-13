"""URL builders per FMG version.

Each adapter must produce stable URLs for every endpoint a manager hits.
Tests are exhaustive (one per method) so a typo in any builder fails CI
loudly. The 7.4 vs 7.6 divergences (dynamic_variable namespace) get
explicit per-version asserts.
"""

from __future__ import annotations

import pytest

from fmg_api_client import (
    BaseAdapter,
    FMG72Adapter,
    FMG74Adapter,
    FMG76Adapter,
)


@pytest.fixture
def v72() -> FMG72Adapter:
    return FMG72Adapter()


@pytest.fixture
def v74() -> FMG74Adapter:
    return FMG74Adapter()


@pytest.fixture
def v76() -> FMG76Adapter:
    return FMG76Adapter()


# ---------- workspace ----------


@pytest.mark.parametrize(
    ("method", "expected"),
    [
        ("workspace_lock_url", "/dvmdb/adom/X/workspace/lock"),
        ("workspace_commit_url", "/dvmdb/adom/X/workspace/commit"),
        ("workspace_unlock_url", "/dvmdb/adom/X/workspace/unlock"),
        ("workspace_lockinfo_url", "/dvmdb/adom/X/workspace/lockinfo"),
    ],
)
def test_workspace_urls_shared_across_versions(
    method: str,
    expected: str,
    v72: BaseAdapter,
    v74: BaseAdapter,
    v76: BaseAdapter,
) -> None:
    for adapter in (v72, v74, v76):
        assert getattr(adapter, method)("X") == expected


# ---------- devices ----------


def test_device_urls(v76: FMG76Adapter) -> None:
    assert v76.device_url("X", "fgt1") == "/dvmdb/adom/X/device/fgt1"
    assert v76.device_group_url("X", "hubs") == "/dvmdb/adom/X/group/hubs"
    assert v76.device_group_collection_url("X") == "/dvmdb/adom/X/group"
    assert v76.device_group_member_url("X", "hubs") == "/dvmdb/adom/X/group/hubs/object member"
    assert v76.device_add_url() == "/dvm/cmd/add/device"
    assert v76.device_delete_url() == "/dvm/cmd/del/device"


# ---------- model_device_extra_fields (THE 7.6 DIVERGENCE) ----------


def test_model_device_extra_fields_empty_on_legacy(v72: FMG72Adapter, v74: FMG74Adapter) -> None:
    """7.2/7.4 infer ``os_type`` from platform — no extra fields needed."""
    assert v72.model_device_extra_fields() == {}
    assert v74.model_device_extra_fields() == {}


def test_model_device_extra_fields_includes_os_type_on_76(
    v76: FMG76Adapter,
) -> None:
    """7.6 rejects /dvm/cmd/add/device without ``os_type: fos``."""
    assert v76.model_device_extra_fields() == {"os_type": "fos"}


# ---------- CLI templates ----------


def test_cli_template_urls(v76: FMG76Adapter) -> None:
    assert v76.cli_template_collection_url("X") == "/pm/config/adom/X/obj/cli/template"
    assert v76.cli_template_url("X", "t") == "/pm/config/adom/X/obj/cli/template/t"
    assert v76.cli_template_group_collection_url("X") == "/pm/config/adom/X/obj/cli/template-group"
    assert v76.cli_template_group_url("X", "g") == "/pm/config/adom/X/obj/cli/template-group/g"
    assert (
        v76.cli_template_group_scope_url("X", "g")
        == "/pm/config/adom/X/obj/cli/template-group/g/scope member"
    )


# ---------- dynamic variables (7.4/7.2 vs 7.6 — THE BIG DIVERGENCE) ----------


def test_dynamic_variable_urls_legacy_namespace(v72: FMG72Adapter, v74: FMG74Adapter) -> None:
    """7.2/7.4 use ``obj/dynamic/variable``."""
    for adapter in (v72, v74):
        assert (
            adapter.dynamic_variable_collection_url("X")
            == "/pm/config/adom/X/obj/dynamic/variable"
        )
        assert (
            adapter.dynamic_variable_url("X", "INET1_ip")
            == "/pm/config/adom/X/obj/dynamic/variable/INET1_ip"
        )
        assert (
            adapter.dynamic_variable_mapping_url("X", "INET1_ip")
            == "/pm/config/adom/X/obj/dynamic/variable/INET1_ip/dynamic_mapping"
        )


def test_dynamic_variable_urls_renamed_on_76(v76: FMG76Adapter) -> None:
    """7.6 moved variables to ``obj/fmg/variable``."""
    assert v76.dynamic_variable_collection_url("X") == "/pm/config/adom/X/obj/fmg/variable"
    assert (
        v76.dynamic_variable_url("X", "INET1_ip") == "/pm/config/adom/X/obj/fmg/variable/INET1_ip"
    )
    assert (
        v76.dynamic_variable_mapping_url("X", "INET1_ip")
        == "/pm/config/adom/X/obj/fmg/variable/INET1_ip/dynamic_mapping"
    )


# ---------- policy / blueprints / tmplgrp / install / scripts ----------


def test_policy_blueprint_tmplgrp_install_urls(v76: FMG76Adapter) -> None:
    assert v76.policy_package_url("X") == "/pm/pkg/adom/X"
    assert v76.policy_package_member_url("X", "p") == "/pm/pkg/adom/X/p/scope member"
    assert v76.policy_package_firewall_url("X", "p") == "/pm/config/adom/X/pkg/p/firewall/policy"
    assert v76.blueprint_collection_url("X") == "/pm/config/adom/X/obj/fmg/device/blueprint"
    assert v76.blueprint_url("X", "bp") == "/pm/config/adom/X/obj/fmg/device/blueprint/bp"
    assert v76.provisioning_tmplgrp_collection_url("X") == "/pm/tmplgrp/adom/X"
    assert v76.provisioning_tmplgrp_url("X", "g") == "/pm/tmplgrp/adom/X/g"
    assert v76.provisioning_tmplgrp_scope_url("X", "g") == "/pm/tmplgrp/adom/X/g/scope member"
    assert v76.install_device_url() == "/securityconsole/install/device"
    assert v76.install_package_url() == "/securityconsole/install/package"
    assert v76.install_preview_url() == "/securityconsole/install/preview"


def test_provisioning_template_collection_url_for_each_slug(
    v76: FMG76Adapter,
) -> None:
    for slug in ("devprof", "wanprof", "tmplgrp", "crprof"):
        assert v76.provisioning_template_collection_url("X", slug) == f"/pm/{slug}/adom/X"


def test_script_urls(v76: FMG76Adapter) -> None:
    assert v76.script_collection_url("X") == "/dvmdb/adom/X/script"
    assert v76.script_execute_url("X") == "/dvmdb/adom/X/script/execute"
