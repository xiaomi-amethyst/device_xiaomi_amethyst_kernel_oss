#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Extract hwid module metadata, export CRCs, KCFI IDs, and disassembly."""

import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess


def inspect(module):
    data = module.read_bytes()
    if data[:6] != b"\x7fELF\x02\x01" or struct.unpack_from("<H", data, 18)[0] != 183:
        raise ValueError("Expected a little-endian ELF64 AArch64 module")
    shoff = struct.unpack_from("<Q", data, 40)[0]
    shentsize, shnum, shstrndx = struct.unpack_from("<HHH", data, 58)
    headers = [struct.unpack_from("<IIQQQQIIQQ", data, shoff + i * shentsize)
               for i in range(shnum)]

    def contents(index):
        header = headers[index]
        return data[header[4]:header[4] + header[5]]

    def string(blob, offset):
        return blob[offset:blob.index(b"\0", offset)].decode()

    names = contents(shstrndx)
    sections = {string(names, header[0]): i for i, header in enumerate(headers)}
    symidx = sections[".symtab"]
    strings = contents(headers[symidx][6])
    symbols = {}
    table = contents(symidx)
    for offset in range(0, len(table), headers[symidx][9]):
        name, info, other, section, value, size = struct.unpack_from("<IBBHQQ", table, offset)
        if name:
            symbols[string(strings, name)] = (section, value, size)
    exports = {}
    for name, (section, value, size) in symbols.items():
        if not name.startswith("__crc_"):
            continue
        function = name[len("__crc_"):]
        crc = struct.unpack_from("<I", contents(section), value)[0]
        text_section, entry, length = symbols[function]
        # Android's AArch64 KCFI build places a type ID immediately before
        # each function. This extractor is specific to that module format.
        kcfi = struct.unpack_from("<I", contents(text_section), entry - 4)[0]
        exports[function] = {"crc": "0x{:08x}".format(crc),
                             "kcfi": "0x{:08x}".format(kcfi), "size": length}
    modinfo = contents(sections[".modinfo"]).decode().rstrip("\0").split("\0")
    return {"module": str(module.resolve()), "sha256": hashlib.sha256(data).hexdigest(),
            "modinfo": modinfo, "exports": exports}


def main():
    kernel = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("module", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--kernel", type=Path, help="Also extract the prebuilt Image's embedded config")
    parser.add_argument("--llvm-bin", type=Path,
                        default=kernel.parent / "prebuilts/clang/host/linux-x86/clang-r487747c/bin")
    args = parser.parse_args()
    report = inspect(args.module)
    args.out.mkdir(parents=True, exist_ok=True)
    commands = {
        "disassembly.txt": ["llvm-objdump", "-dr", "--no-show-raw-insn"],
        "relocations.txt": ["llvm-readelf", "-r"],
        "sections.txt": ["llvm-readelf", "-S", "-s", "-p", ".rodata", "-p", ".modinfo",
                         "-x", "__param", "-x", ".data", "-x", "__kcrctab"],
    }
    for filename, command in commands.items():
        with (args.out / filename).open("w") as output:
            subprocess.run([str(args.llvm_bin / command[0]), *command[1:], str(args.module)],
                           stdout=output, check=True)
    if args.kernel:
        config = subprocess.check_output([str(kernel / "scripts/extract-ikconfig"),
                                          str(args.kernel)])
        (args.out / "stock.config").write_bytes(config)
    with (args.out / "hwid.json").open("w") as output:
        json.dump(report, output, indent=2, sort_keys=True)
        output.write("\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
