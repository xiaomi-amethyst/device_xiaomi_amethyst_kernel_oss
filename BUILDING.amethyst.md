# Amethyst source workspace

## Current status

**The standalone ARM64 `Image`, in-tree modules and Amethyst board DTs build
successfully from source.**
This is a GKI-based Qualcomm vendor/device kernel source tree. The standalone
build combines its GKI config with the Pineapple-family and Amethyst fragments;
it is not the separate ACK + vendor mixed-build release produced by Kleaf.
The default build includes three Volcano DTBs and the Amethyst board DTBO.
The mixed Muyu/Flourite overlay experiment is also documented below.

The reconstructed `drivers/misc/hwid/` compiles with all nine export CRCs and
KCFI IDs matching the supplied stock module. Its getters also match the stock
AArch64 machine code in emulator tests. See `HWID-PREBUILT.md`.

**Boot compatibility remains unresolved.** Of 715 supplied stock module files,
2 have import-CRC mismatches against the final standalone build:
`update_sched_opt` and `ufshcd_qti_hba_init_crypto_capabilities`. Restoring the
stock panel-notifier enum resolved the previous 11 touch/fingerprint/power
module mismatches. There are also 107 module files
requiring providers absent from the in-tree `Module.symvers`. `module_layout`
now matches stock (`0xea759d7f`). The first diagnostic build lacked host BTF
tooling during configuration and reported much broader mismatches; install
the dependencies before configuring. No boot image has been packaged or
tested on a phone.

## Reproduce the standalone build

On an Ubuntu/Debian build host, install the usual kernel build dependencies:

```sh
sudo apt-get install build-essential flex bison bc libssl-dev libelf-dev \
  zlib1g-dev cpio pahole pkg-config python3 git curl xz-utils
```

Install Clang r487747c at the path documented in the experiment below, or
point `CLANG_BIN` to its `bin` directory. From the kernel checkout:

```sh
bash scripts/build-amethyst-standalone.sh
```

The linked MiCode `kernel_devicetree` checkout is required for the default DT
goals. Populate it with the source setup script below. No stock `Image`, DTB,
DTBO or kernel module is copied into the standalone build.

Defaults: 16 jobs on the tested host (`nproc`), output at
`../out/amethyst-standalone`. Override with `JOBS`, `OUT_DIR`, or `CLANG_BIN`.
An optional `HOST_SYSROOT` can point to unpacked native development packages
with `usr/include` and `usr/lib/x86_64-linux-gnu`; only host-tool flags use it.
The tested no-root environment used `/tmp/opencode/amethyst-host-deps`.

The script regenerates the output config from the three source fragments on
each invocation. Optional arguments replace the default Image/module/DT goals:

```sh
bash scripts/build-amethyst-standalone.sh drivers/misc/hwid/hwid.o
```

Successful outputs include `arch/arm64/boot/Image`, `vmlinux`, `Module.symvers`,
`drivers/misc/hwid/hwid.ko`, and `arch/arm64/boot/dts/vendor/qcom/{volcano.dtb,
volcano6.dtb,volcano6p.dtb,amethyst-sm7635-overlay.dtbo}` under the output
directory. These DT outputs are not a packaged Android `dtbo.img`. The full build log
from this session is `../out/amethyst-standalone-build.log`.

The build fixes also remove unconditional references to the unpublished
`st_asm330lhhx` directory (not enabled by Amethyst), and correct a host libbpf
const qualifier exposed by the newer host C library. The automotive target's
ASM330 driver is still unavailable; no replacement sensor driver is claimed.

### Touchscreen gap

The released Amethyst DTS describes `xiaomi,touch-spi`, Goodix 9916R and
FocalTech 3683G, with IRQ GPIO 70 and reset GPIO 87. Its properties request
`goodix_firmware_csot` and `goodix_cfg_group_csot`. The stock module list loads
`xiaomi_touch.ko`, `goodix_core.ko` and `focaltech_touch.ko`.

No driver matching `xiaomi,touch-spi` exists in this kernel checkout. The
generic in-tree Goodix driver is not that Xiaomi SPI driver. Thus successful
DT compilation alone does not provide working touch. The default build
does not silently reuse the stock touch modules. Touch driver integration,
display/camera overlays, external modules and device testing are still
required for a complete OSS device-kernel package.

`TOUCHSCREEN.amethyst.md` records the candidate controller sources, framework
differences, and the verified panel-notifier ABI fix. Stock touch module CRCs
now match all providers present in the standalone build, but the common touch
module still requires the five `cdev_tevent_*` exports supplied by stock miev.

MiCode's `flourite-v-oss` release contains Amethyst/SM7635 and Volcano
support. Its device-tree platform map selects `volcano.dtb`, `volcano6.dtb`,
`volcano6p.dtb`, and `amethyst-sm7635-overlay.dtbo` for Amethyst. The kernel's
`amethyst` target inherits the shared `pineapple` build configuration, which
also supports Volcano.

## Populate the released sources

From this kernel checkout, run:

```sh
python3 scripts/setup-amethyst-sources.py
```

The script shallow-clones the eight MiCode repositories on `flourite-v-oss`
into the parent directory. It reuses existing Git checkouts without updating
them. It creates the `msm-kernel`, `WORKSPACE`, `tools/bazel`, and `vendor/qcom`
links required by the build paths. Conflicting existing paths cause an error.
The kernel's tracked `arch/arm64/boot/dts/vendor` link resolves to
`qcom/proprietary/devicetree` in that workspace.

The repository-to-path mapping is in `SOURCES` in the script. Display and
camera device trees are separate from the SoC device tree; downloading them
does not by itself integrate their module/overlay build targets.

