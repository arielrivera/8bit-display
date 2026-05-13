#!/usr/bin/env python3
"""Send a single known command over the macOS Bluetooth serial port."""

from __future__ import annotations

import argparse
import os
import sys
import termios
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from matrix_display import protocol


DEFAULT_PORT = "/dev/cu.MIMatrixDisplay"

COMMANDS = {
    "power-off": protocol.POWER_OFF,
    "power-on": protocol.POWER_ON,
    "reset": protocol.RESET,
    "slideshow": protocol.START_SLIDESHOW_MODE,
}


def open_serial(port: str) -> int:
    fd = os.open(port, os.O_RDWR | os.O_NOCTTY)
    attrs = termios.tcgetattr(fd)
    attrs[4] = termios.B9600
    attrs[5] = termios.B9600
    attrs[2] = attrs[2] | termios.CLOCAL | termios.CREAD
    attrs[2] = attrs[2] & ~termios.PARENB
    attrs[2] = attrs[2] & ~termios.CSTOPB
    attrs[2] = attrs[2] & ~termios.CSIZE
    attrs[2] = attrs[2] | termios.CS8
    termios.tcsetattr(fd, termios.TCSANOW, attrs)
    return fd


def send(port: str, command: bytes) -> None:
    fd = open_serial(port)
    try:
        os.write(fd, command)
        termios.tcdrain(fd)
    finally:
        os.close(fd)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=COMMANDS)
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--delay", type=float, default=0.25)
    args = parser.parse_args()

    command = COMMANDS[args.command]
    for i in range(args.repeat):
        send(args.port, command)
        print(f"sent {args.command} {i + 1}/{args.repeat}: {command.hex(' ')}")
        time.sleep(args.delay)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
