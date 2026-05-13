# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - YYYY-MM-DD

Initial public release.

### Added

- `FMGClient` / `FMGClientProtocol` — async JSON-RPC transport with
  retries (jittered exponential backoff) and typed error mapping.
- `SessionManager` — Bearer (API token) and user/password authentication.
- `WorkspaceLockContext` / `workspace_session()` — ADOM workspace lock
  context manager with safe `-9` degrade when workspace mode is off.
- `TaskTracker` — polls long-running FMG tasks (installs, scripts) to
  completion.
- `VersionAdapter` ABC + `BaseAdapter` defaults + per-version adapters
  for FMG 7.2, 7.4, 7.6 (`AdapterRegistry`, `detect_version()`).
- Managers (all require explicit `adapter` keyword — no defaults):
  - `DeviceManager`, `MetafieldManager`, `InstallManager`,
    `CLITemplateManager`, `CLITemplateGroupManager`, `AddressManager`,
    `AddressGroupManager`, `ServiceManager`, `ServiceGroupManager`,
    `PolicyPackageManager`, `BlueprintManager`,
    `ProvisioningTemplateManager`.
- Typed exception hierarchy: `FMGError`, `AuthError`, `LockError`,
  `NotFoundError`, `DuplicateError`, `TaskTimeoutError`, `VersionError`.
- Pydantic v2 frozen models with `extra="forbid"` for FMG responses.
- 14 unit-test modules covering client, session, locking, models,
  registry, detection, every manager, payload shape per version, and
  golden fixtures captured from a live FMG 7.6.5.
- `scripts/capture_fixtures.py` — standalone fixture capture against a
  real FMG, configured via `.env`.
