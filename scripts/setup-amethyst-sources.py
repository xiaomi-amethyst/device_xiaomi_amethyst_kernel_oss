#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Fetch the MiCode flourite release dependencies beside this kernel tree."""

import argparse
import os
from pathlib import Path
import subprocess
import sys


SOURCES = {
    "build/kernel": "kernel_build",
    "qcom/proprietary/devicetree": "kernel_devicetree",
    "qcom/proprietary/display-devicetree": "vendor_qcom_proprietary_display-devicetree",
    "qcom/proprietary/camera-devicetree": "vendor_qcom_proprietary_camera-devicetree",
    "qcom/opensource/wlan": "vendor_qcom_opensource_wlan",
    "qcom/opensource/display-drivers": "vendor_opensource_display-drivers",
    "qcom/opensource/audio-kernel": "vendor_qcom_opensource_audio-kernel",
    "qcom/opensource/camera-kernel": "vendor_qcom_opensource_camera-kernel",
}
BRANCH = "flourite-v-oss"


def link(source, destination):
    if os.path.lexists(destination):
        if destination.resolve() != source.resolve():
            raise RuntimeError("Conflicting workspace path: {}".format(destination))
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.symlink_to(os.path.relpath(source, destination.parent))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check sources without downloading")
    args = parser.parse_args()
    kernel = Path(__file__).resolve().parents[1]
    workspace = kernel.parent
    missing = []
    for relative, repository in SOURCES.items():
        destination = workspace / relative
        if os.path.lexists(destination):
            if not (destination / ".git").exists():
                raise RuntimeError("Expected a Git checkout: {}".format(destination))
            print("Using existing checkout: {}".format(destination), flush=True)
        elif args.check:
            missing.append(relative)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run([
                "git", "clone", "--depth=1", "--single-branch", "--branch", BRANCH,
                "https://github.com/MiCode/{}.git".format(repository), str(destination),
            ], check=True)

    if not args.check:
        link(kernel, workspace / "msm-kernel")
        link(kernel / "bazel.WORKSPACE", workspace / "WORKSPACE")
        link(workspace / "build/kernel/kleaf/bazel.sh", workspace / "tools/bazel")
        link(workspace / "qcom", workspace / "vendor/qcom")

    # These come from the matching Qualcomm/Android kernel-platform manifest,
    # rather than from the eight MiCode repositories above.
    for relative in (
        "msm-kernel/Makefile", "WORKSPACE", "tools/bazel", "vendor/qcom",
        "msm-kernel/drivers/misc/hwid/Kconfig",
        "msm-kernel/drivers/misc/hwid/hwid.h",
        "common/BUILD.bazel",
        "build/bazel_common_rules", "prebuilts/bazel", "prebuilts/build-tools",
        "prebuilts/clang/host/linux-x86/clang-r487747c",
        "prebuilts/clang/host/linux-x86/kleaf", "prebuilts/kernel-build-tools",
        "prebuilts/jdk/jdk11/linux-x86", "prebuilts/ndk-r23", "external/dtc",
        "vendor/qcom/opensource/securemsm-kernel",
        "vendor/qcom/opensource/mmrm-driver", "vendor/qcom/opensource/mm-drivers",
        "vendor/qcom/opensource/synx-kernel", "vendor/qcom/opensource/dataipa",
        "vendor/xiaomi/proprietary/minet/mixdp",
    ):
        if not (workspace / relative).exists():
            missing.append(relative)
    if missing:
        print("Workspace incomplete; missing:\n  " + "\n  ".join(missing), file=sys.stderr)
        return 1
    print("Source paths present. Run the Bazel build to validate integration.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        sys.exit(str(error))
