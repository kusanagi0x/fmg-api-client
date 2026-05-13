"""Version adapters for FortiManager.

Public surface:

- :class:`VersionAdapter` — strategy ABC; managers depend on this.
- :class:`BaseAdapter` — shared defaults for supported versions.
- :class:`FMG72Adapter`, :class:`FMG74Adapter`, :class:`FMG76Adapter` —
  concrete strategies.
- :class:`AdapterRegistry` — decorator-based registry for the factory.
- :func:`detect_version` — async helper that probes ``/sys/status`` and
  returns the right adapter via the registry.
"""

from __future__ import annotations

# Side-effect imports register adapters with AdapterRegistry. Order does
# not matter; the registry is keyed by version string.
import fmg_api_client.versions.v72
import fmg_api_client.versions.v74
import fmg_api_client.versions.v76  # noqa: F401
from fmg_api_client.versions.base import BaseAdapter, VersionAdapter
from fmg_api_client.versions.detect import detect_version
from fmg_api_client.versions.registry import AdapterRegistry
from fmg_api_client.versions.v72 import FMG72Adapter
from fmg_api_client.versions.v74 import FMG74Adapter
from fmg_api_client.versions.v76 import FMG76Adapter

__all__ = [
    "AdapterRegistry",
    "BaseAdapter",
    "FMG72Adapter",
    "FMG74Adapter",
    "FMG76Adapter",
    "VersionAdapter",
    "detect_version",
]
