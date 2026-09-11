#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Compare compiled hwid getters with stock AArch64 code using Unicorn.

Requires pyelftools and unicorn. Tests the exported getters/product lookup,
not kernel module loading or the sysfs lifecycle.
"""

import argparse
from pathlib import Path
import random
import re
import struct

from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM
from unicorn.arm64_const import UC_ARM64_REG_X0, UC_ARM64_REG_X30, UC_ARM64_REG_SP, UC_ARM64_REG_PC


class Module:
    SOCINFO = 0x2000000
    STOP = 0x2001000
    STACK = 0x3000000

    def __init__(self, path):
        self.uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        self.symbols = {}
        with path.open("rb") as stream:
            elf = ELFFile(stream)
            assert elf["e_machine"] == "EM_AARCH64"
            table = elf.get_section_by_name(".symtab")
            addresses = {}
            cursor = 0x1000000
            for index, section in enumerate(elf.iter_sections()):
                if not section["sh_flags"] & 2 or not section["sh_size"]:
                    continue
                size = (section["sh_size"] + 4095) & ~4095
                addresses[index] = cursor
                self.uc.mem_map(cursor, size)
                self.uc.mem_write(cursor, section.data())
                cursor += size

            def address(symbol):
                index = symbol["st_shndx"]
                if index == "SHN_UNDEF":
                    if symbol.name == "socinfo_get_id":
                        return self.SOCINFO
                    # Other external calls must fail if accidentally reached.
                    return 0x5000000
                if index == "SHN_ABS":
                    return symbol["st_value"]
                return addresses.get(index, 0) + symbol["st_value"]

            for symbol in table.iter_symbols():
                if symbol.name:
                    self.symbols[symbol.name] = address(symbol)
            for section in elf.iter_sections():
                if section["sh_type"] != "SHT_RELA" or section["sh_info"] not in addresses:
                    continue
                for relocation in section.iter_relocations():
                    place = addresses[section["sh_info"]] + relocation["r_offset"]
                    value = address(table.get_symbol(relocation["r_info_sym"])) + relocation["r_addend"]
                    kind = relocation["r_info_type"]
                    if kind == 257:  # ABS64
                        self.uc.mem_write(place, struct.pack("<Q", value))
                        continue
                    if kind in (258, 261):  # ABS32, PREL32
                        result = value if kind == 258 else value - place
                        self.uc.mem_write(place, struct.pack("<I", result & 0xffffffff))
                        continue
                    instruction = self.u32(place)
                    if kind == 275:  # ADR_PREL_PG_HI21
                        immediate = ((value >> 12) - (place >> 12)) & 0x1fffff
                        instruction = (instruction & ~0x60ffffe0) | ((immediate & 3) << 29) | ((immediate >> 2) << 5)
                    elif kind in (277, 278, 284, 285, 286):
                        shift = {277: 0, 278: 0, 284: 1, 285: 2, 286: 3}[kind]
                        instruction = (instruction & ~0x3ffc00) | (((value & 0xfff) >> shift) << 10)
                    elif kind in (282, 283):  # JUMP26, CALL26
                        instruction = (instruction & ~0x3ffffff) | (((value - place) >> 2) & 0x3ffffff)
                    else:
                        raise ValueError("Unsupported AArch64 relocation: {}".format(kind))
                    self.uc.mem_write(place, struct.pack("<I", instruction))
        self.uc.mem_map(self.SOCINFO, 8192)
        self.uc.mem_map(self.STACK, 65536)

    def u32(self, address):
        return struct.unpack("<I", self.uc.mem_read(address, 4))[0]

    def set_value(self, name, value):
        self.uc.mem_write(self.symbols[name], struct.pack("<I", value))

    def call(self, name, soc=636):
        # movz w0, #soc; ret -- only permitted external call in the getters.
        self.uc.mem_write(self.SOCINFO, struct.pack("<II", 0x52800000 | (soc << 5), 0xd65f03c0))
        self.uc.ctl_remove_cache(self.SOCINFO, self.SOCINFO + 8)
        self.uc.reg_write(UC_ARM64_REG_SP, self.STACK + 65520)
        self.uc.reg_write(UC_ARM64_REG_X30, self.STOP)
        self.uc.emu_start(self.symbols[name], self.STOP, count=10000)
        assert self.uc.reg_read(UC_ARM64_REG_PC) == self.STOP, "Getter failed to return"
        result = self.uc.reg_read(UC_ARM64_REG_X0)
        if name == "product_name_get":
            return bytes(self.uc.mem_read(result, 32)).split(b"\0", 1)[0]
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stock", type=Path)
    parser.add_argument("rebuilt_object", type=Path)
    args = parser.parse_args()
    stock, rebuilt = Module(args.stock), Module(args.rebuilt_object)
    cmdfile = args.rebuilt_object.with_name("." + args.rebuilt_object.name + ".cmd")
    crcs = dict(re.findall(r"^#SYMVER (\w+) (0x[0-9a-f]+)$", cmdfile.read_text(), re.MULTILINE))
    exports = sorted(name[len("__crc_"):] for name in stock.symbols if name.startswith("__crc_"))
    assert len(exports) == 9 and set(exports) == set(crcs)
    for name in exports:
        assert stock.u32(stock.symbols["__crc_" + name]) == int(crcs[name], 16), name + " CRC mismatch"
        assert stock.u32(stock.symbols[name] - 4) == rebuilt.u32(rebuilt.symbols[name] - 4), name + " KCFI mismatch"
    print("PASS: all 9 export CRCs and KCFI type IDs match")

    rng = random.Random(7635)
    vectors = [0, 1, 0xffff, 0x10000, 0xf0000, 0x100000, 0x200000, 0xffffffff]
    vectors += [rng.getrandbits(32) for _ in range(256)]
    getters = [name for name in exports if name != "product_name_get"]
    for value in vectors:
        for variable in ("hwid_value", "project", "project_adc", "build_adc"):
            stock.set_value(variable, value)
            rebuilt.set_value(variable, value)
        for name in getters:
            assert stock.call(name) == rebuilt.call(name), (name, hex(value))
    print("PASS: 8 integer getters across {} boundary/random inputs".format(len(vectors)))

    combinations = 0
    for soc in (0, 457, 519, 557, 614, 636, 640, 641, 657, 658, 65535):
        for project in list(range(33)) + [0xffffffff]:
            stock.set_value("project", project)
            rebuilt.set_value("project", project)
            assert stock.call("product_name_get", soc) == rebuilt.call("product_name_get", soc), (soc, project)
            combinations += 1
    print("PASS: product lookup across {} SoC/project combinations".format(combinations))


if __name__ == "__main__":
    main()
