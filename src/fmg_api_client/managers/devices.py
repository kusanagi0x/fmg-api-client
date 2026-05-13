"""``DeviceManager`` — model device lifecycle on FortiManager.

All write operations assume the caller holds a workspace lock (via
``async with workspace_session(client, adom, adapter=adapter)``).

Idempotency:
- :meth:`ensure_model_device` — creates only if missing.
- :meth:`ensure_device_group` — creates only if missing.
- :meth:`assign_to_group` — tolerates ``DuplicateError`` (already a member).

Notes on FMG behaviour we absorb:
- 7.6 ``/dvm/cmd/add/device`` returns ``OK`` immediately but materializes
  the device row asynchronously. We poll ``/dvmdb/.../device/<name>``
  until it appears so subsequent reads do not race.
- ``/dvm/cmd/add/device`` accepts the OS version as ``os_ver`` (major)
  + ``mr`` (minor) ints, NOT the dotted ``"7.4"`` string.
- ``object member`` GET on an empty group returns the group's own
  metadata; we filter by ``vdom`` presence so empty groups don't look
  like one-member groups.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fmg_api_client.core.exceptions import DuplicateError, NotFoundError
from fmg_api_client.managers.base import ManagerBase
from fmg_api_client.managers.meta_objects import _to_dict_or_none

logger = logging.getLogger(__name__)


def _parse_os_version(os_ver: str) -> tuple[int, int]:
    """Split a version string into ``(major, mr)`` ints.

    Accepts ``"7"``, ``"7.6"``, ``"7.6.5"``, ``"v7.6.5-buildN"`` — only
    the first two numeric components matter to FMG's
    ``/dvm/cmd/add/device``, which rejects the dotted form with
    ``-20002 Invalid argument``. Returns ``(7, 0)`` on any parse error.
    """
    try:
        cleaned = str(os_ver).strip().lstrip("vV")
        if "-" in cleaned:
            cleaned = cleaned.split("-", 1)[0]
        parts = cleaned.split(".")
        major = int(parts[0])
        mr = int(parts[1]) if len(parts) >= 2 and parts[1] else 0
    except (TypeError, ValueError, IndexError):
        return (7, 0)
    return (major, mr)


class DeviceManager(ManagerBase):
    """Model device creation, authorization, and group assignment."""

    async def create_model_device(
        self,
        name: str,
        serial: str,
        *,
        platform: str = "FortiGate-VM64",
        os_ver: str = "7.0",
        psk: str = "",
        wait_timeout: float = 30.0,
        poll_interval: float = 1.0,
    ) -> Any:
        """Create a model device via ``/dvm/cmd/add/device`` and wait for the row.

        Args:
            name: Device name (hostname).
            serial: Serial number (or empty for PSK-based registration).
            platform: Platform string (e.g. ``"FortiGate-VM64"``).
            os_ver: FortiOS version string (``"major.minor"``).
            psk: Pre-shared key for zero-touch provisioning.
            wait_timeout: Seconds to poll for the device row to materialize.
            poll_interval: Seconds between device-GET polls.

        Returns:
            The device record from the first successful GET.

        Raises:
            TimeoutError: If the device row does not materialize before
                ``wait_timeout`` elapses.
        """
        os_major, mr = _parse_os_version(os_ver)

        device_data: dict[str, Any] = {
            "name": name,
            "sn": serial,
            "platform_str": platform,
            "os_ver": os_major,
            "mr": mr,
            "mgmt_mode": "fmg",
            "device action": "add_model",
            "flags": ["is_model", "linked_to_model"],
        }
        if psk:
            device_data["psk"] = psk
        device_data.update(self._adapter.model_device_extra_fields())

        # ``create_task`` (without ``nonblocking``) wraps the create in a
        # task and blocks the JSON-RPC response until it finishes. Without
        # it, task-level errors (e.g. -20084 "VM device not allowed") are
        # silently lost — only the outer OK is observed.
        data: dict[str, Any] = {
            "adom": self._adom,
            "flags": ["create_task"],
            "device": device_data,
        }
        url = self._adapter.device_add_url()
        await self._client.execute(url, data)
        logger.info(
            "Model device create accepted: %s (SN: %s) — waiting for row",
            name,
            serial or "PSK",
        )

        device_url = self._adapter.device_url(self._adom, name)
        deadline = asyncio.get_event_loop().time() + wait_timeout
        attempt = 0
        while True:
            try:
                record = await self._client.get(device_url)
                logger.info(
                    "Model device %s persisted after %d poll(s)",
                    name,
                    attempt + 1,
                )
                return record
            except NotFoundError:
                if asyncio.get_event_loop().time() >= deadline:
                    raise TimeoutError(
                        f"Model device {name!r} did not materialize within {wait_timeout:.0f}s"
                    ) from None
                attempt += 1
                await asyncio.sleep(poll_interval)

    async def ensure_model_device(
        self,
        name: str,
        serial: str,
        *,
        platform: str = "FortiGate-VM64",
        os_ver: str = "7.0",
        psk: str = "",
    ) -> tuple[Any, bool]:
        """Idempotent counterpart of :meth:`create_model_device`.

        Looks up by name; if missing, creates. Returns ``(record, created)``
        so callers can surface "Created" vs "Reused" without an extra GET.
        """
        url = self._adapter.device_url(self._adom, name)
        try:
            existing = await self._client.get(url)
            logger.info("Model device %s already present — skipping create", name)
            return existing, False
        except NotFoundError:
            record = await self.create_model_device(
                name=name,
                serial=serial,
                platform=platform,
                os_ver=os_ver,
                psk=psk,
            )
            return record, True

    async def authorize_device(self, name: str) -> dict[str, Any]:
        """Verify a model device is registered (read-only presence check).

        Model devices created via ``device action=add_model`` are already
        registered. Real hardware gets *promoted* automatically when it
        phones home with a matching SN/PSK. There is no separate write
        "authorize" API for pre-staged model devices; this call is a
        loud assertion that the device exists.
        """
        url = self._adapter.device_url(self._adom, name)
        existing = await self._client.get(url)
        logger.info(
            "Authorize (verify): device %s is registered in ADOM %s",
            name,
            self._adom,
        )
        narrowed = _to_dict_or_none(existing)
        if narrowed is None:
            raise NotFoundError(f"Device {name!r} not present", status_code=-3, url=url)
        return narrowed

    async def get_device_group(self, name: str) -> dict[str, Any] | None:
        """Return the device group record, or ``None`` if absent."""
        url = self._adapter.device_group_url(self._adom, name)
        try:
            return _to_dict_or_none(await self._client.get(url))
        except NotFoundError:
            return None

    async def ensure_device_group(self, name: str) -> None:
        """Create the device group if missing. Idempotent."""
        if await self.get_device_group(name) is not None:
            return
        url = self._adapter.device_group_collection_url(self._adom)
        await self._client.add(url, {"name": name, "type": "normal"})
        logger.info("Created device group: %s", name)

    async def assign_to_group(self, device_name: str, group_name: str) -> Any:
        """Add a device to a group (idempotent on ``DuplicateError``)."""
        await self.ensure_device_group(group_name)
        url = self._adapter.device_group_member_url(self._adom, group_name)
        data: dict[str, Any] = {"name": device_name, "vdom": "root"}
        try:
            result = await self._client.add(url, data)
        except DuplicateError:
            logger.info(
                "%s already member of group %s — skipping",
                device_name,
                group_name,
            )
            return None
        logger.info("Assigned %s -> group %s", device_name, group_name)
        return result

    async def get_device(self, name: str) -> Any:
        """Retrieve device details from FMG."""
        url = self._adapter.device_url(self._adom, name)
        return await self._client.get(url)

    async def try_get_device(self, name: str) -> dict[str, Any] | None:
        """Return the device record, or ``None`` if absent."""
        try:
            return _to_dict_or_none(await self.get_device(name))
        except NotFoundError:
            return None

    async def list_group_members(self, group_name: str) -> list[str]:
        """Return device names currently in ``group_name``.

        FMG quirk: a GET on an *empty* group returns the group's own
        metadata dict (``{"name": ..., "oid": ..., "type": "normal"}``)
        instead of an empty list. Real members always carry a ``vdom``
        field, so we use its presence as the discriminator.
        """
        url = self._adapter.device_group_member_url(self._adom, group_name)
        try:
            result = await self._client.get(url)
        except NotFoundError:
            return []
        if not result:
            return []
        entries = [result] if isinstance(result, dict) else result
        return [
            m["name"] for m in entries if isinstance(m, dict) and "vdom" in m and m.get("name")
        ]

    async def get_device_status(self, name: str) -> dict[str, Any]:
        """Return ``{name, conn_status, conf_status, db_status}`` for ``name``."""
        device = await self.get_device(name)
        return {
            "name": device.get("name", name),
            "conn_status": device.get("conn_status", "unknown"),
            "conf_status": device.get("conf_status", "unknown"),
            "db_status": device.get("db_status", "unknown"),
        }

    async def delete_device(self, name: str) -> Any:
        """Remove a model device from FMG."""
        url = self._adapter.device_delete_url()
        data: dict[str, Any] = {
            "adom": self._adom,
            "device": name,
            "flags": ["create_task", "nonblocking"],
        }
        result = await self._client.execute(url, data)
        logger.info("Deleted device: %s", name)
        return result


__all__ = ["DeviceManager"]
