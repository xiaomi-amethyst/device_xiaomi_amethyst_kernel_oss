#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Audit literal Kconfig includes and Amethyst module directories in Git trees."""

import argparse
from pathlib import PurePosixPath
import re
import subprocess


def git(*args):
    return subprocess.check_output(["git", *args], text=True)


def audit(revision):
    files = set(git("ls-tree", "-r", "--name-only", revision).splitlines())
    kconfigs = sorted(path for path in files
                      if PurePosixPath(path).name.startswith("Kconfig")
                      and not path.startswith("scripts/kconfig/tests/"))
    missing = set()
    # Batch reads avoid spawning a Git process for each Kconfig file.
    objects = "\n".join("{}:{}".format(revision, path) for path in kconfigs) + "\n"
    result = subprocess.run(["git", "cat-file", "--batch"], input=objects.encode(),
                            stdout=subprocess.PIPE, check=True).stdout
    position = 0
    for path in kconfigs:
        end = result.index(b"\n", position)
        size = int(result[position:end].split()[2])
        text = result[end + 1:end + 1 + size].decode(errors="replace")
        position = end + size + 2
        for target in re.findall(r'^\s*source\s+"([^"$]+)"', text, re.MULTILINE):
            if target not in files:
                missing.add((path, target))
    print("\n{} ({})".format(revision, git("rev-parse", revision).strip()))
    print("Missing literal Kconfig sources (all architectures):")
    for path, target in sorted(missing):
        print("  {} -> {}".format(path, target))

    print("Amethyst module entries with no source directory:")
    modules = "\n".join(git("show", "{}:{}".format(revision, path))
                        for path in ("amethyst.bzl", "xiaomi_sm8650_common.bzl"))
    directories = {str(PurePosixPath(path).parent) for path in files}
    absent_modules = []
    for module in re.findall(r'"([^"\n]+\.ko)"', modules):
        if str(PurePosixPath(module).parent) not in directories:
            absent_modules.append(module)
            print("  " + module)
    config = "arch/arm64/configs/vendor/amethyst_GKI.config"
    print("Amethyst config: " + ("present" if config in files else "MISSING"))
    return bool(missing or absent_modules or config not in files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("revisions", nargs="+", help="Git revisions to inspect; checkout is not changed")
    args = parser.parse_args()
    failed = False
    for revision in args.revisions:
        failed = audit(revision) or failed
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
