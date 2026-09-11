#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Compile Volcano DTBs and apply the Amethyst overlay for integration testing."""

import argparse
import os
from pathlib import Path
import subprocess
import sys


def main():
    kernel = Path(__file__).resolve().parents[1]
    workspace = kernel.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-tree", type=Path, required=True,
                        help="Device-tree checkout providing the Volcano base DTBs")
    parser.add_argument("--overlay-tree", type=Path,
                        default=workspace / "qcom/proprietary/devicetree")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out = args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=True)
    tools = workspace / "external/dtc"
    clang = workspace / "prebuilts/clang/host/linux-x86/clang-r487747c/bin/clang"
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = str(tools / "libfdt") + (
        ":" + env["LD_LIBRARY_PATH"] if env.get("LD_LIBRARY_PATH") else "")

    def run(command, log):
        subprocess.run([str(arg) for arg in command], stdout=log, stderr=log,
                       env=env, check=True)

    def compile_tree(tree, name, output):
        source = tree.resolve() / "qcom" / (name + ".dts")
        preprocessed = args.out / (name + ".dts.preprocessed")
        log_path = args.out / (name + ".log")
        print("Compiling {} (log: {})".format(source, log_path), flush=True)
        with log_path.open("w") as log:
            run([clang, "-E", "-nostdinc", "-undef", "-D__DTS__",
                 "-x", "assembler-with-cpp", "-I", kernel / "include",
                 "-I", source.parent, source, "-o", preprocessed], log)
            run([tools / "dtc", "-@", "-I", "dts", "-O", "dtb",
                 "-o", output, preprocessed], log)

    overlay = args.out / "amethyst-sm7635-overlay.dtbo"
    compile_tree(args.overlay_tree, "amethyst-sm7635-overlay", overlay)
    model = subprocess.check_output(
        [str(tools / "fdtget"), str(overlay), "/", "model"], env=env, text=True).strip()
    if "Amethyst" not in model:
        raise RuntimeError("Unexpected overlay model: " + model)
    for name in ("volcano", "volcano6", "volcano6p"):
        base = args.out / (name + ".dtb")
        combined = args.out / (name + "-amethyst.dtb")
        compile_tree(args.base_tree, name, base)
        with (args.out / (name + "-overlay.log")).open("w") as log:
            run([tools / "fdtoverlay", "-i", base, "-o", combined, overlay], log)
        compatible = subprocess.check_output(
            [str(tools / "fdtget"), str(combined), "/soc/fingerprint_goodix", "compatible"],
            env=env, text=True).strip()
        if compatible != "goodix,fingerprint":
            raise RuntimeError("Amethyst fingerprint node was not applied")
        print("PASS: {}: Amethyst overlay applied".format(combined.name), flush=True)
    print("DT integration passed. These are test DTBs, not boot images.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        sys.exit(str(error))
