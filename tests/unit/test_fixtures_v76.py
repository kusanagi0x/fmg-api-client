"""Fixture-based tests against captured FMG 7.6.5 responses.

These tests load real JSON responses captured by
``scripts/capture_fixtures.py`` against a live FMG 7.6.5 lab and verify
that the managers + adapter parse them correctly. If Fortinet ships an
incompatible shape change in 7.8, these tests fail with a clear delta
between the captured fixture and what the manager expected.

Fixtures live in ``tests/fixtures/responses/v76/`` and are committed
(redacted of identifying data — see :func:`_redact`).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from fmg_api_client import (
    AddressManager,
    CLITemplateManager,
    FMG76Adapter,
    PolicyPackageManager,
    ServiceManager,
    SystemStatus,
)

_FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "responses" / "v76"


def _load(slug: str) -> dict[str, Any]:
    """Load a captured fixture by slug. Returns the parsed JSON dict."""
    path = _FIXTURES_DIR / f"{slug}.json"
    return json.loads(path.read_text(encoding="utf-8"))


class _ReplayClient:
    """Replays a single canned response per URL.

    Tests pre-load fixture data and the client returns the
    ``response`` field for matching ``get`` calls. Mismatched URLs raise
    so tests fail loud rather than silently passing.
    """

    def __init__(self, responses: dict[str, Any]) -> None:
        self._responses = responses
        self.calls: list[tuple[str, str, Any]] = []

    async def get(self, url: str, **params: Any) -> Any:
        del params
        self.calls.append(("get", url, None))
        if url not in self._responses:
            raise AssertionError(f"unexpected GET {url}")
        return self._responses[url]

    async def add(self, url: str, data: dict[str, Any]) -> Any:
        self.calls.append(("add", url, data))
        return None

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
        return None

    async def multiplex(self, requests: list[dict[str, Any]]) -> list[Any]:
        self.calls.append(("multiplex", "", requests))
        return [None] * len(requests)


# ---------- /sys/status ----------


def test_system_status_parses_real_fmg_response() -> None:
    fixture = _load("sys_status")
    status = SystemStatus.model_validate(fixture["response"])
    assert status.major_minor == "7.6"
    assert status.version.startswith("v7.6.5-build")
    assert status.serial_number  # present (redacted, but non-empty)
    assert status.hostname  # present


# ---------- collections fixtures ----------


@pytest.mark.asyncio
async def test_address_manager_parses_default_objects() -> None:
    """FMG ships ~18 default address objects (RFC1918, all, none, …)."""
    fixture = _load("address_objects_collection")
    client = _ReplayClient({fixture["url"]: fixture["response"]})
    mgr = AddressManager(client, "lab", adapter=FMG76Adapter())  # type: ignore[arg-type]

    items = await mgr.list_all()
    assert len(items) >= 10  # default Fortinet set
    names = {i["name"] for i in items if "name" in i}
    # Spot-check well-known FMG defaults.
    assert "all" in names
    assert "none" in names


@pytest.mark.asyncio
async def test_service_manager_parses_default_services() -> None:
    """FMG ships ~88 default service objects (HTTP, HTTPS, SSH, …)."""
    fixture = _load("service_objects_collection")
    client = _ReplayClient({fixture["url"]: fixture["response"]})
    mgr = ServiceManager(client, "lab", adapter=FMG76Adapter())  # type: ignore[arg-type]

    items = await mgr.list_all()
    assert len(items) >= 50
    names = {i["name"] for i in items if "name" in i}
    # Spot-check well-known FMG defaults.
    assert "HTTP" in names
    assert "HTTPS" in names
    assert "SSH" in names


@pytest.mark.asyncio
async def test_cli_template_manager_parses_collection() -> None:
    fixture = _load("cli_templates_collection")
    client = _ReplayClient({fixture["url"]: fixture["response"]})
    mgr = CLITemplateManager(  # type: ignore[arg-type]
        client, "lab", adapter=FMG76Adapter()
    )
    items = await mgr.list_all()
    assert len(items) >= 1
    # Every item should have a name.
    assert all(isinstance(i, dict) and "name" in i for i in items)


def test_device_groups_collection_shape_is_list_of_dicts() -> None:
    """``GET /dvmdb/adom/<X>/group`` returns a list of group dicts.

    The DeviceManager doesn't have a ``list_groups`` method (we use
    ``list_group_members(name)`` instead), so we just verify the
    collection-level shape we can rely on for future managers.
    """
    fixture = _load("device_groups_collection")
    response = fixture["response"]
    assert isinstance(response, list)
    assert all(isinstance(g, dict) and "name" in g for g in response)
    names = {g["name"] for g in response}
    assert "All_FortiGate" in names  # default group present in every ADOM


@pytest.mark.asyncio
async def test_policy_package_manager_parses_collection() -> None:
    fixture = _load("policy_packages_collection")
    client = _ReplayClient({fixture["url"]: fixture["response"]})
    mgr = PolicyPackageManager(  # type: ignore[arg-type]
        client, "lab", adapter=FMG76Adapter()
    )
    items = await mgr.list_all()
    assert len(items) >= 1


# ---------- dynamic_variable: THE CORE TEST ----------


@pytest.mark.asyncio
async def test_dynamic_variable_collection_parses_with_per_device_mappings() -> None:
    """Fixture from a live FMG with INET1_ip having 4 device mappings.

    Verifies the shape FMG 7.6 returns:
    ``{name, oid, value, type, dynamic_mapping: [{_scope, oid, value}]}``.
    Each mapping uses the **value** field (not the legacy ``local-value``).
    """
    fixture = _load("dynamic_variable_collection_76")
    response = fixture["response"]
    assert isinstance(response, list)

    # Find INET1_ip — it's the one with populated dynamic_mapping in our lab.
    inet1_ip = next((v for v in response if v.get("name") == "INET1_ip"), None)
    assert inet1_ip is not None, "INET1_ip should be in the fixture"
    mappings = inet1_ip.get("dynamic_mapping", []) or []
    # Expected: 4 per-device mappings (HQ-MAIN, HQ-DR, Branch-01, Branch-02).
    assert len(mappings) == 4
    for m in mappings:
        # FMG 7.6 uses ``value``, NOT the legacy 7.4 ``local-value``.
        assert "value" in m
        assert "local-value" not in m
        assert "_scope" in m
        assert isinstance(m["_scope"], list)
        assert m["_scope"][0]["vdom"] == "root"


# ---------- 7.4 namespace probe (negative on 7.6) ----------


def test_v74_namespace_returns_not_found_on_v76() -> None:
    """``obj/dynamic/variable`` (7.4 path) is gone on 7.6 — captured as evidence.

    This fixture is the empirical proof for ``versions/v76.py``: on 7.6
    the legacy 7.4 collection URL returns -3, so the adapter MUST point
    elsewhere (``obj/fmg/variable``).
    """
    path = _FIXTURES_DIR / "dynamic_variable_collection_74_on_76_error.json"
    if not path.exists():
        pytest.skip("negative-probe fixture not captured")
    err = json.loads(path.read_text(encoding="utf-8"))
    assert "Object does not exist" in err["error"] or "-3" in err["error"]


# ---------- coverage of payload + parser parity ----------


def test_metafield_payload_round_trip_against_fixture() -> None:
    """Adapter-built payload matches the shape FMG actually persists.

    Take a per-device mapping from the captured fixture, pretend our
    adapter produced it, and verify the round-trip. Catches any future
    drift between what we send and what FMG stores.
    """
    fixture = _load("dynamic_variable_collection_76")
    response = fixture["response"]
    inet1_ip = next(v for v in response if v["name"] == "INET1_ip")
    sample_mapping = inet1_ip["dynamic_mapping"][0]
    device_name = sample_mapping["_scope"][0]["name"]
    value = sample_mapping["value"]

    rebuilt = FMG76Adapter().dynamic_variable_mapping_payload(device_name, value)
    # Compare ignoring oid (FMG-assigned, not in our outgoing payload).
    expected_keys = {"_scope", "value"}
    assert set(rebuilt.keys()) == expected_keys
    assert rebuilt["_scope"] == sample_mapping["_scope"]
    assert rebuilt["value"] == sample_mapping["value"]
