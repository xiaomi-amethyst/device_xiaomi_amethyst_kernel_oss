#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
# Build the local Qualcomm kernel, in-tree Amethyst modules and board DTs.
set -euo pipefail

kernel=$(realpath "$(dirname "${BASH_SOURCE[0]}")/..")
workspace=$(dirname "$kernel")
clang_bin=${CLANG_BIN:-"$workspace/prebuilts/clang/host/linux-x86/clang-r487747c/bin"}
out=${OUT_DIR:-"$workspace/out/amethyst-standalone"}
jobs=${JOBS:-$(nproc)}

if [[ ! -x "$clang_bin/clang" ]]; then
    printf 'Missing Clang: %s/clang (see BUILDING.amethyst.md)\n' "$clang_bin" >&2
    exit 1
fi
export PATH="$clang_bin:$PATH"
mkdir -p "$out"
out=$(realpath "$out")
make_args=("O=$out" ARCH=arm64 LLVM=1 DTC_FLAGS=-@)

# Optional unpacked host packages for machines without root access.
# These flags affect host tools, not the ARM64 kernel's include paths.
if [[ -n ${HOST_SYSROOT:-} ]]; then
    host_root=$(realpath "$HOST_SYSROOT")
    export PATH="$host_root/usr/bin:$PATH"
    export LD_LIBRARY_PATH="$host_root/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    make_args+=("HOSTCFLAGS=-O2 -I$host_root/usr/include -I$host_root/usr/include/x86_64-linux-gnu"
                "HOSTLDFLAGS=-L$host_root/usr/lib/x86_64-linux-gnu")
fi

make -C "$kernel" "${make_args[@]}" gki_defconfig
"$kernel/scripts/kconfig/merge_config.sh" -m -O "$out" \
    "$kernel/arch/arm64/configs/gki_defconfig" \
    "$kernel/arch/arm64/configs/vendor/pineapple_GKI.config" \
    "$kernel/arch/arm64/configs/vendor/amethyst_GKI.config"
make -C "$kernel" "${make_args[@]}" olddefconfig

if [[ $# -eq 0 ]]; then
    set -- Image modules vendor/qcom/volcano.dtb vendor/qcom/volcano6.dtb \
        vendor/qcom/volcano6p.dtb vendor/qcom/amethyst-sm7635-overlay.dtbo
fi
make -C "$kernel" -j"$jobs" "${make_args[@]}" "$@"
