#!/usr/bin/env python3
"""Scan nearby BLE devices and print names/addresses."""

from __future__ import annotations

import asyncio

from bleak import BleakScanner


async def main() -> int:
    devices = await BleakScanner.discover(timeout=10)
    for device in devices:
        print(f"name={device.name!r} address={device.address}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

