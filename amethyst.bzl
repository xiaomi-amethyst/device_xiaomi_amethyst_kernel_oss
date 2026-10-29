load(":target_variants.bzl", "la_variants")
load(":msm_kernel_la.bzl", "define_msm_la")
load(":image_opts.bzl", "boot_image_opts")
load(":pineapple.bzl", "target_arch", "target_arch_in_tree_modules", "target_arch_consolidate_in_tree_modules", "target_arch_kernel_vendor_cmdline_extras", "target_arch_board_kernel_cmdline_extras", "target_arch_board_bootconfig_extras")
load(":xiaomi_sm8650_common.bzl", "xiaomi_common_in_tree_modules", "xiaomi_common_consolidate_in_tree_modules")

target_name = "amethyst"

def define_amethyst():
    _target_in_tree_modules = target_arch_in_tree_modules + \
        xiaomi_common_in_tree_modules + [
        # keep sorted
        "drivers/block/zram/zram.ko",
        "drivers/gpio/gpio-mi-t1.ko",
        "drivers/gpio/gpio-tiantong.ko",
        "drivers/hyperenhance/hyperframe/hyperframe.ko",
        "drivers/input/fingerprint/fpc_fod/fpc16xx.ko",
        "drivers/input/fingerprint/goodix_fod/goodix_fod.ko",
        "drivers/input/touchscreen/goodix_berlin_driver/goodix_core.ko",
        "drivers/input/touchscreen/xiaomi/xiaomi_touch.ko",
        "drivers/input/misc/aw86927_haptic/aw8697-haptic.ko",
        "drivers/input/misc/si_haptic/si_haptic.ko",
        "drivers/misc/mi_sw_sync/mi_sw_sync.ko",
        "drivers/misc/wifi_gpio/xiaomi_wifi_gpio.ko",
        "drivers/power/supply/charger_partition.ko",
        "drivers/tty/n_gsm.ko",
        "mm/zsmalloc.ko",
        ]

    _target_consolidate_in_tree_modules = _target_in_tree_modules + \
            target_arch_consolidate_in_tree_modules + \
            xiaomi_common_consolidate_in_tree_modules + [
        # keep sorted
        ]
    kernel_vendor_cmdline_extras = list(target_arch_kernel_vendor_cmdline_extras)
    board_kernel_cmdline_extras = list(target_arch_board_kernel_cmdline_extras)
    board_bootconfig_extras = list(target_arch_board_bootconfig_extras)

    for variant in la_variants:
        if variant == "consolidate":
            mod_list = _target_consolidate_in_tree_modules
        else:
            mod_list = _target_in_tree_modules
            board_kernel_cmdline_extras += ["nosoftlockup"]
            kernel_vendor_cmdline_extras += ["nosoftlockup"]
            board_bootconfig_extras += ["androidboot.console=0"]
        define_msm_la(
            msm_target = target_name,
            msm_arch = target_arch,
            variant = variant,
            in_tree_module_list = mod_list,
            boot_image_opts = boot_image_opts(
                earlycon_addr = "qcom_geni,0x00a9C000",
                kernel_vendor_cmdline_extras = kernel_vendor_cmdline_extras,
                board_kernel_cmdline_extras = board_kernel_cmdline_extras,
                board_bootconfig_extras = board_bootconfig_extras,
            )
        )
