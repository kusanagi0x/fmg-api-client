"""``MetafieldManager`` — per-device meta-variable bindings on FMG.

Design notes (each one is here because we got it wrong before):

1. Signature is ``set_per_device(device_name, variables: dict)``. The
   alternative shape ``set_per_device(var, dev, value)`` is unworkable
   because real-world callers set several variables per device in one
   transaction.
2. ``adapter`` is required (no default). A silent default to a 7.4-shape
   adapter against a 7.6 FMG would build ``obj/dynamic/variable`` URLs
   that return ``-3`` — making it explicit forces the caller to be
   correct.
3. The 7.6 payload field rename (``local-value`` → ``value``) lives in
   :meth:`VersionAdapter.dynamic_variable_mapping_payload`, so this
   manager stays version-agnostic.
4. URL form: writes target the **collection** URL (``…/dynamic_mapping``)
   with a ``_scope`` payload — FMG matches by ``_scope`` and ``set`` is
   an idempotent upsert. Suffixed URLs identify entries by ``oid`` (int),
   not device name; passing a device name in the suffix returns ``-3``.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from fmg_api_client.managers.base import ManagerBase

if TYPE_CHECKING:
    from collections.abc import Iterable

logger = logging.getLogger(__name__)


class MetafieldManager(ManagerBase):
    """Manages ADOM-level dynamic variables and per-device overrides."""

    async def create_if_missing(self, variable_name: str, default_value: str = "") -> Any:
        """Create (upsert) a variable definition. Idempotent.

        URL + payload come from the adapter, so the 7.4 vs 7.6 diff
        (``default-value`` vs ``value``, different namespace) is invisible
        to callers.
        """
        url = self._adapter.dynamic_variable_collection_url(self._adom)
        data = self._adapter.dynamic_variable_create_payload(variable_name, default_value)
        result = await self._client.set(url, data)
        logger.debug("Ensured metafield: %s", variable_name)
        return result

    async def ensure_variables(self, variable_names: Iterable[str]) -> None:
        """Create the listed variables in bulk if not already present.

        FMG 7.6's CLI template parser rejects ``$(var)`` references with
        ``-9001`` unless the dynamic variable exists as an ADOM object.
        Call this BEFORE writing per-device mappings or uploading CLI
        templates that reference the variables.
        """
        names = sorted(set(variable_names))
        for name in names:
            await self.create_if_missing(name)
        logger.info("Ensured %d ADOM-level dynamic variables", len(names))

    async def set_per_device(
        self,
        device_name: str,
        variables: dict[str, str],
        *,
        vdom: str = "root",
    ) -> list[Any]:
        """Set per-device overrides for ``device_name``.

        Args:
            device_name: FMG device name (must exist in the ADOM device
                list — set via :class:`DeviceManager` first, or the
                writes return -3 "Object does not exist").
            variables: ``{var_name: value}``. The variable definitions
                themselves must already exist (via :meth:`ensure_variables`).
            vdom: VDOM to scope the override to (default ``"root"``).

        Returns:
            One result per variable in ``variables`` insertion order.
        """
        results: list[Any] = []
        for var_name, var_value in variables.items():
            url = self._adapter.dynamic_variable_mapping_url(self._adom, var_name)
            payload = self._adapter.dynamic_variable_mapping_payload(
                device_name, var_value, vdom=vdom
            )
            result = await self._client.set(url, payload)
            results.append(result)
        logger.info(
            "Set %d metafields on %s: %s",
            len(variables),
            device_name,
            ", ".join(variables),
        )
        return results

    async def get_variable(self, variable_name: str) -> Any:
        """Read a variable definition (and its dynamic_mapping array)."""
        url = self._adapter.dynamic_variable_url(self._adom, variable_name)
        return await self._client.get(url)


__all__ = ["MetafieldManager"]
