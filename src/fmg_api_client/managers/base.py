"""``ManagerBase`` — common DI shape for every FMG domain manager.

Every concrete manager (DeviceManager, MetafieldManager, …) inherits
from this so the constructor signature is uniform and predictable:
``(client, adom, *, adapter)``. ``adapter`` is keyword-only and required
— there is no default. A silent default to one specific FMG version is
a major bug source the day the same code base talks to a newer FMG, so
the explicit form is mandatory.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fmg_api_client.core.client import FMGClientProtocol
    from fmg_api_client.versions.base import VersionAdapter


class ManagerBase:
    """Holds the client + ADOM + adapter for a manager."""

    def __init__(
        self,
        client: FMGClientProtocol,
        adom: str,
        *,
        adapter: VersionAdapter,
    ) -> None:
        self._client = client
        self._adom = adom
        self._adapter = adapter

    @property
    def adom(self) -> str:
        """ADOM this manager operates on."""
        return self._adom

    @property
    def adapter(self) -> VersionAdapter:
        """The :class:`VersionAdapter` carrying URL + payload shape."""
        return self._adapter


__all__ = ["ManagerBase"]
