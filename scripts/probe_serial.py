#!/usr/bin/env python3
"""Open the Matrix Display Bluetooth serial port without sending data."""

from __future__ import annotations

import argparse
import os
import select
import time


DEFAULT_PORT = "/dev/cu.MIMatrixDisplay"


def probe(port: str, seconds: float) -> int:
    fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        print(f"opened {port}")
        deadline = time.monotonic() + seconds
        saw_data = False

        while time.monotonic() < deadline:
            remaining = max(0.0, deadline - time.monotonic())
            readable, _, _ = select.select([fd], [], [], min(0.5, remaining))
            if not readable:
                continue

            chunk = os.read(fd, 4096)
            if not chunk:
                continue

            saw_data = True
            print(f"read {len(chunk)} bytes: {chunk.hex(' ')}")

        if not saw_data:
            print(f"no data received during {seconds:g}s passive read")
        return 0
    finally:
        os.close(fd)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--seconds", type=float, default=3.0)
    args = parser.parse_args()
    return probe(args.port, args.seconds)


if __name__ == "__main__":
    raise SystemExit(main())

