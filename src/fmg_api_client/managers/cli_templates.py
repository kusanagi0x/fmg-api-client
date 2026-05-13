"""CLI template + group managers.

CLI templates are Jinja2/CLI scripts that FMG expands per-device using
meta-variable bindings. The body is the ``script`` field; the FMG GUI
uses it verbatim.
"""

from __future__ import annotations

import logging
from typing import Any

from fmg_api_client.core.exceptions import NotFoundError
from fmg_api_client.managers.base import ManagerBase
from fmg_api_client.managers.meta_objects import _to_dict_or_none, _to_list

logger = logging.getLogger(__name__)


class CLITemplateManager(ManagerBase):
    """Manages ``obj/cli/template``."""

    async def list_all(self) -> list[dict[str, Any]]:
        url = self._adapter.cli_template_collection_url(self._adom)
        return _to_list(await self._client.get(url))

    async def get(self, name: str) -> dict[str, Any] | None:
        url = self._adapter.cli_template_url(self._adom, name)
        try:
            return _to_dict_or_none(await self._client.get(url))
        except NotFoundError:
            return None

    async def upsert(self, payload: dict[str, Any]) -> Any:
        """Idempotent ``set``. ``payload`` must include ``name`` and may include ``script``."""
        url = self._adapter.cli_template_url(self._adom, payload["name"])
        return await self._client.set(url, payload)

    async def delete(self, name: str) -> Any:
        url = self._adapter.cli_template_url(self._adom, name)
        return await self._client.delete(url)


class CLITemplateGroupManager(ManagerBase):
    """Manages ``obj/cli/template-group`` (with ``scope member``)."""

    async def list_all(self) -> list[dict[str, Any]]:
        url = self._adapter.cli_template_group_collection_url(self._adom)
        return _to_list(await self._client.get(url))

    async def get(self, name: str) -> dict[str, Any] | None:
        url = self._adapter.cli_template_group_url(self._adom, name)
        try:
            return _to_dict_or_none(await self._client.get(url))
        except NotFoundError:
            return None

    async def upsert(self, payload: dict[str, Any]) -> Any:
        url = self._adapter.cli_template_group_url(self._adom, payload["name"])
        return await self._client.set(url, payload)

    async def assign_to_device_group(
        self, group_name: str, device_group: str, *, vdom: str = "root"
    ) -> Any:
        """Add a device group as a scope member of a CLI template group."""
        url = self._adapter.cli_template_group_scope_url(self._adom, group_name)
        return await self._client.add(url, {"name": device_group, "vdom": vdom})

    async def delete(self, name: str) -> Any:
        url = self._adapter.cli_template_group_url(self._adom, name)
        return await self._client.delete(url)


__all__ = ["CLITemplateGroupManager", "CLITemplateManager"]
