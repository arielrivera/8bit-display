#!/usr/bin/env python3
"""Send a generated test image to the Matrix Display.

Dry-run is the default. Add --send to actually write to the Bluetooth serial
port and change what the panel displays.
"""

from __future__ import annotations

import argparse
import os
import sys
import termios
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from matrix_display.protocol import gradient_pixels, image_packets, solid_pixels


DEFAULT_PORT = "/dev/cu.MIMatrixDisplay"


def parse_color(value: str) -> tuple[int, int, int]:
    parts = value.split(",")
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("color must be R,G,B")
    try:
        r, g, b = [int(part) for part in parts]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("color must use integer channels") from exc
    if any(channel < 0 or channel > 255 for channel in (r, g, b)):
        raise argparse.ArgumentTypeError("color channels must be 0..255")
    return r, g, b


def write_packets(port: str, packets: list[bytes], delay: float) -> None:
    fd = os.open(port, os.O_RDWR | os.O_NOCTTY)
    try:
        attrs = termios.tcgetattr(fd)
        attrs[4] = termios.B9600
        attrs[5] = termios.B9600
        attrs[2] = attrs[2] | termios.CLOCAL | termios.CREAD
        attrs[2] = attrs[2] & ~termios.PARENB
        attrs[2] = attrs[2] & ~termios.CSTOPB
        attrs[2] = attrs[2] & ~termios.CSIZE
        attrs[2] = attrs[2] | termios.CS8
        termios.tcsetattr(fd, termios.TCSANOW, attrs)

        for i, packet in enumerate(packets, start=1):
            os.write(fd, packet)
            termios.tcdrain(fd)
            print(f"sent packet {i}/{len(packets)}: {len(packet)} bytes")
            time.sleep(delay)
    finally:
        os.close(fd)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--pattern", choices=["gradient", "solid"], default="gradient")
    parser.add_argument("--color", type=parse_color, default=(255, 0, 0), help="solid color as R,G,B")
    parser.add_argument("--gamma", type=float, default=0.6)
    parser.add_argument("--delay", type=float, default=0.05, help="seconds between packets")
    parser.add_argument("--send", action="store_true", help="actually write to the display")
    args = parser.parse_args()

    pixels = gradient_pixels() if args.pattern == "gradient" else solid_pixels(*args.color)
    packets = image_packets(pixels, gamma=args.gamma)

    if not args.send:
        print("dry run only; add --send to write to the display")
        for i, packet in enumerate(packets, start=1):
            print(f"{i:02d}: {packet.hex(' ')}")
        return 0

    write_packets(args.port, packets, args.delay)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
