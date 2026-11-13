"""Package an RP2040 application binary as UF2."""
import argparse
from pathlib import Path
import struct

FLASH_BASE = 0x10000000
FIRMWARE_LIMIT = 0x1DE000
RP2040_FAMILY = 0xE48BFF56
PAYLOAD_SIZE = 256


def convert(data):
    if not 0 < len(data) <= FIRMWARE_LIMIT:
        raise ValueError("Firmware must fit before the song partition")
    count = (len(data) + PAYLOAD_SIZE - 1) // PAYLOAD_SIZE
    blocks = []
    for index in range(count):
        offset = index * PAYLOAD_SIZE
        payload = data[offset:offset + PAYLOAD_SIZE].ljust(PAYLOAD_SIZE, b"\0")
        header = struct.pack("<8I", 0x0A324655, 0x9E5D5157, 0x2000,
                             FLASH_BASE + offset, PAYLOAD_SIZE, index, count, RP2040_FAMILY)
        blocks.append(header + payload.ljust(476, b"\0") + struct.pack("<I", 0x0AB16F30))
    return b"".join(blocks)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.write_bytes(convert(args.input.read_bytes()))
    print("UF2: " + str(args.output))


if __name__ == "__main__":
    main()
