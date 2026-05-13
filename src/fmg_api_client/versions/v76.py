"""``FMG76Adapter`` — strategy for FortiManager 7.6.x.

Diverges from 7.4 in two main areas, verified empirically:

1. **ADOM-level dynamic variables** moved from ``obj/dynamic/variable``
   to ``obj/fmg/variable``. The default-value field was renamed from
   ``default-value`` to ``value``. Per-device mapping under
   ``dynamic_mapping`` ALSO renamed ``local-value`` → ``value``
   (verified empirically against FMG 7.6.5).

2. **Model device registration** (``/dvm/cmd/add/device``) requires
   ``os_type: "fos"`` or returns ``-20024 "Unsupported device os type"``.
   7.4 inferred it from ``platform_str`` and tolerated its absence.

Everything else inherits from :class:`BaseAdapter`.
"""

from __future__ import annotations

from typing import Any

from fmg_api_client.versions.base import BaseAdapter
from fmg_api_client.versions.registry import AdapterRegistry


@AdapterRegistry.register("7.6")
class FMG76Adapter(BaseAdapter):
    """Adapter for FortiManager 7.6.x."""

    @property
    def version_label(self) -> str:
        return "7.6"

    # Model-device registration -----------------------------------------

    def model_device_extra_fields(self) -> dict[str, Any]:
        return {"os_type": "fos"}

    # Dynamic variables -------------------------------------------------

    def dynamic_variable_collection_url(self, adom: str) -> str:
        return f"/pm/config/adom/{adom}/obj/fmg/variable"

    def dynamic_variable_url(self, adom: str, name: str) -> str:
        return f"/pm/config/adom/{adom}/obj/fmg/variable/{name}"

    def dynamic_variable_mapping_url(self, adom: str, name: str) -> str:
        return f"/pm/config/adom/{adom}/obj/fmg/variable/{name}/dynamic_mapping"

    def dynamic_variable_create_payload(
        self, name: str, default_value: str = ""
    ) -> dict[str, Any]:
        return {"name": name, "value": default_value}

    def dynamic_variable_mapping_payload(
        self, device: str, value: str, *, vdom: str = "root"
    ) -> dict[str, Any]:
        return {
            "_scope": [{"name": device, "vdom": vdom}],
            "value": value,
        }


__all__ = ["FMG76Adapter"]
