"""High-level FortiManager domain managers.

Each manager composes a :class:`FMGClientProtocol` + a
:class:`VersionAdapter` to expose idempotent operations on a single
ADOM. All managers require ``adapter`` explicitly — no defaults — to
prevent the silent "wrong adapter picked" class of bug that surfaces
when one version's URL shape is sent to a different version's FMG.
"""

from __future__ import annotations

from fmg_api_client.managers.base import ManagerBase
from fmg_api_client.managers.blueprints import BlueprintManager
from fmg_api_client.managers.cli_templates import (
    CLITemplateGroupManager,
    CLITemplateManager,
)
from fmg_api_client.managers.devices import DeviceManager
from fmg_api_client.managers.install import InstallManager
from fmg_api_client.managers.meta_objects import (
    AddressGroupManager,
    AddressManager,
    ServiceGroupManager,
    ServiceManager,
)
from fmg_api_client.managers.metafields import MetafieldManager
from fmg_api_client.managers.policies import PolicyPackageManager
from fmg_api_client.managers.provisioning import ProvisioningTemplateManager

__all__ = [
    "AddressGroupManager",
    "AddressManager",
    "BlueprintManager",
    "CLITemplateGroupManager",
    "CLITemplateManager",
    "DeviceManager",
    "InstallManager",
    "ManagerBase",
    "MetafieldManager",
    "PolicyPackageManager",
    "ProvisioningTemplateManager",
    "ServiceGroupManager",
    "ServiceManager",
]
