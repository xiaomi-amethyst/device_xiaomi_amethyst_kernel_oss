# Amethyst touch/display integration findings

## Source DTs and stock modules

The build compiles the Amethyst board overlay and three Volcano base DTBs
from MiCode sources. It does not copy the stock DTB/DTBO files. The overlay's
touch node uses `xiaomi,touch-spi` on SPI SE0, IRQ GPIO 70, reset GPIO 87,
and describes Goodix 9916R and FocalTech 3683G configurations.

The supplied prebuilt repository loads:

- `xiaomi_touch.ko`: common Xiaomi touch framework; depends on
  `panel_event_notifier` and `miev`.
- `goodix_core.ko`: Goodix controller, depends on `xiaomi_touch`.
- `focaltech_touch.ko`: FocalTech controller, depends on `xiaomi_touch` and
  advertises the exact `xiaomi,touch-spi` DT compatible.

Stock uses a modern framework exposing `register_touch_panel`,
`unregister_touch_panel`, `register_xiaomi_input_dev`,
`driver_get_touch_mode`, `driver_update_touch_mode`, shared raw-data buffers,
and display suspend/resume notification APIs.

## Verified panel-notifier fix

The released kernel's `enum panel_event_notifier_client` omitted three
stock entries. This changed client numbering and the CRC of
`panel_event_notifier_register`. Stock module BTF establishes:

| Client | Value |
| --- | --- |
| PRIMARY_TOUCH | 0 |
| SECONDARY_TOUCH | 1 |
| ECM | 2 |
| THERMAL | 3 |
| THERMAL_SECOND | 4 |
| BATTERY_CHARGER | 5 |
| BATTERY_CHARGER_SECOND | 6 |
| FINGERPRINT | 7 |
| FINGERPRINT_SECOND | 8 |
| KEYBOARD | 9 |
| MAX | 10 |

The header now contains all entries in this order. The rebuilt provider's
CRC is `0x5d69499b`, matching stock consumers. All 11 related CRC mismatches
in the supplied touch/fingerprint/thermal/battery module files are resolved.
The rebuilt provider's complete enum was also compared with stock BTF.

Reproduce the BTF inspection (requires pyelftools):

```sh
python3 scripts/inspect-module-btf-enum.py \
  ../amethyst-prebuilt/modules/vendor_dlkm/panel_event_notifier.ko \
  panel_event_notifier_client
python3 scripts/inspect-module-btf-enum.py \
  ../out/amethyst-standalone/drivers/soc/qcom/panel_event_notifier.ko \
  panel_event_notifier_client
```

The full standalone Image/module/DT build passed after the fix. Its log is
`../out/amethyst-panel-abi-build.log`. The import-CRC audit now reports only
two remaining mismatched stock module files: `sched-penalty.ko` and
`ufs_qcom.ko`. There are still 107 files needing providers absent from the
in-tree symbol table; this audit alone does not establish bootability.

For `xiaomi_touch.ko`, those missing exports are `cdev_tevent_alloc`,
`cdev_tevent_add_int`, `cdev_tevent_add_str`, `cdev_tevent_write` and
`cdev_tevent_destroy`. CRCs for all its providers present in the rebuilt
symbol table now match. No stock touch modules have been installed or loaded.

## Candidate source investigation

MiCode's dedicated touch-driver repository has no Amethyst, Flourite or Muyu
branch. Its Bixi release contains a newer common framework and a secondary
Goodix driver; it is not a complete Amethyst driver set.

Two community references were checked out locally for investigation:

- `xiaomi-8550-kernel/vendor_qcom_opensource_touch-drivers`: contains a
  Qualcomm touch framework and Goodix Berlin driver, but its FocalTech
  definitions do not supply the required FT3683G implementation.
- `LinkBoi00/android_kernel_xiaomi_garnet_dnm`: contains `goodix_9916r` and
  `FT3683G` controller sources. Its framework uses the older
  `xiaomitouch_register_modedata` interface, and its FocalTech driver binds
  `focaltech,n16-3683g-spi`. Its Goodix driver expects a `panel` phandle and
  uses L16 default firmware names, whereas Amethyst's base overlay previously
  lacked that phandle and requests different firmware/config names.

Other SM8650/SM8735 trees contain the modern common framework, but the
controller sources inspected were not a complete matching Amethyst pair.
The useful controller references require an actual port of framework,
display callbacks, DT property handling, firmware selection and panel-specific
features. Merely renaming their DT compatible would not make them a verified
Amethyst replacement. They are not part of the default device build.

## Goodix Linux 6.1 reference build

The Garnet reference at commit
`b6b8649899069260544e0f8df3d3c8bf9c59f1cf` now builds both its
`xiaomi_touch.ko` and `goodix_core.ko` against our Amethyst kernel. The small
compatibility patch changes SPI/I2C remove callbacks to `void` and replaces
the removed `PDE_DATA()` API with `pde_data()`.

