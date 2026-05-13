"""``detect_version`` — pick the right :class:`VersionAdapter` from a live FMG.

Calls ``GET /sys/status`` (a cheap, unauthenticated-feeling read), parses
the ``Version`` field (e.g. ``"v7.6.5-build1234..."``) and resolves the
adapter via :class:`AdapterRegistry`.

The function takes a connected client (or a stub implementing
:class:`FMGClientProtocol`) so it works in both production and tests.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fmg_api_client.core.models import SystemStatus
from fmg_api_client.versions.registry import AdapterRegistry

if TYPE_CHECKING:
    from fmg_api_client.core.client import FMGClientProtocol
    from fmg_api_client.versions.base import VersionAdapter

logger = logging.getLogger(__name__)


async def detect_version(client: FMGClientProtocol) -> VersionAdapter:
    """Probe ``/sys/status`` and return a matching :class:`VersionAdapter`.

    Args:
        client: A connected :class:`FMGClient` (or any compatible stub).

    Returns:
        A fresh adapter instance for the detected major.minor version.

    Raises:
        VersionError: If the FMG version is not registered.
    """
    data = await client.get("/sys/status")
    status = SystemStatus.model_validate(data) if isinstance(data, dict) else SystemStatus()
    adapter = AdapterRegistry.get(status.major_minor)
    logger.info(
        "FMG version %s detected — using %s",
        status.version or status.major_minor,
        adapter.version_label,
    )
    return adapter


__all__ = ["detect_version"]
