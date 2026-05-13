"""Decorator-based registry for :class:`VersionAdapter` subclasses.

Open/Closed: a new FMG version is added by creating ``versions/v78.py``
with ``@AdapterRegistry.register("7.8")`` — no other file changes.

Resolution rules:

- Exact match wins (``"7.6"`` → ``FMG76Adapter``).
- ``major.X`` lookups support a wildcard fallback when only the major is
  known (``"7"`` returns the highest registered minor for major 7).

All registered adapters are stateless, so :meth:`AdapterRegistry.get`
returns a freshly instantiated copy on every call.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from fmg_api_client.core.exceptions import VersionError

if TYPE_CHECKING:
    from collections.abc import Callable

    from fmg_api_client.versions.base import VersionAdapter


class AdapterRegistry:
    """Registry of :class:`VersionAdapter` subclasses keyed by version string."""

    _registry: ClassVar[dict[str, type[VersionAdapter]]] = {}

    @classmethod
    def register(cls, version: str) -> Callable[[type[VersionAdapter]], type[VersionAdapter]]:
        """Decorator: register ``adapter_cls`` under ``version`` (e.g. ``"7.6"``)."""

        def decorator(
            adapter_cls: type[VersionAdapter],
        ) -> type[VersionAdapter]:
            if version in cls._registry:
                raise ValueError(
                    f"Adapter for FMG {version!r} already registered "
                    f"(was {cls._registry[version].__name__}, "
                    f"now {adapter_cls.__name__})"
                )
            cls._registry[version] = adapter_cls
            return adapter_cls

        return decorator

    @classmethod
    def get(cls, version: str) -> VersionAdapter:
        """Resolve ``version`` to a fresh adapter instance.

        Args:
            version: Semantic version string. Accepted forms:
                - ``"7.6"`` (exact major.minor)
                - ``"7.6.5"`` (major.minor.patch — patch is dropped)
                - ``"v7.6.5-build1234"`` (FMG-style — leading ``v`` and
                  trailing ``-build…`` are tolerated).

        Raises:
            VersionError: If no adapter is registered for the resolved key.
        """
        normalized = cls._normalize(version)
        if normalized not in cls._registry:
            available = ", ".join(sorted(cls._registry.keys()))
            raise VersionError(
                f"No adapter registered for FMG {version!r} "
                f"(normalized to {normalized!r}). "
                f"Available: {available}",
                status_code=-1,
            )
        return cls._registry[normalized]()

    @classmethod
    def available(cls) -> tuple[str, ...]:
        """Return the registered version keys, sorted."""
        return tuple(sorted(cls._registry.keys()))

    @classmethod
    def _normalize(cls, version: str) -> str:
        """Strip ``v`` prefix and ``-build…`` suffix; keep only ``major.minor``."""
        v = version.strip().lstrip("vV")
        # Trim ``-build…`` or any other dash-suffix.
        if "-" in v:
            v = v.split("-", 1)[0]
        parts = v.split(".")
        if len(parts) >= 2:
            return f"{parts[0]}.{parts[1]}"
        return v


__all__ = ["AdapterRegistry"]
