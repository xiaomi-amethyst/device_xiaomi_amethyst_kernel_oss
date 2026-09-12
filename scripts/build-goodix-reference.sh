#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
# Compile a pinned controller/framework reference; Amethyst port is incomplete.
set -euo pipefail

kernel=$(realpath "$(dirname "${BASH_SOURCE[0]}")/..")
workspace=$(dirname "$kernel")
source_dir=${TOUCH_REFERENCE_DIR:-"$workspace/qcom/opensource/touch-garnet-reference"}
revision=b6b8649899069260544e0f8df3d3c8bf9c59f1cf
patch_file="$kernel/scripts/amethyst-patches/goodix-9916r-linux-6.1.patch"
out=${OUT_DIR:-"$workspace/out/amethyst-standalone"}
clang_bin=${CLANG_BIN:-"$workspace/prebuilts/clang/host/linux-x86/clang-r487747c/bin"}

if [[ ! -f "$out/Module.symvers" || ! -x "$clang_bin/clang" ]]; then
    printf 'Build the standalone kernel first; see BUILDING.amethyst.md.\n' >&2
    exit 1
fi
if [[ ! -e "$source_dir" ]]; then
    mkdir -p "$(dirname "$source_dir")"
    git clone --depth=1 --filter=blob:none --no-checkout \
        https://github.com/LinkBoi00/android_kernel_xiaomi_garnet_dnm.git "$source_dir"
    git -C "$source_dir" sparse-checkout set \
        drivers/input/touchscreen/xiaomi drivers/input/touchscreen/goodix_9916r
    git -C "$source_dir" fetch --depth=1 origin "$revision"
    git -C "$source_dir" checkout --detach "$revision"
fi
if [[ $(git -C "$source_dir" rev-parse HEAD) != "$revision" ]]; then
    printf 'Expected reference revision %s; existing checkout was not changed.\n' "$revision" >&2
    exit 1
fi
# Zero-context patch offsets are tied to the exact revision checked above.
if git -C "$source_dir" apply --unidiff-zero --check "$patch_file" 2>/dev/null; then
    git -C "$source_dir" apply --unidiff-zero "$patch_file"
elif ! git -C "$source_dir" apply --unidiff-zero --reverse --check "$patch_file"; then
    printf 'Reference patch conflicts with the existing checkout.\n' >&2
    exit 1
fi

export PATH="$clang_bin:$PATH"
if [[ -n ${HOST_SYSROOT:-} ]]; then
    host_root=$(realpath "$HOST_SYSROOT")
    export PATH="$host_root/usr/bin:$PATH"
    export LD_LIBRARY_PATH="$host_root/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi
touch_dir="$(realpath "$source_dir")/drivers/input/touchscreen"
make_args=(-C "$kernel" "O=$(realpath "$out")" ARCH=arm64 LLVM=1 "-j${JOBS:-$(nproc)}")
make "${make_args[@]}" "M=$touch_dir/xiaomi" CONFIG_TOUCHSCREEN_XIAOMI_TOUCHFEATURE=m modules
make "${make_args[@]}" "M=$touch_dir/goodix_9916r" CONFIG_TOUCHSCREEN_GOODIX_BRL_9916R=m \
    "KBUILD_EXTRA_SYMBOLS=$touch_dir/xiaomi/Module.symvers" modules
printf 'Reference modules built. Amethyst DT/framework integration and device testing remain pending.\n'
