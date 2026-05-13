"""``FMG72Adapter`` — strategy for FortiManager 7.2.x.

7.2 predates the dynamic-variable namespace move that 7.6 did, so this
adapter inherits the legacy 7.4 shape from :class:`BaseAdapter`:

- ``obj/dynamic/variable`` (not ``obj/fmg/variable``).
- ``default-value`` for variable definitions.
- ``local-value`` for ``dynamic_mapping`` per-device overrides.
- No ``os_type`` requirement on model-device registration.

If empirical probing against an FMG 7.2 lab uncovers a divergence we
have not seen in 7.4, override the affected method here and add a
golden fixture under ``tests/fixtures/responses/v72/``. Until then,
behaviour is identical to 7.4 by inheritance.
"""

from __future__ import annotations

from fmg_api_client.versions.base import BaseAdapter
from fmg_api_client.versions.registry import AdapterRegistry


@AdapterRegistry.register("7.2")
class FMG72Adapter(BaseAdapter):
    """Adapter for FortiManager 7.2.x (assumed 7.4-shape, unverified)."""

    @property
    def version_label(self) -> str:
        return "7.2"


__all__ = ["FMG72Adapter"]
