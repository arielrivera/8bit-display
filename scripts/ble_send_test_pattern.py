#!/usr/bin/env python3
"""Send a generated test image using BLE GATT writes.

This uses the same service/characteristic path as the working Web Bluetooth
implementations.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bleak import BleakClient, BleakScanner

from matrix_display.protocol import (
    POWER_OFF,
    POWER_ON,
    gradient_pixels,
    image_packets,
    solid_pixels,
)


SERVICE_UUID = "0000ffd0-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_UUID = "0000ffd1-0000-1000-8000-00805f9b34fb"
DEFAULT_NAME = "MI Matrix Display"


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


async def find_device(name: str, address: str | None):
    if address:
        return address

    print(f"scanning for {name!r} advertising service {SERVICE_UUID}...")
    devices = await BleakScanner.discover(timeout=8, service_uuids=[SERVICE_UUID])
    if not devices:
        devices = await BleakScanner.discover(timeout=8)

    for device in devices:
        print(f"found: name={device.name!r} address={device.address}")
        if device.name == name or (device.name and "Matrix" in device.name):
            return device.address

    raise RuntimeError(f"could not find BLE device named {name!r}")


async def write_packets(address: str, packets: list[bytes], delay: float) -> None:
    async with BleakClient(address) as client:
        print(f"connected: {client.is_connected}")
        for i, packet in enumerate(packets, start=1):
            await client.write_gatt_char(CHARACTERISTIC_UUID, packet, response=False)
            print(f"sent packet {i}/{len(packets)}: {len(packet)} bytes")
            await asyncio.sleep(delay)


async def main_async(args: argparse.Namespace) -> int:
    address = await find_device(args.name, args.address)

    if args.command == "power-off":
        packets = [POWER_OFF]
    elif args.command == "power-on":
        packets = [POWER_ON]
    else:
        pixels = gradient_pixels() if args.pattern == "gradient" else solid_pixels(*args.color)
        packets = image_packets(pixels, gamma=args.gamma)

    if not args.send:
        print("dry run only; add --send to write to the display")
        print(f"target address: {address}")
        for i, packet in enumerate(packets, start=1):
            print(f"{i:02d}: {packet.hex(' ')}")
        return 0

    await write_packets(address, packets, args.delay)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", default=DEFAULT_NAME)
    parser.add_argument("--address", help="BLE address/id from a prior scan")
    parser.add_argument("--command", choices=["image", "power-off", "power-on"], default="image")
    parser.add_argument("--pattern", choices=["gradient", "solid"], default="gradient")
    parser.add_argument("--color", type=parse_color, default=(255, 0, 0), help="solid color as R,G,B")
    parser.add_argument("--gamma", type=float, default=0.6)
    parser.add_argument("--delay", type=float, default=0.05)
    parser.add_argument("--send", action="store_true", help="actually write to the display")
    args = parser.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())

