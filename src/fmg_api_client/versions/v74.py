"""``FMG74Adapter`` — strategy for FortiManager 7.4.x.

Inherits all defaults from :class:`BaseAdapter` (which encodes the 7.4
shape: ``obj/dynamic/variable``, ``local-value`` field name, …). Override
points are limited to the version label.
"""

from __future__ import annotations

from fmg_api_client.versions.base import BaseAdapter
from fmg_api_client.versions.registry import AdapterRegistry


@AdapterRegistry.register("7.4")
class FMG74Adapter(BaseAdapter):
    """Adapter for FortiManager 7.4.x."""

    @property
    def version_label(self) -> str:
        return "7.4"


__all__ = ["FMG74Adapter"]
