/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef _XIAOMI_HWID_H
#define _XIAOMI_HWID_H

#include <linux/types.h>

/* Values verified against the Amethyst hwid, Wi-Fi and USBSS modules. */
enum hw_country_version {
	CountryCN = 0,
	CountryGlobal = 1,
	CountryIndia = 2,
};

enum hw_project_version {
	HARDWARE_PROJECT_N18 = 7,
	HARDWARE_PROJECT_N16T = 8,
	HARDWARE_PROJECT_N9 = 9,
	HARDWARE_PROJECT_O81 = 10,
	HARDWARE_PROJECT_O82 = 11,
	HARDWARE_PROJECT_O16U = 12,
	HARDWARE_PROJECT_P16U = 14,
};

const char *product_name_get(void);
uint32_t get_hw_project_adc(void);
uint32_t get_hw_build_adc(void);
uint32_t get_hw_version_platform(void);
uint32_t get_hw_id_value(void);
uint32_t get_hw_country_version(void);
uint32_t get_hw_version_major(void);
uint32_t get_hw_version_minor(void);
uint32_t get_hw_version_build(void);

#endif /* _XIAOMI_HWID_H */
