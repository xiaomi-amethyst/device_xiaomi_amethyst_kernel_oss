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
  uses L16 default firmware names; the Amethyst touch node has no such
  phandle and requests different firmware/config names.

Other SM8650/SM8735 trees contain the modern common framework, but the
controller sources inspected were not a complete matching Amethyst pair.
The useful controller references require an actual port of framework,
display callbacks, DT property handling, firmware selection and panel-specific
features. Merely renaming their DT compatible would not make them a verified
Amethyst replacement. They have not been added to the build.

A complete OSS touchscreen stack remains pending. The checked-in fixes
provide a buildable source kernel/DT foundation and a matching panel notifier
interface; they do not claim working touch or a tested boot image.
