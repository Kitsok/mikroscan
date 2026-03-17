#!/usr/bin/env python3
"""Generate build metadata files for the web UIs."""

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = REPO_ROOT / "VERSION"
OUTPUTS = [
    REPO_ROOT / "web" / "build_info.json",
    REPO_ROOT / "addons" / "mikroscan" / "app" / "web" / "build_info.json",
]


def current_build_id() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def current_version() -> str:
    return VERSION_FILE.read_text(encoding="utf-8").strip()


def main() -> int:
    build_id = current_build_id()
    payload = {
        "build_id": build_id,
        "version": current_version(),
    }

    for output in OUTPUTS:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(f"{json.dumps(payload, indent=2)}\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
