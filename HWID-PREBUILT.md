# Amethyst hardware-ID module: extracted evidence

## Provenance

- Repository: https://github.com/BluedMC-Amethyst/device_xiaomi_amethyst-kernel
- Branch: `sixteen`
- Inspected commit: `a093cd87d71320d010f9af036bde9f956aaf0e64`
- Module: `modules/vendor_boot/hwid.ko` (23,592 bytes)
- SHA256: `4abe827d6448b8cc4f872a69b847648739208db94900598a42c173d155547539`
- ELF build ID: `237b32a74f83908e1bb06c1e9c123d81f11cf8de`
- Format: ELF64 little-endian AArch64, unstripped, with symbols and split BTF.
- License metadata: `GPL v2`
- Dependency: `socinfo`
- Vermagic: `6.1.68-android14-11-maybe-dirty SMP preempt mod_unload modversions aarch64`

The checkout is at `../amethyst-prebuilt`. It includes the kernel Image,
base DTBs, `dtbo.img`, vendor-boot modules, vendor-DLKM modules and system-DLKM
modules. No `hwid.h` was found in its exported kernel headers.

## Reproduce extraction

From this kernel source checkout, with the Clang tools installed:

```sh
python3 scripts/inspect-hwid-prebuilt.py \
  ../amethyst-prebuilt/modules/vendor_boot/hwid.ko \
  --kernel ../amethyst-prebuilt/images/kernel \
  --out ../out/hwid-prebuilt-analysis
```

This writes `hwid.json`, `disassembly.txt`, `relocations.txt`, `sections.txt`,
and `stock.config`. The extractor expects this Android AArch64 KCFI module
format; it is not a general-purpose decoder for every kernel module.

## Verified parameter and function behavior

Four unsigned 32-bit module parameters hold all hardware-ID data:
`hwid_value`, `project`, `build_adc`, and `project_adc`. All start at zero
in `.bss`. Parameter permissions decode to `0444`. The module does not
read the device tree, sample ADCs, or parse boot arguments itself; the
kernel/module loader supplies its parameters.

Disassembly establishes the following behavior:

| Export | Result | Export CRC |
| --- | --- | --- |
| `get_hw_id_value()` | `hwid_value` | `0x89a009ef` |
| `get_hw_version_platform()` | `project` | `0x4766f8d8` |
| `get_hw_project_adc()` | `project_adc` | `0xd2fa4265` |
| `get_hw_build_adc()` | `build_adc` | `0x5729f0d4` |
| `get_hw_country_version()` | `hwid_value >> 20` | `0x1b138c6d` |
| `get_hw_version_major()` | `hwid_value >> 16` | `0xae8bbffd` |
| `get_hw_version_minor()` | `hwid_value & 0xffff` | `0x5d6bcb5d` |
| `get_hw_version_build()` | `(hwid_value >> 16) & 0xf` | `0x090a7fa1` |
| `product_name_get()` | SoC/project lookup, otherwise `"unknown"` | `0x0f12f8be` |

The eight integer getters have KCFI type ID `0x837de525`. Compiling candidate
prototypes with Clang r487747c confirmed this matches `unsigned int (void)`.
The product function's ID `0x9b32cf31` matches `const char * (void)`, not
`char * (void)`. These checks establish function types, but do not recover
the original typedef spelling or all enums in the missing header.

### Product lookup

`product_name_get()` calls `socinfo_get_id()` and then examines `project`.
String-table relocations and bounds checks give these mappings:

| SoC ID | Project IDs and names |
| --- | --- |
| 457 (`0x1c9`) | 1 zeus, 2 cupid, 3 katyusha, 4 ingres, 5 zizhan, 6 thor, 7 loki, 8 unicorn, 9 ziyi, 10 diting, 11 caiwei, 12 mayfly |
| 519 (`0x207`) | 1 nuwa, 2 fuxi, 3 wangshu, 4 socrates, 5 ishtar, 6 babylon |
| 557 (`0x22d`) | 1 shennong, 2 houji, 3 manet, 4 aurora, 5 suiren, 6 ruyi, 7 goku, 13 zorn; IDs 8–12 return unknown |
| 614 (`0x266`) | 8 peridot, 9 chenfeng, 10 muyu, 11 uke |
| 636 (`0x27c`) | 12 amethyst, 14 flourite |

Other SoC IDs or project values return `"unknown"`. In particular, the
stock module has no additional cases for every SoC ID listed in the DTBO.
A reconstruction should not silently extend this mapping without evidence.

### Sysfs and lifetime

The module creates a top-level kobject named `hwid` and four read-only
attributes: `hwid_project`, `hwid_value`, `hwid_project_adc`, and
`hwid_build_adc`. Project/value format is `0x%x\n`; ADC format is `%d\n`.

