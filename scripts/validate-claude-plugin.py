#!/usr/bin/env python3
"""Keep strict Claude validation, allowing only the intentional version warning."""

from pathlib import Path
import subprocess
import sys


def main() -> int:
    for kind, prefix in (("plugin", ""), ("marketplace", "plugins[0] plugin.json → ")):
        path = Path(f".claude-plugin/{kind}.json").resolve()
        result = subprocess.run(
            ["claude", "plugin", "validate", str(path), "--strict"],
            capture_output=True,
            text=True,
        )
        print(result.stdout, end="")
        print(result.stderr, end="", file=sys.stderr)
        expected_warning = (
            f"Validating {kind} manifest: {path}\n\n"
            "⚠ Found 1 warning:\n\n"
            f"  ❯ {prefix}version: No version specified. Consider adding a version "
            'following semver (e.g., "1.0.0")\n\n'
            "✘ Validation failed (--strict treats warnings as errors)\n"
        )
        if result.returncode == 0:
            continue
        if result.returncode != 1 or result.stderr or result.stdout != expected_warning:
            return 1
        print("Accepted missing version: Claude updates follow Git commits.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
