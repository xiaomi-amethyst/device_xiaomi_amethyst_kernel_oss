// SPDX-License-Identifier: GPL-2.0-only
/*
 * Xiaomi hardware identification, reconstructed from the Amethyst stock
 * hwid.ko interface. See HWID-PREBUILT.md for provenance and ABI evidence.
 */

#include <linux/init.h>
#include <linux/kernel.h>
#include <linux/kobject.h>
#include <linux/module.h>
#include <linux/moduleparam.h>
#include <linux/sysfs.h>
#include <soc/qcom/socinfo.h>

#include "hwid.h"

static unsigned int hwid_value;
static unsigned int project;
static unsigned int build_adc;
static unsigned int project_adc;

module_param(hwid_value, uint, 0444);
MODULE_PARM_DESC(hwid_value, "Xiaomi encoded hardware revision and country");
module_param(project, uint, 0444);
MODULE_PARM_DESC(project, "Xiaomi project identifier");
module_param(build_adc, uint, 0444);
MODULE_PARM_DESC(build_adc, "Build resistance ADC value");
module_param(project_adc, uint, 0444);
MODULE_PARM_DESC(project_adc, "Project resistance ADC value");

static struct kobject *hwid_kobj;

const char *product_name_get(void)
{
	static const char * const sm8450[] = {
		"zeus", "cupid", "katyusha", "ingres", "zizhan", "thor",
		"loki", "unicorn", "ziyi", "diting", "caiwei", "mayfly",
	};
	static const char * const sm8550[] = {
		"nuwa", "fuxi", "wangshu", "socrates", "ishtar", "babylon",
	};
	static const char * const sm8650[] = {
		"shennong", "houji", "manet", "aurora", "suiren", "ruyi",
		"goku", "unknown", "unknown", "unknown", "unknown", "unknown",
		"zorn",
	};
	static const char * const sm8635[] = {
		"peridot", "chenfeng", "muyu", "uke",
	};

	switch (socinfo_get_id()) {
	case 457:
		if (project >= 1 && project <= ARRAY_SIZE(sm8450))
			return sm8450[project - 1];
		break;
	case 519:
		if (project >= 1 && project <= ARRAY_SIZE(sm8550))
			return sm8550[project - 1];
		break;
	case 557:
		if (project >= 1 && project <= ARRAY_SIZE(sm8650))
			return sm8650[project - 1];
		break;
	case 614:
		if (project >= 8 && project - 8 < ARRAY_SIZE(sm8635))
			return sm8635[project - 8];
		break;
	case 636:
		if (project == HARDWARE_PROJECT_O16U)
			return "amethyst";
		if (project == HARDWARE_PROJECT_P16U)
			return "flourite";
		break;
	}

	return "unknown";
}
EXPORT_SYMBOL(product_name_get);

uint32_t get_hw_project_adc(void)
{
	return project_adc;
}
EXPORT_SYMBOL(get_hw_project_adc);

uint32_t get_hw_build_adc(void)
{
	return build_adc;
}
EXPORT_SYMBOL(get_hw_build_adc);

uint32_t get_hw_version_platform(void)
{
	return project;
}
EXPORT_SYMBOL(get_hw_version_platform);

uint32_t get_hw_id_value(void)
{
	return hwid_value;
}
EXPORT_SYMBOL(get_hw_id_value);

uint32_t get_hw_country_version(void)
{
	return hwid_value >> 20;
}
EXPORT_SYMBOL(get_hw_country_version);

uint32_t get_hw_version_major(void)
{
	return hwid_value >> 16;
}
EXPORT_SYMBOL(get_hw_version_major);

uint32_t get_hw_version_minor(void)
{
	return hwid_value & 0xffff;
}
EXPORT_SYMBOL(get_hw_version_minor);

uint32_t get_hw_version_build(void)
{
	return (hwid_value >> 16) & 0xf;
}
EXPORT_SYMBOL(get_hw_version_build);

static ssize_t hwid_project_show(struct kobject *kobj,
				struct kobj_attribute *attr, char *buf)
{
	return sysfs_emit(buf, "0x%x\n", project);
}

static ssize_t hwid_value_show(struct kobject *kobj,
			      struct kobj_attribute *attr, char *buf)
{
	return sysfs_emit(buf, "0x%x\n", hwid_value);
}

static ssize_t hwid_project_adc_show(struct kobject *kobj,
				    struct kobj_attribute *attr, char *buf)
{
	return sysfs_emit(buf, "%d\n", (int)project_adc);
}

static ssize_t hwid_build_adc_show(struct kobject *kobj,
				  struct kobj_attribute *attr, char *buf)
{
	return sysfs_emit(buf, "%d\n", (int)build_adc);
}

static struct kobj_attribute hwid_project_attr = __ATTR_RO(hwid_project);
static struct kobj_attribute hwid_value_attr = __ATTR_RO(hwid_value);
static struct kobj_attribute hwid_project_adc_attr = __ATTR_RO(hwid_project_adc);
static struct kobj_attribute hwid_build_adc_attr = __ATTR_RO(hwid_build_adc);

static struct attribute *hwid_attrs[] = {
	&hwid_project_attr.attr,
	&hwid_value_attr.attr,
	&hwid_project_adc_attr.attr,
	&hwid_build_adc_attr.attr,
	NULL,
};

static const struct attribute_group hwid_attr_group = {
	.attrs = hwid_attrs,
};

static int __init hwid_init(void)
{
	int ret;

	hwid_kobj = kobject_create_and_add("hwid", NULL);
	if (!hwid_kobj)
		return -ENOMEM;

	ret = sysfs_create_group(hwid_kobj, &hwid_attr_group);
	if (ret) {
		kobject_put(hwid_kobj);
		hwid_kobj = NULL;
	}

	return ret;
}

static void __exit hwid_exit(void)
{
	sysfs_remove_group(hwid_kobj, &hwid_attr_group);
	kobject_put(hwid_kobj);
}

module_init(hwid_init);
module_exit(hwid_exit);

MODULE_DESCRIPTION("Xiaomi hardware identification");
MODULE_LICENSE("GPL v2");
