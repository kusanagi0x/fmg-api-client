# Contributing

Thanks for considering a contribution! This document covers the most
common scenarios.

## Development setup

```bash
git clone https://github.com/kusanagi0x/fmg-api-client.git
cd fmg-api-client
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

Quality gates that must pass before merge:

```bash
ruff check src tests
ruff format --check src tests
mypy --strict src
pytest --cov=fmg_api_client
```

The CI workflow at `.github/workflows/ci.yml` enforces ruff + pytest +
coverage on every PR; mypy is recommended but not gated yet.

## Adding support for a new FMG version

This is the most common kind of contribution. Suppose Fortinet ships
FMG 7.8 with a renamed endpoint. The change is **a single new file**.

1. Create `src/fmg_api_client/versions/v78.py`:

   ```python
   """``FMG78Adapter`` — strategy for FortiManager 7.8.x."""

   from __future__ import annotations

   from fmg_api_client.versions.base import BaseAdapter
   from fmg_api_client.versions.registry import AdapterRegistry


   @AdapterRegistry.register("7.8")
   class FMG78Adapter(BaseAdapter):
       """Adapter for FortiManager 7.8.x."""

       @property
       def version_label(self) -> str:
           return "7.8"

       # Override only the methods whose URL/payload changed in 7.8. The
       # rest is inherited from BaseAdapter (or from a more recent
       # adapter you may parent-import).
   ```

2. Import-and-register from `src/fmg_api_client/versions/__init__.py`:

   ```python
   from fmg_api_client.versions.v78 import FMG78Adapter
   ```

3. Add a payload-shape test in `tests/unit/test_versions_payloads.py`
   asserting any new field rename or URL change you encoded.

4. (Optional but encouraged) Capture a golden fixture from a real
   FMG 7.8 via `scripts/capture_fixtures.py` and add a parsing test in
   `tests/unit/test_fixtures_v78.py` mirroring `test_fixtures_v76.py`.

5. Open a PR. The CI runs ruff + pytest; if everything is green and
   the existing 7.4 / 7.6 tests still pass (i.e. you did not regress
   `BaseAdapter`), it lands.

## Capturing golden fixtures against a real FMG

```bash
cp .env.example .env       # edit FMG_HOST, FMG_API_KEY (or USER/PASS), FMG_ADOM
python scripts/capture_fixtures.py
```

**Before committing**, redact identifying data from the captured JSON:
- Replace real hostnames with `fmg-lab-redacted`.
- Replace real serial numbers with `FMGVMSXX00000000`.
- Replace customer IPs with [RFC 5737](https://datatracker.ietf.org/doc/html/rfc5737)
  documentation ranges (`203.0.113.0/24`, `198.51.100.0/24`) or
  [RFC 1918](https://datatracker.ietf.org/doc/html/rfc1918) private
  ranges (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`).

The committed fixtures must contain **only** generic example data.

## Style

- Python 3.12+, strict type hints.
- `from __future__ import annotations` in every module.
- Pydantic v2 models for any data crossing the JSON-RPC boundary —
  never plain dicts.
- stdlib `logging` only (no `print`, no `loguru`).
- One short docstring per public function/class. No multi-paragraph
  docstrings; no comments for "what the code does" — the code does it.
- 99-char line length (ruff-enforced).

## Submitting changes

1. Fork the repo.
2. Create a feature branch.
3. Make your change with tests.
4. Open a PR with a clear description of the change and **why** it is
   needed (link to the FMG release notes or the empirical probe that
   surfaced the divergence, if relevant).
5. CI must be green.

## Reporting bugs

Open an issue with:
- FMG version (`/sys/status` output is ideal).
- The JSON-RPC URL + payload + response that misbehaves.
- The traceback or the assertion that fails.

For sensitive issues (security, customer data leakage), email
`kusanagi0x-security@…` instead of opening a public issue.