The inspected init code calls `kobject_del()` even after successful group
creation. Therefore the strings alone do **not** establish that `/sys/hwid`
remains visible after init. A replacement should explicitly decide how to
handle this apparent lifetime bug and validate userspace expectations,
rather than describing the intended sysfs layout as observed runtime state.

## Cross-checks against source callers

`xiaomi_wifi_gpio.c` compares the country getter with `CountryCN`. Its stock
`xiaomi_wifi_gpio.ko` calls the getter and branches on a nonzero result,
establishing **CountryCN = 0**. The stock WCD USBSS probe compares the country
to 1 on the `CountryGlobal` path. ICNSS's India BDF paths compare it to 2.
Thus the header uses CN=0, Global=1 and India=2.

ICNSS's switch table at `.rodata + 0x8e70`, indexed by `project - 8`, maps
N16T=8, N9=9, O82=11, O16U=12 and P16U=14 to their named BDF strings.
WCD USBSS confirms N18=7 and the O81/O82 pair 10/11. The reconstructed
header includes these verified constants. Constants for other platform
branches, such as CNSS2's N1/N2/N3 names, remain outside this verified subset.

USB, WCD939x, camera and WLAN callers also use this interface. Matching only
the Wi-Fi GPIO calls would leave the reconstruction incomplete.

The stock Image's embedded config was successfully extracted. It enables
`CONFIG_MODVERSIONS`, `CONFIG_CFI_CLANG`, `CONFIG_KALLSYMS`, `CONFIG_IKCONFIG`
and `CONFIG_IKCONFIG_PROC`. Its system modules are stored under the release
`6.1.138-android14-11-g0c3d559bcd85-ab14529422`, while the vendor hwid module
has the different vermagic above. This is evidence to investigate within
the Android mixed-build ABI, not proof of either compatibility or failure
with our rebuilt kernel.

## Reconstructed driver and verification

The replacement is in `drivers/misc/hwid/{Kconfig,Makefile,hwid.h,hwid.c}`.
It preserves the parameters, default values, getter semantics, product
lookup and read-only sysfs formats. It uses proper `kobject_put()` cleanup
and retains the sysfs group after successful initialization, correcting the
apparent stock lifetime bug described above. This intentional difference
needs device/userspace testing.

The in-tree Amethyst configuration and full standalone `Image modules`
build passed. Wi-Fi GPIO, WCD USBSS, DWC3, eUSB2 repeater and SI haptic
objects also compiled. The new hwid C/header/Kconfig/Makefile pass checkpatch.

Using the generated hwid object and `.hwid.o.cmd`, the following checks passed:

- All nine exported-symbol CRCs exactly match the stock module.
- All nine KCFI type IDs exactly match the stock module.
- Eight getters, executed as actual AArch64 machine code in Unicorn,
  match stock on 264 boundary/random input vectors.
- Product lookup matches stock across 374 SoC/project combinations,
  including invalid IDs and boundary values.

Reproduce after building (requires `python3-unicorn` and `python3-pyelftools`):

```sh
python3 scripts/test-hwid-prebuilt.py \
  ../amethyst-prebuilt/modules/vendor_boot/hwid.ko \
  ../out/amethyst-standalone/drivers/misc/hwid/hwid.o
```

The emulator test relocates the stock and rebuilt ELF sections, supplies
`socinfo_get_id()` as its only permitted external call, and compares results.
It does not emulate module loading, sysfs, hardware, or other kernel services.

No replacement module has been loaded on a phone. The live parameter values
must still come from that phone's boot/module-loading configuration. Zero
defaults match stock but are not proof of the correct board/region values.

## Whole-kernel ABI result

Matching hwid's exports does **not** make the whole standalone kernel
compatible with stock modules. After installing BTF tooling and regenerating
the config, the final audit found CRC mismatches in 13 of 715 prebuilt module
files, and 107 files with missing providers in the rebuilt in-tree symbol
table. `module_layout` now matches stock (`0xea759d7f`). The initial build
without the BTF tooling available at configuration time differed here and
reported mismatches for all module files.

The remaining CRC differences are `panel_event_notifier_register` (11 files,
including stock touch/fingerprint modules), `update_sched_opt` (sched-penalty)
and `ufshcd_qti_hba_init_crypto_capabilities` (ufs_qcom). Duplicate module files
in vendor_boot and vendor_dlkm are counted separately. This result makes
stock reuse more plausible than the initial audit, but does not establish
loadability or boot compatibility.

```sh
python3 scripts/check-prebuilt-module-crcs.py ../amethyst-prebuilt/modules \
  ../out/amethyst-standalone/Module.symvers \
  --out ../out/hwid-prebuilt-analysis/stock-module-crcs.json
```

This check returns nonzero when mismatches/missing providers exist. Additional
providers may be supplied by external modules, but known CRC mismatches must
be resolved through a matching kernel/configuration and ABI, not by bypassing
module-version checks. Device boot remains untested.
