"""``VersionAdapter`` — Strategy ABC + ``BaseAdapter`` defaults.

Per-FMG-version differences live in concrete subclasses
(:class:`FMG74Adapter`, :class:`FMG76Adapter`, …). The adapter exposes:

- **URL builders** for every endpoint a manager touches.
- **Payload builders** for the parts that diverge between versions
  (``dynamic_variable_create_payload``, ``dynamic_variable_mapping_payload``,
  ``model_device_extra_fields``, install payloads).

Adapters are pure (no I/O, no state) and safe to share across managers.

Scope deliberately excluded:

- SD-WAN overlay payloads (depend on SD-WAN domain models — those
  belong to a caller-side package; this one stays focused on the
  generic FMG JSON-RPC surface).
- Workflow-level orchestration (install ordering, rollback, drift
  detection) — same reason.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class VersionAdapter(ABC):
    """Strategy interface for version-specific FMG behaviour.

    Concrete subclasses implement :pyattr:`version_label` and may override
    any URL or payload hook. Most behaviour is inherited from
    :class:`BaseAdapter`, which provides defaults shared by 7.4 and 7.6.
    """

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def version_label(self) -> str:
        """Human-readable version label, e.g. ``"7.4"`` or ``"7.6"``."""

    # ------------------------------------------------------------------
    # Workspace URLs
    # ------------------------------------------------------------------

    @abstractmethod
    def workspace_lock_url(self, adom: str) -> str:
        """URL to acquire the workspace lock for ``adom``."""

    @abstractmethod
    def workspace_commit_url(self, adom: str) -> str:
        """URL to commit pending workspace changes on ``adom``."""

    @abstractmethod
    def workspace_unlock_url(self, adom: str) -> str:
        """URL to release the workspace lock on ``adom``."""

    @abstractmethod
    def workspace_lockinfo_url(self, adom: str) -> str:
        """URL to read who currently holds the workspace lock on ``adom``."""

    # ------------------------------------------------------------------
    # Device URLs / payload extras
    # ------------------------------------------------------------------

    @abstractmethod
    def device_url(self, adom: str, name: str) -> str:
        """URL to read/write a single device record in ``adom``."""

    @abstractmethod
    def device_group_url(self, adom: str, name: str) -> str:
        """URL to read/write a device group in ``adom``."""

    @abstractmethod
    def device_group_collection_url(self, adom: str) -> str:
        """URL of the device-group collection (used for ``add``)."""

    @abstractmethod
    def device_group_member_url(self, adom: str, group: str) -> str:
        """URL of a device group's ``object member`` collection."""

    @abstractmethod
    def device_add_url(self) -> str:
        """URL used for ``/dvm/cmd/add/device`` (model device registration)."""

    @abstractmethod
    def device_delete_url(self) -> str:
        """URL used for ``/dvm/cmd/del/device``."""

    @abstractmethod
    def model_device_extra_fields(self) -> dict[str, Any]:
        """Extra fields the FMG version requires in model-device payloads.

        7.6 demands ``{"os_type": "fos"}`` or returns ``-20024`` "Unsupported
        device os type"; 7.4 infers it from ``platform_str`` and accepts ``{}``.
        """

    # ------------------------------------------------------------------
    # CLI templates / template groups
    # ------------------------------------------------------------------

    @abstractmethod
    def cli_template_collection_url(self, adom: str) -> str:
        """Collection URL for CLI templates in ``adom``."""

    @abstractmethod
    def cli_template_url(self, adom: str, name: str) -> str:
        """URL of a single CLI template."""

    @abstractmethod
    def cli_template_group_collection_url(self, adom: str) -> str:
        """Collection URL for CLI template groups in ``adom``."""

    @abstractmethod
    def cli_template_group_url(self, adom: str, name: str) -> str:
        """URL of a single CLI template group."""

    @abstractmethod
    def cli_template_group_scope_url(self, adom: str, group: str) -> str:
        """URL of a CLI template group's ``scope member`` collection."""

    # ------------------------------------------------------------------
    # Scripts
    # ------------------------------------------------------------------

    @abstractmethod
    def script_collection_url(self, adom: str) -> str:
        """Collection URL for scripts in ``adom``."""

    @abstractmethod
    def script_execute_url(self, adom: str) -> str:
        """URL to execute a script in ``adom``."""

    # ------------------------------------------------------------------
    # Dynamic variables (a.k.a. meta-variables)
    # ------------------------------------------------------------------

    @abstractmethod
    def dynamic_variable_collection_url(self, adom: str) -> str:
        """Collection URL for ADOM-level dynamic variables."""

    @abstractmethod
    def dynamic_variable_url(self, adom: str, name: str) -> str:
        """URL of a single dynamic variable definition."""

    @abstractmethod
    def dynamic_variable_mapping_url(self, adom: str, name: str) -> str:
        """URL of the per-device ``dynamic_mapping`` collection for a variable."""

    @abstractmethod
    def dynamic_variable_create_payload(
        self, name: str, default_value: str = ""
    ) -> dict[str, Any]:
        """Payload to create a variable definition.

        7.4 uses ``default-value``; 7.6 renamed it to ``value`` and moved
        the URL to ``obj/fmg/variable``.
        """

    @abstractmethod
    def dynamic_variable_mapping_payload(
        self, device: str, value: str, *, vdom: str = "root"
    ) -> dict[str, Any]:
        """Payload to upsert a per-device variable override.

        7.4 uses ``local-value``; 7.6 renamed it to ``value`` (verified
        empirically against FMG 7.6.5). The upsert is written to
        :meth:`dynamic_variable_mapping_url` (collection, no per-device
        suffix); FMG matches existing entries by ``_scope``.
        """

    # ------------------------------------------------------------------
    # Provisioning templates (devprof / wanprof / tmplgrp / crprof)
    # ------------------------------------------------------------------

    @abstractmethod
    def provisioning_template_collection_url(self, adom: str, slug: str) -> str:
        """URL of the per-type provisioning-template collection.

        ``slug`` is one of ``devprof``, ``wanprof``, ``crprof``, ``tmplgrp``.
        Pattern: ``/pm/<slug>/adom/<adom>``.
        """

    # ------------------------------------------------------------------
    # Policy packages
    # ------------------------------------------------------------------

    @abstractmethod
    def policy_package_url(self, adom: str) -> str:
        """Collection URL for policy packages in ``adom``."""

    @abstractmethod
    def policy_package_member_url(self, adom: str, pkg: str) -> str:
        """URL of a policy package's ``scope member`` collection."""

    @abstractmethod
    def policy_package_firewall_url(self, adom: str, pkg: str) -> str:
        """URL of a policy package's ``firewall/policy`` collection."""

    # ------------------------------------------------------------------
    # Blueprints
    # ------------------------------------------------------------------

    @abstractmethod
    def blueprint_collection_url(self, adom: str) -> str:
        """Collection URL for device blueprints in ``adom``."""

    @abstractmethod
    def blueprint_url(self, adom: str, name: str) -> str:
        """URL of a specific device blueprint."""

    # ------------------------------------------------------------------
    # Provisioning Template Groups (tmplgrp)
    # ------------------------------------------------------------------

    @abstractmethod
    def provisioning_tmplgrp_collection_url(self, adom: str) -> str:
        """Collection URL for Provisioning Template Groups in ``adom``."""

    @abstractmethod
    def provisioning_tmplgrp_url(self, adom: str, name: str) -> str:
        """URL of a specific Provisioning Template Group."""

    @abstractmethod
    def provisioning_tmplgrp_scope_url(self, adom: str, name: str) -> str:
        """URL of a PTG's ``scope member`` collection."""

    # ------------------------------------------------------------------
    # Install operations
    # ------------------------------------------------------------------

    @abstractmethod
    def install_device_url(self) -> str:
        """URL used for ``securityconsole/install/device``."""

    @abstractmethod
    def install_package_url(self) -> str:
        """URL used for ``securityconsole/install/package``."""

    @abstractmethod
    def install_preview_url(self) -> str:
        """URL used for ``securityconsole/install/preview``."""

    @abstractmethod
    def install_device_payload(
        self, adom: str, device: str, *, vdom: str = "root"
    ) -> dict[str, Any]:
        """Payload for ``install_device``."""

    @abstractmethod
    def install_package_payload(
        self, adom: str, pkg: str, device: str, *, vdom: str = "root"
    ) -> dict[str, Any]:
        """Payload for ``install_package``."""

    @abstractmethod
    def install_preview_payload(
        self, adom: str, device: str, *, vdom: str = "root"
    ) -> dict[str, Any]:
        """Payload for ``install_preview``."""


