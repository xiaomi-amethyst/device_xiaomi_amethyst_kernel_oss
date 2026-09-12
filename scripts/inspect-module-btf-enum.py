#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Read an enum from a module's split BTF (requires pyelftools).

Infer the base-string offset by matching the requested enum name and
validating all locally defined enum/member string boundaries. Ambiguous
matches are rejected rather than guessed.
"""

import argparse
import json
from pathlib import Path
import struct

from elftools.elf.elffile import ELFFile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("module", type=Path)
    parser.add_argument("enum")
    args = parser.parse_args()
    with args.module.open("rb") as stream:
        data = ELFFile(stream).get_section_by_name(".BTF").data()
    magic, version, flags, header, toff, tlen, soff, slen = struct.unpack_from("<HBBIIIII", data)
    assert magic == 0xeb9f and version == 1
    strings = data[header + soff:header + soff + slen]
    local = {}
    offset = 0
    while offset < len(strings):
        end = strings.index(b"\0", offset)
        local[offset] = strings[offset:end].decode()
        offset = end + 1
    anchors = [offset for offset, name in local.items() if name == args.enum]
    assert len(anchors) == 1, "Enum name not uniquely present in local BTF strings"
    enums = []
    offset = header + toff
    while offset < header + toff + tlen:
        name, info, size = struct.unpack_from("<III", data, offset)
        kind, count = (info >> 24) & 31, info & 0xffff
        offset += 12
        if kind == 6:
            entries = [struct.unpack_from("<Ii", data, offset + i * 8) for i in range(count)]
            enums.append((name, entries))
        extra = {1: 4, 2: 0, 3: 12, 4: count * 12, 5: count * 12,
                 6: count * 8, 7: 0, 8: 0, 9: 0, 10: 0, 11: 0, 12: 0,
                 13: count * 8, 14: 4, 15: count * 12, 16: 0, 17: 4,
                 18: 0, 19: count * 12}[kind]
        offset += extra
    candidates = []
    for name, entries in enums:
        base = name - anchors[0]
        if all(n - base in local and local[n - base]
               for enum_name, members in enums
               for n in [enum_name, *(member[0] for member in members)]):
            candidates.append((base, entries))
    assert len(candidates) == 1, "Cannot uniquely infer split-BTF string base"
    base, entries = candidates[0]
    print(json.dumps({"enum": args.enum, "base_string_offset": base,
                      "values": {local[name - base]: value for name, value in entries}}, indent=2))


if __name__ == "__main__":
    main()
