"""Tests for ``detect_version``."""

from __future__ import annotations

from typing import Any

import pytest

from fmg_api_client import (
    FMG74Adapter,
    FMG76Adapter,
    VersionError,
    detect_version,
)


class _FakeClient:
    """Minimal client returning a canned ``/sys/status`` response."""

    def __init__(self, status: dict[str, Any]) -> None:
        self._status = status
        self.calls: list[str] = []

    async def get(self, url: str, **params: Any) -> Any:
        del params
        self.calls.append(url)
        return self._status


@pytest.mark.asyncio
async def test_detect_version_76() -> None:
    client = _FakeClient({"Version": "v7.6.5-build1234", "Hostname": "fmg"})
    adapter = await detect_version(client)  # type: ignore[arg-type]
    assert isinstance(adapter, FMG76Adapter)
    assert client.calls == ["/sys/status"]


@pytest.mark.asyncio
async def test_detect_version_74() -> None:
    client = _FakeClient({"Version": "v7.4.3-build4567", "Hostname": "fmg"})
    adapter = await detect_version(client)  # type: ignore[arg-type]
    assert isinstance(adapter, FMG74Adapter)


@pytest.mark.asyncio
async def test_detect_version_handles_no_v_prefix() -> None:
    client = _FakeClient({"Version": "7.6.0", "Hostname": "fmg"})
    adapter = await detect_version(client)  # type: ignore[arg-type]
    assert adapter.version_label == "7.6"


@pytest.mark.asyncio
async def test_detect_version_unsupported_raises() -> None:
    """A version we don't have an adapter for must fail loudly."""
    client = _FakeClient({"Version": "v6.4.10", "Hostname": "fmg"})
    with pytest.raises(VersionError):
        await detect_version(client)  # type: ignore[arg-type]
