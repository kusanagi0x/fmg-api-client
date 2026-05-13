"""``ProvisioningTemplateManager`` — devprof / wanprof / tmplgrp / crprof.

FMG 7.6 puts these provisioning templates under ``/pm/<slug>/adom/<X>``,
each with the body shape ``{name, type: <slug>, …}``. The slug is the
type identifier the FMG demands in the payload — ``"devprof"`` for
system / device profiles, ``"wanprof"`` for WAN/SDWAN, ``"tmplgrp"``
for template groups, ``"crprof"`` for certificate profiles.

Single manager class parameterised by slug, since the URL pattern and
payload are identical across types.
"""

from __future__ import annotations

from typing import Any

from fmg_api_client.core.exceptions import NotFoundError
from fmg_api_client.managers.base import ManagerBase
from fmg_api_client.managers.meta_objects import _to_dict_or_none, _to_list


class ProvisioningTemplateManager(ManagerBase):
    """CRUD over ``/pm/<slug>/adom/<X>`` for one of: devprof, wanprof, tmplgrp, crprof."""

    def __init__(
        self,
        client: Any,
        adom: str,
        *,
        adapter: Any,
        slug: str,
    ) -> None:
        super().__init__(client, adom, adapter=adapter)
        self._slug = slug

    @property
    def slug(self) -> str:
        return self._slug

    def _coll_url(self) -> str:
        return self._adapter.provisioning_template_collection_url(self._adom, self._slug)

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
        """Idempotent ``set``. ``payload`` must include ``name``.

        FMG 7.6 also requires ``type: <slug>`` inside the payload — this
        method injects it if missing so callers don't have to remember.
        """
        name = payload["name"]
        body = dict(payload)
        body.setdefault("type", self._slug)
        return await self._client.set(self._item_url(name), body)

    async def delete(self, name: str) -> Any:
        return await self._client.delete(self._item_url(name))


__all__ = ["ProvisioningTemplateManager"]