## Remaining build dependencies

These eight repositories are **not a complete kernel-platform workspace**.
Supply the matching Qualcomm/Android manifest's `common` kernel, Bazel common
rules, build-tool and compiler prebuilts, JDK, NDK, and `external/dtc`.
`build.config.constants` requests Android 14 / Linux 6.1 and Clang `r487747c`.
The vendor drivers also reference `securemsm-kernel`, `mmrm-driver`,
`mm-drivers`, `synx-kernel`, `dataipa`, and Xiaomi `minet/mixdp`.

Check for the known missing paths without downloading anything:

```sh
python3 scripts/setup-amethyst-sources.py --check
```

The script returns nonzero while required paths are missing. This is a path
check, not a compatibility or build-success check; further dependencies may
be reported by Bazel once the base workspace is available.

## Build

Once the matching base workspace is populated:

```sh
python3 build_with_bazel.py -t amethyst gki
```

Use `-t amethyst consolidate` for the consolidate variant. The default output
directory for GKI is `../out/msm-kernel-amethyst-gki`.

The Kleaf mixed build, external-module integration, and device boot have not
yet been validated. The successful standalone build is described above.

## Muyu + Flourite experiment (2026-09-11)

The initial comparison, before reconstructing hwid, used Muyu kernel commit
`681e88870888dec258dd48b0ab8c908b303eb159`. Both releases omit:

- `drivers/misc/hwid/`: required by `CONFIG_MI_HARDWARE_ID`, the shared
  `hwid.ko` module list, and the Wi-Fi GPIO driver's `hwid.h` include.
- `drivers/iio/stm/imu/st_asm330lhhx/`: referenced unconditionally by the
  STM IMU Kconfig. Its configuration is used by the automotive target,
  but the missing Kconfig file prevents parsing even for Amethyst.

Muyu additionally omits `arch/arm64/configs/vendor/amethyst_GKI.config` and
source directories for several modules named in its Amethyst list. These
include fingerprint drivers, `binder_prio`, `mi_schedule`, `miev`, `migt`,
`metis`, `mist`, and the mi-log/mi-perf modules. Combining the module lists
therefore adds unresolved dependencies.

Reproduce the Git-tree audit from the kernel checkout (it checks committed
trees, not working-tree edits):

```sh
git fetch --depth=1 https://github.com/MiCode/Xiaomi_Kernel_OpenSource.git muyu-v-oss
python3 scripts/audit-amethyst-sources.py HEAD 681e88870888dec258dd48b0ab8c908b303eb159
```

### Kernel build attempt

Installed Google's `clang-r487747c` archive from:

```text
https://android.googlesource.com/platform/prebuilts/clang/host/linux-x86/+archive/refs/heads/android14-release/clang-r487747c.tar.gz
SHA256: e6b88a46f5cbe0ef5d49b4a4fe07111dd42bc3194b327bae7f9565c29f67d1cf
```

Extracted under `../prebuilts/clang/host/linux-x86/clang-r487747c`.
The initial standalone configuration command was:

```sh
export PATH="$(realpath ../prebuilts/clang/host/linux-x86/clang-r487747c/bin):$PATH"
make O="$(realpath ../out/amethyst-standalone)" ARCH=arm64 LLVM=1 gki_defconfig
```

It compiled the host Kconfig tools, then stopped at:

```text
drivers/misc/Kconfig:535: can't open file "drivers/misc/hwid/Kconfig"
```

That initial attempt produced no kernel `Image` or loadable kernel modules.
The later stock-module reconstruction resolved the hwid blocker and the
standalone build now succeeds, as described at the top of this document.

### Combined device-tree build: passed

- Muyu base tree: `MiCode/kernel_devicetree` at
  `21b354440459b84995dd7266c95cd17c0abc110c`, checked out separately at
  `../qcom/proprietary/devicetree-muyu`.
- Flourite overlay tree: `MiCode/kernel_devicetree` at
  `4a44b8da9f6a9b9e66c61e640d090b421f9d71be`.
- DTC: AOSP `platform/external/dtc`, `android14-release`, commit
  `7044ca195a41133db1fd03d6e6d93f03e733b865`, at `../external/dtc`.

Build the DTC tools, then run the experiment from the kernel checkout:

```sh
make -C ../external/dtc -j16 \
  CC="$(realpath ../prebuilts/clang/host/linux-x86/clang-r487747c/bin/clang)" \
  PKG_CONFIG=true NO_PYTHON=1 NO_YAML=1 dtc fdtoverlay fdtget
python3 scripts/build-amethyst-dt-smoke.py \
  --base-tree ../qcom/proprietary/devicetree-muyu \
  --out ../out/amethyst-muyu-flourite-dt
```

All three bases (`volcano`, `volcano6`, `volcano6p`) compiled and accepted
Flourite's Amethyst overlay. The test also checked the overlay's model and
the resulting Amethyst fingerprint node. Compiler warnings are preserved
in the output directory's `.log` files; this is not a DT schema validation.

Outputs include `amethyst-sm7635-overlay.dtbo` and three
`volcano*-amethyst.dtb` files. They are integration-test artifacts, not
packaged `dtbo.img` or `boot.img`. Camera/display overlays, firmware matching,
module ABI, and device boot remain untested.

### Combined driver change

`drivers/input/misc/si_haptic/haptic.c` restores Muyu's conversion of a busy
GPIO error to `-EPROBE_DEFER` after Flourite's bounded GPIO retries. This
allows a later probe instead of permanently failing after temporary GPIO
contention. The change passes `checkpatch.pl` and the haptic object compiled
successfully with the Amethyst configuration. Hardware testing is pending.
