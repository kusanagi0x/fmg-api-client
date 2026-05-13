"""``InstallManager`` — install device settings and policy packages.

All install ops are async on FMG: the API returns a task ID and the
caller polls it via :class:`TaskTracker`. URL + payload come from the
version adapter so 7.4/7.6 differences in flags/scope shape are absorbed.
"""

from __future__ import annotations

import logging

from fmg_api_client.managers.base import ManagerBase

logger = logging.getLogger(__name__)


class InstallManager(ManagerBase):
    """Device-config installation + policy-package pushes (async)."""

    async def install_device_settings(
        self,
        device_name: str,
        *,
        vdom: str = "root",
    ) -> int:
        """Install device-level settings (templates, metafields) to a device.

        Returns the FMG task id; poll with :class:`TaskTracker`.
        """
        url = self._adapter.install_device_url()
        data = self._adapter.install_device_payload(self._adom, device_name, vdom=vdom)
        result = await self._client.execute(url, data)
        task_id = int(result.get("task", 0)) if isinstance(result, dict) else 0
        logger.info(
            "Install device settings started: %s (task %d)",
            device_name,
            task_id,
        )
        return task_id

    async def install_policy_package(
        self,
        package_name: str,
        device_name: str,
        *,
        vdom: str = "root",
    ) -> int:
        """Install ``package_name`` to ``device_name``. Returns task id."""
        url = self._adapter.install_package_url()
        data = self._adapter.install_package_payload(
            self._adom, package_name, device_name, vdom=vdom
        )
        result = await self._client.execute(url, data)
        task_id = int(result.get("task", 0)) if isinstance(result, dict) else 0
        logger.info(
            "Install policy package started: %s -> %s (task %d)",
            package_name,
            device_name,
            task_id,
        )
        return task_id

    async def install_preview(
        self,
        device_name: str,
        *,
        vdom: str = "root",
    ) -> int:
        """Generate an install preview (dry-run) for ``device_name``."""
        url = self._adapter.install_preview_url()
        data = self._adapter.install_preview_payload(self._adom, device_name, vdom=vdom)
        result = await self._client.execute(url, data)
        task_id = int(result.get("task", 0)) if isinstance(result, dict) else 0
        logger.info("Install preview started: %s (task %d)", device_name, task_id)
        return task_id


__all__ = ["InstallManager"]
