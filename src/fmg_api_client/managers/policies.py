"""``PolicyPackageManager`` — policy packages and firewall rules.

A policy package owns a list of firewall policies. The FMG endpoints
are split: package metadata (``/pm/pkg/adom/<X>/<pkg>``) and rule list
(``/pm/config/adom/<X>/pkg/<pkg>/firewall/policy``). This manager
exposes both behind a small API.

Rules are upserted by ``policyid``. Caller is responsible for assigning
unique ids — FMG does NOT auto-generate them on ``set``.
"""

from __future__ import annotations

import logging
from typing import Any

from fmg_api_client.core.exceptions import NotFoundError
from fmg_api_client.managers.base import ManagerBase
from fmg_api_client.managers.meta_objects import _to_dict_or_none, _to_list

logger = logging.getLogger(__name__)


class PolicyPackageManager(ManagerBase):
    """Manages policy packages and their firewall policies."""

    # ---- package CRUD ----

    async def list_all(self) -> list[dict[str, Any]]:
        url = self._adapter.policy_package_url(self._adom)
        return _to_list(await self._client.get(url))

    async def get(self, name: str) -> dict[str, Any] | None:
        url = f"{self._adapter.policy_package_url(self._adom)}/{name}"
        try:
            return _to_dict_or_none(await self._client.get(url))
        except NotFoundError:
            return None

    async def upsert(self, payload: dict[str, Any]) -> Any:
        """Idempotent set of a policy package. ``payload`` must include ``name``."""
        url = f"{self._adapter.policy_package_url(self._adom)}/{payload['name']}"
        return await self._client.set(url, payload)

    async def delete(self, name: str) -> Any:
        url = f"{self._adapter.policy_package_url(self._adom)}/{name}"
        return await self._client.delete(url)

    # ---- scope members (which device groups the package binds to) ----

    async def list_scope_members(self, package_name: str) -> list[dict[str, Any]]:
        url = self._adapter.policy_package_member_url(self._adom, package_name)
        result = await self._client.get(url)
        if isinstance(result, list):
            return [item for item in result if isinstance(item, dict)]
        if isinstance(result, dict):
            return [result]
        return []

    async def add_scope_member(
        self, package_name: str, device_group: str, *, vdom: str = "root"
    ) -> Any:
        url = self._adapter.policy_package_member_url(self._adom, package_name)
        return await self._client.add(url, {"name": device_group, "vdom": vdom})

    # ---- rules ----

    async def list_rules(self, package_name: str) -> list[dict[str, Any]]:
        url = self._adapter.policy_package_firewall_url(self._adom, package_name)
        return _to_list(await self._client.get(url))

    async def upsert_rule(self, package_name: str, rule: dict[str, Any]) -> Any:
        """Upsert a firewall rule (identified by ``rule["policyid"]``)."""
        policyid = rule["policyid"]
        base = self._adapter.policy_package_firewall_url(self._adom, package_name)
        url = f"{base}/{policyid}"
        return await self._client.set(url, rule)

    async def delete_rule(self, package_name: str, policyid: int) -> Any:
        base = self._adapter.policy_package_firewall_url(self._adom, package_name)
        url = f"{base}/{policyid}"
        return await self._client.delete(url)


__all__ = ["PolicyPackageManager"]