After the standalone kernel build:

```sh
bash scripts/build-goodix-reference.sh
```

This fetches the pinned reference into
`../qcom/opensource/touch-garnet-reference`, applies the version-specific
patch idempotently, and builds the two modules with the kernel's generated
headers and symbol table. Existing checkouts must have the expected revision.
The script accepts `TOUCH_REFERENCE_DIR`, `OUT_DIR`, `CLANG_BIN`, `JOBS` and
`HOST_SYSROOT`. The zero-context patch is tied to the pinned revision.

Outputs are under the reference's `drivers/input/touchscreen/xiaomi/` and
`drivers/input/touchscreen/goodix_9916r/` directories. Both passed compilation,
linking, modpost and BTF generation without unresolved symbols. Forward and
reverse patch checks and the repeated/idempotent build were also verified.

**This is a controller-port starting point, not a stock touch replacement.**
The pair uses its own older Xiaomi framework, retains its original
Garnet-compatible DT match, and has not been loaded on Amethyst. It still
needs correct binding, panel notification/firmware handling, userspace
interface validation and tests on a phone with the Goodix controller.

The FT3683G reference build was also attempted. It fails on old remove/procfs
APIs, two malformed logging calls, and a missing `include/firmware/fw_sample.i`
include. Correct Amethyst firmware selection and framework integration are
required before treating that driver as an Amethyst candidate.

## Rooted-stock reference observations

A read-only inspection was performed over rooted ADB with an explicit local
command allowlist; no writes, reloads or settings changes were issued to the
phone. The phone was running HyperOS OS3.0.305.0.WOPCNXM and kernel
`6.1.138-android14-Wild` with KernelSU. This is the tested environment, not
proof that the kernel was unmodified.

Verified live settings (`hwid_value=1638400`, `project=12`, `build_adc=20488`,
`project_adc=4537`, SoC ID 636) decode to project 12, global region and build
revision 9. They validate the reconstructed bit fields and Amethyst product
mapping, but must be supplied by boot configuration rather than compiled in:
they are specific to that inspected board.

The phone's SPI device `spi0.0` is bound to `xiaomi,touch-spi`. Both
controller modules are loaded, while `/proc/bus/input/devices` identifies the
active input device as `goodix_ts`. Its stock module contains this source
path:

```text
vendor/xiaomi/proprietary/touch/touchfeature_v2/touch_driver/o16u/goodix_9916k/
```

That path was extracted from the module for candidate identification; the
corresponding source directory was not found in the public MiCode branches
checked. Embedded strings also use the released `goodix_firmware_csot.bin` and
`goodix_cfg_group_csot.bin` names, and the pcopied binaries match those names.

`/sys/hwid` is absent despite the stock module's four sysfs attribute
registrations. This runtime evidence agrees with its stock init code deleting
the kobject immediately after creating the group, so a reconstructed driver
should not claim stock's broken sysfs lifetime is a hardware interface.

The phone's running-DTB touch node has a six-entry `panel` phandle property.
That entry corresponds to the released display devicetree's
`amethyst-sde-display.dtsi`, which links the SPI touch device to six panel
sources. Display output and notifier integration still need a matching build
and device test; read-only inspection cannot prove these are functionally
correct. The phone's stock DT overlay applies cleanly to the added display
overlay node because its target path exists.

## Live device diagnostic summary

- Active input: `goodix_ts`; bound SPI driver: `xiaomi,touch-spi`.
- Touch modules loaded: `xiaomi_touch`, `goodix_core`, `focaltech_touch`.
- Framework dependencies: `panel_event_notifier` and `miev`.
- hwid: `hwid_value=1638400`, `project=12`, `build_adc=20488`,
  `project_adc=4537`; SoC ID 636.
- `/sys/hwid` is absent after init.
- Display link: six-panel `panel` property present in running DT.
- Firmware/config names confirmed: `goodix_firmware_csot.bin`,
  `goodix_cfg_group_csot.bin`, plus secondary Goodix firmware and THP INI
  files.

These observations validate the existing Goodix stock interface and provide
constraints for a source port. They do not establish that a rebuilt OSS stack
is boot- or touch-functional.

The local report and read-only captures (input devices, running FDT, live
module files and Goodix firmware/config binaries) are under
`../out/phone-readonly`. They are evidence for source comparison and should
not be blindly mixed into a build. The live kernel/KernelSU environment and
published prebuilt repository's touch module versions differ, so extracted
source-path and binding information must be treated as evidence to port
against, not proof of a compatible upstream source.

A complete OSS touchscreen stack remains pending. The checked-in fixes
provide a buildable source kernel/DT foundation, a matching panel notifier
interface and a reproducible Goodix reference build. Working Amethyst touch
and device boot still require validation.
