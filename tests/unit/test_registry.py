"""Tests for ``AdapterRegistry``.

Open/Closed: a new version key can be registered, retrieved, and listed
without touching the framework. Duplicate registration fails loudly.
"""

from __future__ import annotations

import pytest

from fmg_api_client import (
    AdapterRegistry,
    BaseAdapter,
    FMG72Adapter,
    FMG74Adapter,
    FMG76Adapter,
    VersionError,
)


def test_default_versions_registered() -> None:
    """7.2, 7.4, 7.6 are auto-registered via ``versions.__init__`` imports."""
    available = AdapterRegistry.available()
    assert "7.2" in available
    assert "7.4" in available
    assert "7.6" in available


def test_get_returns_correct_adapter_class() -> None:
    assert isinstance(AdapterRegistry.get("7.2"), FMG72Adapter)
    assert isinstance(AdapterRegistry.get("7.4"), FMG74Adapter)
    assert isinstance(AdapterRegistry.get("7.6"), FMG76Adapter)


def test_get_returns_fresh_instance_each_call() -> None:
    """Adapters are stateless, but instances should not be shared either."""
    a = AdapterRegistry.get("7.6")
    b = AdapterRegistry.get("7.6")
    assert a is not b
    assert isinstance(a, FMG76Adapter)


def test_get_normalizes_patch_version() -> None:
    """``"7.6.5"`` resolves to the 7.6 adapter (patch ignored)."""
    adapter = AdapterRegistry.get("7.6.5")
    assert adapter.version_label == "7.6"


def test_get_normalizes_v_prefix_and_build_suffix() -> None:
    """FMG-style ``"v7.6.5-build1234"`` is accepted."""
    adapter = AdapterRegistry.get("v7.6.5-build1234")
    assert adapter.version_label == "7.6"


def test_get_unknown_version_raises_version_error() -> None:
    with pytest.raises(VersionError) as ei:
        AdapterRegistry.get("7.0")
    msg = str(ei.value)
    assert "7.0" in msg
    # Lists what IS supported.
    assert "7.6" in msg


def test_register_duplicate_raises_value_error() -> None:
    """Registering twice for the same version is a programming error."""

    class _Dummy(BaseAdapter):
        @property
        def version_label(self) -> str:
            return "9.9"

    AdapterRegistry.register("9.9")(_Dummy)
    try:
        with pytest.raises(ValueError, match="already registered"):
            AdapterRegistry.register("9.9")(_Dummy)
    finally:
        # Cleanup so the registry stays consistent for other tests.
        del AdapterRegistry._registry["9.9"]


def test_register_returns_class_unchanged() -> None:
    """Decorator pattern: the class flows through untouched."""

    class _Dummy(BaseAdapter):
        @property
        def version_label(self) -> str:
            return "9.8"

    returned = AdapterRegistry.register("9.8")(_Dummy)
    try:
        assert returned is _Dummy
        # And the decorator made it findable.
        assert isinstance(AdapterRegistry.get("9.8"), _Dummy)
    finally:
        del AdapterRegistry._registry["9.8"]
