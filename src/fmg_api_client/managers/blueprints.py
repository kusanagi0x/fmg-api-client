"""``BlueprintManager`` — device blueprints (``obj/fmg/device/blueprint``).

Blueprints bundle template-group + policy-package assignments to apply
when a model device is registered. Idempotent ``set``-style upserts.
"""

from __future__ import annotations

from typing import Any

from fmg_api_client.core.exceptions import NotFoundError
from fmg_api_client.managers.base import ManagerBase
from fmg_api_client.managers.meta_objects import _to_dict_or_none, _to_list


class BlueprintManager(ManagerBase):
    """Manages ``obj/fmg/device/blueprint`` records."""

    async def list_all(self) -> list[dict[str, Any]]:
        url = self._adapter.blueprint_collection_url(self._adom)
        return _to_list(await self._client.get(url))

    async def get(self, name: str) -> dict[str, Any] | None:
        url = self._adapter.blueprint_url(self._adom, name)
        try:
            return _to_dict_or_none(await self._client.get(url))
        except NotFoundError:
            return None

    async def upsert(self, payload: dict[str, Any]) -> Any:
        """Idempotent ``set``. ``payload`` must include ``name``."""
        url = self._adapter.blueprint_url(self._adom, payload["name"])
        return await self._client.set(url, payload)

    async def delete(self, name: str) -> Any:
        url = self._adapter.blueprint_url(self._adom, name)
        return await self._client.delete(url)


__all__ = ["BlueprintManager"]
