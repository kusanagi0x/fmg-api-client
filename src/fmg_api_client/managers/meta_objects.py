"""Address and service object/group managers.

These are the firewall-object building blocks (``obj/firewall/address``,
``obj/firewall/addrgrp``, ``obj/firewall/service/custom``,
``obj/firewall/service/group``). Idempotent ``set`` upserts; payloads
are pass-through dicts (the FMG schema has dozens of fields per object,
and we don't want to model every shape — callers pass what they have).

URL building is hard-coded here rather than going through the adapter
because the firewall object endpoints have not changed shape between
7.4 and 7.6 (verified). If they do diverge in a future version, lift
the URL builders into :class:`VersionAdapter`.
"""

from __future__ import annotations

from typing import Any

from fmg_api_client.core.exceptions import NotFoundError
from fmg_api_client.managers.base import ManagerBase


def _to_list(result: object) -> list[dict[str, Any]]:
    """Coerce an FMG ``Any`` GET response into a typed list-of-dict."""
    if isinstance(result, list):
        return [item for item in result if isinstance(item, dict)]
    return []


def _to_dict_or_none(result: object) -> dict[str, Any] | None:
    """Coerce an FMG ``Any`` GET response into a dict or ``None``."""
    return result if isinstance(result, dict) else None


class _ObjectManagerBase(ManagerBase):
    """Common CRUD shape for firewall object managers (address / service)."""

    _COLL_PATH: str = ""

    def _coll_url(self) -> str:
        return f"/pm/config/adom/{self._adom}/{self._COLL_PATH}"

    def _item_url(self, name: str) -> str:
        return f"{self._coll_url()}/{name}"

    async def list_all(self) -> list[dict[str, Any]]:
        return _to_list(await self._client.get(self._coll_url()))

    async def get(self, name: str) -> dict[str, Any] | None:
        try:
            return _to_dict_or_none(await self._client.get(self._item_url(name)))
        except NotFoundError:
            return None

    async def upsert(self, payload: dict[str, Any]) -> Any:
        """Idempotent ``set``. ``payload`` must include ``name``."""
        return await self._client.set(self._item_url(payload["name"]), payload)

    async def delete(self, name: str) -> Any:
        return await self._client.delete(self._item_url(name))


class AddressManager(_ObjectManagerBase):
    """Manages ``obj/firewall/address``."""

    _COLL_PATH = "obj/firewall/address"


class AddressGroupManager(_ObjectManagerBase):
    """Manages ``obj/firewall/addrgrp``."""

    _COLL_PATH = "obj/firewall/addrgrp"


class ServiceManager(_ObjectManagerBase):
    """Manages ``obj/firewall/service/custom``."""

    _COLL_PATH = "obj/firewall/service/custom"


class ServiceGroupManager(_ObjectManagerBase):
    """Manages ``obj/firewall/service/group``."""

    _COLL_PATH = "obj/firewall/service/group"


__all__ = [
    "AddressGroupManager",
    "AddressManager",
    "ServiceGroupManager",
    "ServiceManager",
]