class BaseAdapter(VersionAdapter):
    """Shared defaults for the supported FMG versions.

    Concrete subclasses override only the pieces that differ between
    releases. Anything URL-shaped that 7.4 and 7.6 agree on lives here so
    we do not repeat ourselves.
    """

    # Identity ------------------------------------------------------------

    @property
    def version_label(self) -> str:  # pragma: no cover - subclasses override
        raise NotImplementedError

    # Workspace -----------------------------------------------------------

    def workspace_lock_url(self, adom: str) -> str:
        return f"/dvmdb/adom/{adom}/workspace/lock"

    def workspace_commit_url(self, adom: str) -> str:
        return f"/dvmdb/adom/{adom}/workspace/commit"

    def workspace_unlock_url(self, adom: str) -> str:
        return f"/dvmdb/adom/{adom}/workspace/unlock"

    def workspace_lockinfo_url(self, adom: str) -> str:
        return f"/dvmdb/adom/{adom}/workspace/lockinfo"

    # Devices -------------------------------------------------------------

    def device_url(self, adom: str, name: str) -> str:
        return f"/dvmdb/adom/{adom}/device/{name}"

    def device_group_url(self, adom: str, name: str) -> str:
        return f"/dvmdb/adom/{adom}/group/{name}"

    def device_group_collection_url(self, adom: str) -> str:
        return f"/dvmdb/adom/{adom}/group"

    def device_group_member_url(self, adom: str, group: str) -> str:
        return f"/dvmdb/adom/{adom}/group/{group}/object member"

    def device_add_url(self) -> str:
        return "/dvm/cmd/add/device"

    def device_delete_url(self) -> str:
        return "/dvm/cmd/del/device"

    def model_device_extra_fields(self) -> dict[str, Any]:
        return {}

    # CLI templates -------------------------------------------------------

    def cli_template_collection_url(self, adom: str) -> str:
        return f"/pm/config/adom/{adom}/obj/cli/template"

    def cli_template_url(self, adom: str, name: str) -> str:
        return f"/pm/config/adom/{adom}/obj/cli/template/{name}"

    def cli_template_group_collection_url(self, adom: str) -> str:
        return f"/pm/config/adom/{adom}/obj/cli/template-group"

    def cli_template_group_url(self, adom: str, name: str) -> str:
        return f"/pm/config/adom/{adom}/obj/cli/template-group/{name}"

    def cli_template_group_scope_url(self, adom: str, group: str) -> str:
        return f"/pm/config/adom/{adom}/obj/cli/template-group/{group}/scope member"

    # Scripts -------------------------------------------------------------

    def script_collection_url(self, adom: str) -> str:
        return f"/dvmdb/adom/{adom}/script"

    def script_execute_url(self, adom: str) -> str:
        return f"/dvmdb/adom/{adom}/script/execute"

    # Dynamic variables ---------------------------------------------------
    # Defaults match 7.4 (legacy ``obj/dynamic/variable`` + ``local-value``);
    # 7.6 overrides URLs and payload field names.

    def dynamic_variable_collection_url(self, adom: str) -> str:
        return f"/pm/config/adom/{adom}/obj/dynamic/variable"

    def dynamic_variable_url(self, adom: str, name: str) -> str:
        return f"/pm/config/adom/{adom}/obj/dynamic/variable/{name}"

    def dynamic_variable_mapping_url(self, adom: str, name: str) -> str:
        return f"/pm/config/adom/{adom}/obj/dynamic/variable/{name}/dynamic_mapping"

    def dynamic_variable_create_payload(
        self, name: str, default_value: str = ""
    ) -> dict[str, Any]:
        return {"name": name, "default-value": default_value}

    def dynamic_variable_mapping_payload(
        self, device: str, value: str, *, vdom: str = "root"
    ) -> dict[str, Any]:
        return {
            "_scope": [{"name": device, "vdom": vdom}],
            "local-value": value,
        }

    # Provisioning templates ---------------------------------------------

    def provisioning_template_collection_url(self, adom: str, slug: str) -> str:
        return f"/pm/{slug}/adom/{adom}"

    # Policy packages -----------------------------------------------------

    def policy_package_url(self, adom: str) -> str:
        return f"/pm/pkg/adom/{adom}"

    def policy_package_member_url(self, adom: str, pkg: str) -> str:
        return f"/pm/pkg/adom/{adom}/{pkg}/scope member"

    def policy_package_firewall_url(self, adom: str, pkg: str) -> str:
        return f"/pm/config/adom/{adom}/pkg/{pkg}/firewall/policy"

    # Blueprints ----------------------------------------------------------

    def blueprint_collection_url(self, adom: str) -> str:
        return f"/pm/config/adom/{adom}/obj/fmg/device/blueprint"

    def blueprint_url(self, adom: str, name: str) -> str:
        return f"/pm/config/adom/{adom}/obj/fmg/device/blueprint/{name}"

    # Provisioning Template Groups ---------------------------------------

    def provisioning_tmplgrp_collection_url(self, adom: str) -> str:
        return f"/pm/tmplgrp/adom/{adom}"

    def provisioning_tmplgrp_url(self, adom: str, name: str) -> str:
        return f"/pm/tmplgrp/adom/{adom}/{name}"

    def provisioning_tmplgrp_scope_url(self, adom: str, name: str) -> str:
        return f"/pm/tmplgrp/adom/{adom}/{name}/scope member"

    # Install operations --------------------------------------------------

    def install_device_url(self) -> str:
        return "/securityconsole/install/device"

    def install_package_url(self) -> str:
        return "/securityconsole/install/package"

    def install_preview_url(self) -> str:
        return "/securityconsole/install/preview"

    def install_device_payload(
        self, adom: str, device: str, *, vdom: str = "root"
    ) -> dict[str, Any]:
        return {
            "adom": adom,
            "scope": [{"name": device, "vdom": vdom}],
            "flags": ["none"],
        }

    def install_package_payload(
        self, adom: str, pkg: str, device: str, *, vdom: str = "root"
    ) -> dict[str, Any]:
        return {
            "adom": adom,
            "pkg": pkg,
            "scope": [{"name": device, "vdom": vdom}],
            "flags": ["none"],
        }

    def install_preview_payload(
        self, adom: str, device: str, *, vdom: str = "root"
    ) -> dict[str, Any]:
        return {
            "adom": adom,
            "device": [{"name": device, "vdom": vdom}],
            "flags": ["json"],
        }


__all__ = ["BaseAdapter", "VersionAdapter"]
