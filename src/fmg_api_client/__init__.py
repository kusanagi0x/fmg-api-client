"""``fmg-api-client`` — async JSON-RPC client for FortiManager.

Public surface for v0.1 (Phases 14a-14c):

- :class:`FMGClient` / :class:`FMGClientProtocol` — JSON-RPC transport.
- :class:`SessionManager` — auth (API token or user/pass).
- :class:`FMGError` (+ subclasses) — typed error hierarchy.
- :class:`TaskTracker` — async polling for long-running FMG operations.
- :class:`SystemStatus`, :class:`TaskStatus`, :class:`FMGStatusCode` — typed responses.
- :class:`VersionAdapter` (+ ``BaseAdapter``, ``FMG72Adapter``,
  ``FMG74Adapter``, ``FMG76Adapter``) — version strategy.
- :class:`AdapterRegistry` — decorator-based factory.
- :func:`detect_version` — async helper that probes ``/sys/status``.
- :class:`WorkspaceLockContext` and :func:`workspace_session` — workspace lock
  context manager (DI on adapter, no defaults).
- Managers — composable building blocks that take ``(client, adom, *, adapter)``:
  :class:`DeviceManager`, :class:`MetafieldManager`, :class:`InstallManager`,
  :class:`CLITemplateManager`, :class:`CLITemplateGroupManager`,
  :class:`AddressManager`, :class:`AddressGroupManager`,
  :class:`ServiceManager`, :class:`ServiceGroupManager`,
  :class:`PolicyPackageManager`, :class:`BlueprintManager`,
  :class:`ProvisioningTemplateManager`.
"""

from __future__ import annotations

from fmg_api_client.core.client import FMGClient, FMGClientProtocol
from fmg_api_client.core.exceptions import (
    AuthError,
    DuplicateError,
    FMGError,
    LockError,
    NotFoundError,
    TaskTimeoutError,
    VersionError,
)
from fmg_api_client.core.locking import (
    WorkspaceLockContext,
    WorkspaceLockState,
    workspace_session,
)
from fmg_api_client.core.models import (
    FMGStatusCode,
    JsonRpcRequest,
    JsonRpcResponse,
    JsonRpcResult,
    SystemStatus,
    TaskStatus,
)
from fmg_api_client.core.session import SessionManager
from fmg_api_client.core.tasks import TaskTracker
from fmg_api_client.managers import (
    AddressGroupManager,
    AddressManager,
    BlueprintManager,
    CLITemplateGroupManager,
    CLITemplateManager,
    DeviceManager,
    InstallManager,
    ManagerBase,
    MetafieldManager,
    PolicyPackageManager,
    ProvisioningTemplateManager,
    ServiceGroupManager,
    ServiceManager,
)
from fmg_api_client.versions import (
    AdapterRegistry,
    BaseAdapter,
    FMG72Adapter,
    FMG74Adapter,
    FMG76Adapter,
    VersionAdapter,
    detect_version,
)

__version__ = "0.1.0"

__all__ = [
    "AdapterRegistry",
    "AddressGroupManager",
    "AddressManager",
    "AuthError",
    "BaseAdapter",
    "BlueprintManager",
    "CLITemplateGroupManager",
    "CLITemplateManager",
    "DeviceManager",
    "DuplicateError",
    "FMG72Adapter",
    "FMG74Adapter",
    "FMG76Adapter",
    "FMGClient",
    "FMGClientProtocol",
    "FMGError",
    "FMGStatusCode",
    "InstallManager",
    "JsonRpcRequest",
    "JsonRpcResponse",
    "JsonRpcResult",
    "LockError",
    "ManagerBase",
    "MetafieldManager",
    "NotFoundError",
    "PolicyPackageManager",
    "ProvisioningTemplateManager",
    "ServiceGroupManager",
    "ServiceManager",
    "SessionManager",
    "SystemStatus",
    "TaskStatus",
    "TaskTimeoutError",
    "TaskTracker",
    "VersionAdapter",
    "VersionError",
    "WorkspaceLockContext",
    "WorkspaceLockState",
    "__version__",
    "detect_version",
    "workspace_session",
]
