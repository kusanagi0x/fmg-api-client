"""Capture golden response fixtures from a real FMG.

Hits a representative slice of read endpoints against an ADOM you have
access to and writes the JSON responses to
``tests/fixtures/responses/v<NN>/<slug>.json``. Tests then load these to
verify managers parse real shapes correctly.

Configure connection via environment variables (or a ``.env`` file next
to this script):

    FMG_HOST=fmg.example.com
    FMG_API_KEY=...          # OR FMG_USERNAME + FMG_PASSWORD
    FMG_VERIFY_SSL=true
    FMG_ADOM=my-test-adom

Usage::

    python scripts/capture_fixtures.py
    python scripts/capture_fixtures.py --adom OtherADOM
    python scripts/capture_fixtures.py --host 10.0.0.5

Re-running overwrites. Commit the fixtures after redacting any
identifying data (hostnames, serial numbers, customer IPs).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

# Allow running from a checkout without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fmg_api_client import (
    FMG76Adapter,
    FMGClient,
    SessionManager,
    detect_version,
)

# (slug, url-template, description). ``{adom}`` substitutes at runtime.
_ENDPOINTS: list[tuple[str, str, str]] = [
    ("sys_status", "/sys/status", "FMG version + serial"),
    (
        "address_objects_collection",
        "/pm/config/adom/{adom}/obj/firewall/address",
        "Default Fortinet address objects",
    ),
    (
        "service_objects_collection",
        "/pm/config/adom/{adom}/obj/firewall/service/custom",
        "Default Fortinet service objects",
    ),
    (
        "cli_templates_collection",
        "/pm/config/adom/{adom}/obj/cli/template",
        "CLI templates list",
    ),
    (
        "dynamic_variable_collection_76",
        "/pm/config/adom/{adom}/obj/fmg/variable",
        "Meta-variables (FMG 7.6 namespace)",
    ),
    (
        "policy_packages_collection",
        "/pm/pkg/adom/{adom}",
        "Policy packages",
    ),
    (
        "device_groups_collection",
        "/dvmdb/adom/{adom}/group",
        "Device groups",
    ),
    (
        "lockinfo",
        "/dvmdb/adom/{adom}/workspace/lockinfo",
        "Workspace lock state",
    ),
]


def _load_dotenv(path: Path) -> None:
    """Tiny ``.env`` parser — no external dep. Sets os.environ in place."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        os.environ.setdefault(key, value)


def _build_session(host: str) -> SessionManager:
    api_token = os.environ.get("FMG_API_KEY")
    username = os.environ.get("FMG_USERNAME")
    password = os.environ.get("FMG_PASSWORD")
    verify_ssl = os.environ.get("FMG_VERIFY_SSL", "true").lower() != "false"

    if api_token:
        return SessionManager(host=host, api_token=api_token, verify_ssl=verify_ssl)
    if username and password:
        return SessionManager(
            host=host,
            username=username,
            password=password,
            verify_ssl=verify_ssl,
        )
    raise SystemExit(
        "Configure FMG_API_KEY, or FMG_USERNAME + FMG_PASSWORD, in env or .env."
    )


async def _capture(*, host: str, adom: str, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    session = _build_session(host)
    async with FMGClient(session) as client:
        adapter = await detect_version(client)
        version = adapter.version_label.replace(".", "")
        target = out_dir / f"v{version}"
        target.mkdir(parents=True, exist_ok=True)
        print(f"FMG version detected: {adapter.version_label}")
        print(f"Writing fixtures to {target}\n")

        for slug, url_template, desc in _ENDPOINTS:
            url = url_template.format(adom=adom)
            print(f"=== {slug}  ({desc})")
            print(f"    GET {url}")
            try:
                data = await client.get(url)
                fixture = {"url": url, "response": data}
                path = target / f"{slug}.json"
                path.write_text(
                    json.dumps(fixture, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                preview = (
                    f"({len(data)} items)"
                    if isinstance(data, list)
                    else "(dict)"
                    if isinstance(data, dict)
                    else f"({type(data).__name__})"
                )
                print(f"    OK -> {path.relative_to(out_dir.parent)} {preview}")
            except Exception as exc:
                print(f"    FAIL -> {exc}")
            print()

        # 7.4-shape namespace probe — useful as a contrast fixture on 7.6
        # (it should return -3 there; we capture either outcome).
        if isinstance(adapter, FMG76Adapter):
            print("=== dynamic_variable_collection_74_on_76 (negative probe)")
            url = f"/pm/config/adom/{adom}/obj/dynamic/variable"
            print(f"    GET {url}")
            try:
                data = await client.get(url)
                (target / "dynamic_variable_collection_74_on_76.json").write_text(
                    json.dumps({"url": url, "response": data}, indent=2) + "\n",
                    encoding="utf-8",
                )
                print("    OK (unexpected on 7.6) — captured")
            except Exception as exc:
                (
                    target / "dynamic_variable_collection_74_on_76_error.json"
                ).write_text(
                    json.dumps({"url": url, "error": str(exc)}, indent=2) + "\n",
                    encoding="utf-8",
                )
                print(f"    FAIL (expected) -> {exc}")
            print()


def main() -> None:
    _load_dotenv(Path(__file__).resolve().parents[1] / ".env")

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default=os.environ.get("FMG_HOST"))
    parser.add_argument("--adom", default=os.environ.get("FMG_ADOM"))
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "tests"
        / "fixtures"
        / "responses",
    )
    args = parser.parse_args()

    if not args.host:
        raise SystemExit("FMG host required: set FMG_HOST or pass --host.")
    if not args.adom:
        raise SystemExit("ADOM required: set FMG_ADOM or pass --adom.")

    asyncio.run(_capture(host=args.host, adom=args.adom, out_dir=args.out_dir))


if __name__ == "__main__":
    main()
