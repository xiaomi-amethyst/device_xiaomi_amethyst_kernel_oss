#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Compare stock module imports with a rebuilt kernel's Module.symvers.

Requires pyelftools. Unavailable providers and CRC mismatches are reported
separately; this is not a complete module-load or boot compatibility test.
"""

import argparse
import json
from pathlib import Path
import struct

from elftools.elf.elffile import ELFFile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("modules", type=Path)
    parser.add_argument("symvers", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    exports = {}
    for line in args.symvers.read_text().splitlines():
        fields = line.split()
        if len(fields) >= 2:
            exports[fields[1]] = int(fields[0], 16)
    report = {}
    for path in sorted(args.modules.rglob("*.ko")):
        missing, mismatches = [], []
        with path.open("rb") as stream:
            elf = ELFFile(stream)
            assert elf.elfclass == 64 and elf.little_endian
            section = elf.get_section_by_name("__versions")
            if section is None:
                report[str(path.relative_to(args.modules))] = {"status": "no version table"}
                continue
            data = section.data()
            assert len(data) % 64 == 0
            for offset in range(0, len(data), 64):
                crc = struct.unpack_from("<Q", data, offset)[0]
                name = data[offset + 8:offset + 64].split(b"\0", 1)[0].decode()
                if name not in exports:
                    missing.append(name)
                elif exports[name] != crc:
                    mismatches.append({"symbol": name, "stock": "0x{:08x}".format(crc),
                                       "rebuilt": "0x{:08x}".format(exports[name])})
        report[str(path.relative_to(args.modules))] = {
            "missing_providers": missing, "crc_mismatches": mismatches,
        }
    summary = {
        "modules": len(report),
        "with_crc_mismatches": sum(bool(item.get("crc_mismatches")) for item in report.values()),
        "with_missing_providers": sum(bool(item.get("missing_providers")) for item in report.values()),
        "without_version_table": sum("status" in item for item in report.values()),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"summary": summary, "modules": report}, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    for name, item in report.items():
        if item.get("crc_mismatches"):
            print("{}: {}".format(name, ", ".join(
                mismatch["symbol"] for mismatch in item["crc_mismatches"])))
    print("Detailed report: " + str(args.out))
    return int(any(summary[key] for key in summary if key != "modules"))


if __name__ == "__main__":
    raise SystemExit(main())
