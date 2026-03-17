#!/usr/bin/env python3
"""Synchronize the project version across installable artifacts."""

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = REPO_ROOT / "VERSION"
ADDON_CONFIG = REPO_ROOT / "addons" / "mikroscan" / "config.yaml"
INTEGRATION_MANIFEST = REPO_ROOT / "custom_components" / "mikroscan" / "manifest.json"


def read_version() -> str:
    return VERSION_FILE.read_text(encoding="utf-8").strip()


def write_version(version: str) -> None:
    VERSION_FILE.write_text(f"{version}\n", encoding="utf-8")


def bump_patch(version: str) -> str:
    major, minor, patch = version.split(".")
    return f"{major}.{minor}.{int(patch) + 1}"


def update_addon_config(version: str) -> None:
    lines = ADDON_CONFIG.read_text(encoding="utf-8").splitlines()
    updated = []
    for line in lines:
        if line.startswith("version: "):
            updated.append(f'version: "{version}"')
        else:
            updated.append(line)
    ADDON_CONFIG.write_text("\n".join(updated) + "\n", encoding="utf-8")


def update_manifest(version: str) -> None:
    payload = json.loads(INTEGRATION_MANIFEST.read_text(encoding="utf-8"))
    payload["version"] = version
    INTEGRATION_MANIFEST.write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )


def sync(version: str) -> None:
    write_version(version)
    update_addon_config(version)
    update_manifest(version)


def main(argv: list[str]) -> int:
    version = read_version()
    if len(argv) > 1 and argv[1] == "--bump":
        version = bump_patch(version)
    sync(version)
    print(version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
