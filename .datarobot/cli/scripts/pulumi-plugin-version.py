#!/usr/bin/env python3
# Prints the highest installed version of the named Pulumi resource plugin,
# or exits non-zero if none is installed. Usage: pulumi-plugin-version.py <plugin-name>
#
# `dr dependency check` execs a versions.yaml `command:` directly (no shell, no
# pipes, and the same command string for every OS). `pulumi plugin ls` lists
# every installed plugin, not just one, so a bare `command:` couldn't isolate
# the one we care about -- this script does the filtering itself. Python (run
# via `uv run python`, since `uv` is already a required prerequisite here) is
# what's actually cross-platform for a single `command:` string; a shell
# script can't run natively on Windows.
import json
import subprocess
import sys


def main() -> int:
    name = sys.argv[1]
    output = subprocess.run(
        ["pulumi", "plugin", "ls", "--json"], capture_output=True, check=True, text=True
    ).stdout

    versions = sorted(
        (
            p["version"]
            for p in json.loads(output)
            if p.get("name") == name and p.get("kind") == "resource"
        ),
        key=lambda v: [int(x) for x in v.split(".")],
    )
    if not versions:
        return 1

    print(versions[-1])
    return 0


if __name__ == "__main__":
    sys.exit(main())
