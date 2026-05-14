> Part of the [FortiStream Suite](https://github.com/CarlosTejeiro/fortistream-suite).

# fmg-api-client

Async, version-aware JSON-RPC client for **FortiManager**. Built on
`httpx` and Pydantic v2, with strict typing throughout.

The FortiManager API renames endpoints and payload fields between
releases (e.g. 7.4 → 7.6 moved meta-variable storage from
`obj/dynamic/variable` to `obj/fmg/variable` and renamed `local-value`
to `value`). A client that does not absorb those differences silently
corrupts state on upgrade. This package isolates per-version
differences in **adapter classes** and exposes a single high-level
manager surface, so caller code does not need to know which FMG
version it is talking to.

## Supported FMG versions

| Version | Adapter | Notes |
|---|---|---|
| 7.2 | `FMG72Adapter` | Inherits 7.4 shape (no probed-divergence yet) |
| 7.4 | `FMG74Adapter` | Default shape |
| 7.6 | `FMG76Adapter` | Meta-variable namespace moved + `value` rename + `os_type=fos` requirement on model-device registration |

`detect_version()` reads `/sys/status` and resolves the right adapter
automatically.

## Install

```bash
pip install fmg-api-client
# or with uv
uv add fmg-api-client
```

While unreleased on PyPI, install from GitHub:

```bash
pip install "fmg-api-client @ git+https://github.com/kusanagi0x/fmg-api-client.git@v0.1.0"
```

## Quickstart

```python
import asyncio
from fmg_api_client import (
    FMGClient,
    SessionManager,
    CLITemplateManager,
    detect_version,
)

async def main() -> None:
    session = SessionManager(
        host="fmg.example.com",
        api_token="...",     # or username="..." + password="..."
        verify_ssl=True,
    )
    async with FMGClient(session) as client:
        adapter = await detect_version(client)
        print(f"Connected to FMG {adapter.version_label}")

        templates = CLITemplateManager(client, "root", adapter=adapter)
        for tmpl in await templates.list_all():
            print(tmpl["name"], tmpl.get("type"))

asyncio.run(main())
```

## What's in the package

### Core

- `FMGClient` / `FMGClientProtocol` — async JSON-RPC transport with
  retries, backoff, and typed error mapping.
- `SessionManager` — Bearer (API token) or user/password handshake.
- `WorkspaceLockContext` / `workspace_session` — async context manager
  for ADOM workspace lock with safe `-9` degrade when workspace mode is
  disabled.
- `TaskTracker` — polls long-running FMG tasks (installs, scripts) to
  completion.

### Version adapters

Strategy ABC + decorator registry:

```python
@AdapterRegistry.register("7.6")
class FMG76Adapter(BaseAdapter):
    version_label = "7.6"
    # …per-version URL / payload overrides
```

Adding a new FMG version is a new file under `versions/`; the registry
picks it up. See [CONTRIBUTING.md](CONTRIBUTING.md) for the step-by-step.

### Managers

Composable, idempotent building blocks taking `(client, adom, *, adapter)`:

- `DeviceManager` — devices, device groups, model-device registration.
- `MetafieldManager` — ADOM meta-variables (a.k.a. dynamic variables) +
  per-device overrides.
- `InstallManager` — install device settings / policy package /
  preview, with task-tracking.
- `CLITemplateManager` / `CLITemplateGroupManager` — CLI templates and
  their device-group scoping.
- `AddressManager` / `AddressGroupManager`,
  `ServiceManager` / `ServiceGroupManager` — firewall objects.
- `PolicyPackageManager` — policy packages, rules, and scope members.
- `BlueprintManager` — device blueprints.
- `ProvisioningTemplateManager` — `wanprof` / `devprof` / `crprof` /
  `tmplgrp` slugs under the `/pm/<slug>/adom/<adom>` namespace.

### Errors

Typed hierarchy mapped from FMG status codes:

- `NotFoundError` (`-3`)
- `DuplicateError` (`-6`)
- `AuthError` (`-11`)
- `LockError` (workspace `-23`)
- `VersionError` (unsupported version)
- `TaskTimeoutError` (long-running install poll exceeded)
- `FMGError` (catch-all)

## Design notes

| Pattern | Where | Why |
|---|---|---|
| Strategy | `VersionAdapter` ABC + per-version subclasses | URL + payload shape lives in one class per version. |
| Factory + Registry | `@AdapterRegistry.register("7.6")` | Open/Closed: a new version = a new file. |
| Auto-detect | `await detect_version(client)` | Caller code does not branch on version. |
| Adapter (port) | `FMGClientProtocol` | Tests stub the client; production uses httpx. |
| DI (no defaults) | Managers require `client + adom + adapter` explicitly | Prevents the "wrong adapter silently picked" class of bug. |
| Sealed payloads | Pydantic v2 frozen, `extra="forbid"` | Catches typo'd field names at validation time. |

## Development

```bash
git clone https://github.com/kusanagi0x/fmg-api-client.git
cd fmg-api-client
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"

ruff check src tests
ruff format --check src tests
mypy --strict src
pytest --cov=fmg_api_client
```

## Capturing golden fixtures against a real FMG

`scripts/capture_fixtures.py` hits a representative slice of read
endpoints and writes the JSON responses to
`tests/fixtures/responses/v<NN>/`. Configure via `.env`
(see `.env.example`) and run:

```bash
python scripts/capture_fixtures.py --adom <your-test-adom>
```

Re-running overwrites. Always redact identifying data before
committing new fixtures.

## License

Apache License 2.0 — see [LICENSE](LICENSE).

## Contributing

Issues, PRs, and adapters for new FMG versions are welcome. See
[CONTRIBUTING.md](CONTRIBUTING.md).
