"""Per-version payload builders.

These tests guard against a real-world FMG breakage: FMG 7.6 renamed the
``local-value`` field in ``dynamic_mapping`` payloads to ``value``. Any
client that hardcodes the 7.4 spelling for both versions silently writes
broken meta-variables on 7.6. The tests below assert each adapter's
payload shape explicitly per version, so the divergence cannot be
silently regressed.
"""

from __future__ import annotations

from fmg_api_client import FMG72Adapter, FMG74Adapter, FMG76Adapter

# ---------- dynamic_variable_create_payload ----------


def test_create_payload_uses_default_value_on_legacy() -> None:
    for adapter in (FMG72Adapter(), FMG74Adapter()):
        payload = adapter.dynamic_variable_create_payload("INET1_ip", "203.0.113.1")
        assert payload == {"name": "INET1_ip", "default-value": "203.0.113.1"}


def test_create_payload_uses_value_on_76() -> None:
    payload = FMG76Adapter().dynamic_variable_create_payload("INET1_ip", "203.0.113.1")
    assert payload == {"name": "INET1_ip", "value": "203.0.113.1"}


# ---------- dynamic_variable_mapping_payload (THE FIX) ----------


def test_mapping_payload_uses_local_value_on_legacy() -> None:
    """7.4 and 7.2 keep the legacy ``local-value`` field name."""
    for adapter in (FMG72Adapter(), FMG74Adapter()):
        payload = adapter.dynamic_variable_mapping_payload("HQ-MAIN", "198.51.100.1")
        assert payload == {
            "_scope": [{"name": "HQ-MAIN", "vdom": "root"}],
            "local-value": "198.51.100.1",
        }


def test_mapping_payload_uses_value_on_76() -> None:
    """7.6 renamed ``local-value`` to ``value`` — confirm the rename is applied."""
    payload = FMG76Adapter().dynamic_variable_mapping_payload("HQ-MAIN", "198.51.100.1")
    assert payload == {
        "_scope": [{"name": "HQ-MAIN", "vdom": "root"}],
        "value": "198.51.100.1",
    }


def test_mapping_payload_respects_custom_vdom() -> None:
    payload = FMG76Adapter().dynamic_variable_mapping_payload("HQ-MAIN", "x", vdom="root-tenant-1")
    assert payload["_scope"] == [{"name": "HQ-MAIN", "vdom": "root-tenant-1"}]


# ---------- install payloads ----------


def test_install_device_payload_shape() -> None:
    payload = FMG76Adapter().install_device_payload("X", "fgt1")
    assert payload == {
        "adom": "X",
        "scope": [{"name": "fgt1", "vdom": "root"}],
        "flags": ["none"],
    }


def test_install_package_payload_shape() -> None:
    payload = FMG76Adapter().install_package_payload("X", "p1", "fgt1")
    assert payload == {
        "adom": "X",
        "pkg": "p1",
        "scope": [{"name": "fgt1", "vdom": "root"}],
        "flags": ["none"],
    }


def test_install_preview_payload_shape() -> None:
    payload = FMG76Adapter().install_preview_payload("X", "fgt1")
    assert payload == {
        "adom": "X",
        "device": [{"name": "fgt1", "vdom": "root"}],
        "flags": ["json"],
    }


# ---------- version_label ----------


def test_version_labels() -> None:
    assert FMG72Adapter().version_label == "7.2"
    assert FMG74Adapter().version_label == "7.4"
    assert FMG76Adapter().version_label == "7.6"
