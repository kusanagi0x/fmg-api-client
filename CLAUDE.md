# CLAUDE.md

> Keep this file at the root of the repo and at a maximum of one page. For anything longer or cross-cutting, link to the FortiStream Suite repo.

## Project purpose

Async, version-aware JSON-RPC client for FortiManager — the suite's canonical FMG access layer.

## Status

`Foundation`

## Cross-suite context (read these first)

This project is part of the **FortiStream Suite**. Cross-suite architecture, decisions, and principles live in the suite repo:

- Architecture: https://github.com/CarlosTejeiro/fortistream-suite/blob/main/ARCHITECTURE.md
- Principles (mandatory): https://github.com/CarlosTejeiro/fortistream-suite/blob/main/PRINCIPLES.md
- Glossary: https://github.com/CarlosTejeiro/fortistream-suite/blob/main/GLOSSARY.md
- Active roadmap: https://github.com/CarlosTejeiro/fortistream-suite/blob/main/ROADMAP.md
- Cross-suite ADRs: https://github.com/CarlosTejeiro/fortistream-suite/tree/main/decisions
- Integration map (what this project depends on, who depends on it): https://github.com/CarlosTejeiro/fortistream-suite/blob/main/INTEGRATION_MAP.md

## Project-internal architecture (this repo)

- `src/fmg_api_client/core/` — `FMGClient`, `SessionManager`, `WorkspaceLockContext`, `TaskTracker`. Async JSON-RPC transport on httpx with typed error mapping.
- `src/fmg_api_client/versions/` — per-FMG-version adapters (`FMG72Adapter`, `FMG74Adapter`, `FMG76Adapter`) registered via `@AdapterRegistry.register("7.6")`. `detect_version()` resolves the right one from `/sys/status`.
- `src/fmg_api_client/managers/` — composable, idempotent managers (`DeviceManager`, `MetafieldManager`, `InstallManager`, `CLITemplateManager`, address/service/policy/blueprint/provisioning managers). All take `(client, adom, *, adapter)` — no defaults.
- `tests/` — pytest + respx, plus golden fixtures captured from real FMG 7.6 under `tests/fixtures/responses/v<NN>/`.

## Project-specific constraints (delta from suite principles)

- A new FMG version is a new file under `versions/` decorated with `@AdapterRegistry.register(...)`. Never modify an existing adapter to handle a different version.
- Managers must require `client + adom + adapter` explicitly. No defaulting the adapter, ever — that's the "wrong adapter silently picked" class of bug we are protecting against.
- Pydantic v2 payloads are sealed (`frozen=True`, `extra="forbid"`). Don't relax this to "make tests pass".
- Errors are mapped to the typed hierarchy in `errors.py` (`NotFoundError`, `DuplicateError`, `AuthError`, `LockError`, `VersionError`, `TaskTimeoutError`, `FMGError`). Do not raise bare exceptions from manager code.
- Golden fixtures must be redacted before commit (no real hostnames, serials, tokens, IPs).

## Standard commands

```bash
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"

ruff check src tests
ruff format --check src tests
mypy --strict src
pytest --cov=fmg_api_client
```

Capture golden fixtures against a real FMG (requires `.env`):

```bash
python scripts/capture_fixtures.py --adom <your-test-adom>
```

## Things NOT to do

- Do not add `add`/`set`/`update`/`delete` calls inside `core/` — write paths belong in managers that explicitly own the operation.
- Do not branch on FMG version inside caller code; rely on the adapter. If a divergence isn't captured by an adapter override, add the override.
- Do not call a real FMG from unit tests. Use respx + golden fixtures.
- Do not commit unredacted fixtures.

## Trabajo en curso

See `fortistream-suite/briefings/` for active cross-suite work touching this client (e.g. migrations of `fortistream` / `fortival` / `fortiflex-vault` onto this package).

## Contact / ownership

Maintainer: Carlos Tejeiro. Issues: https://github.com/kusanagi0x/fmg-api-client/issues
