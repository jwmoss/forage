#!/usr/bin/env python3
"""Check real Facebook reads through the installed CLI and saved session."""

import json
import os
import shlex
import subprocess
import sys


def main():
    cli = shlex.split(os.environ.get("FORAGE_BIN", "forage"))

    def call(*args):
        result = subprocess.run(
            [*cli, "--no-color", *args], capture_output=True, text=True, timeout=120
        )
        if result.returncode:
            raise RuntimeError(
                f"{args[0]} failed with exit {result.returncode}; run the command to inspect the error"
            )
        return json.loads(result.stdout)

    doctor = call("doctor")
    if not doctor.get("browser_installed") or not doctor.get("session_exists"):
        raise RuntimeError(
            "Install Chromium and save a Facebook session before live tests"
        )
    group = os.environ.get("FORAGE_E2E_GROUP")
    if group:
        result = call("scrape", group, "--limit", "1", "--skip-comments", "--no-input")
        rows = result.get("posts")
    else:
        result = call(
            "marketplace", "computer", "--limit", "1", "--max-candidates", "3"
        )
        rows = result.get("listings")
    if not isinstance(rows, list) or not rows or not rows[0].get("id"):
        raise RuntimeError(
            "Live read returned no verified record; inspect access and page layout"
        )
    print("PASS real Facebook CLI read")


if __name__ == "__main__":
    try:
        main()
    except (
        RuntimeError,
        ValueError,
        KeyError,
        TypeError,
        OSError,
        subprocess.TimeoutExpired,
    ) as error:
        print(f"FAIL {error}", file=sys.stderr)
        sys.exit(1)
