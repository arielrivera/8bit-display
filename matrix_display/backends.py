"""Packet delivery backends for the Matrix Display controller."""

from __future__ import annotations

import os
import subprocess
import tempfile
import termios
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class DisplayBackend(Protocol):
    def send_packets(self, packets: list[bytes]) -> None:
        """Send already-built Matrix Display packets."""


@dataclass
class DryRunBackend:
    """Print packets instead of sending them."""

    show_packets: bool = False

    def send_packets(self, packets: list[bytes]) -> None:
        total_bytes = sum(len(packet) for packet in packets)
        print(f"dry-run: {len(packets)} packets, {total_bytes} bytes")
        if self.show_packets:
            for i, packet in enumerate(packets, start=1):
                print(f"{i:02d}: {packet.hex(' ')}")


@dataclass
class SerialBackend:
    """Diagnostic macOS Bluetooth serial backend.

    Local testing showed this pseudo-port accepts bytes but did not visibly
    update the display. Keep it around for diagnostics, but prefer BLE.
    """

    port: str = "/dev/cu.MIMatrixDisplay"
    packet_delay: float = 0.05

    def send_packets(self, packets: list[bytes]) -> None:
        fd = os.open(self.port, os.O_RDWR | os.O_NOCTTY)
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

            for packet in packets:
                os.write(fd, packet)
                termios.tcdrain(fd)
                time.sleep(self.packet_delay)
        finally:
            os.close(fd)


@dataclass
class SwiftBLEBackend:
    """Call the native Swift/CoreBluetooth helper to write packets.

    This is the intended macOS backend once local Command Line Tools can build
    CoreBluetooth Swift code.
    """

    helper_path: Path = Path("swift/BLEWritePackets.swift")
    device_name: str = "MI Matrix Display"
    packet_delay: float = 0.05

    def send_packets(self, packets: list[bytes]) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".packets", delete=False) as packet_file:
            for packet in packets:
                packet_file.write(packet.hex())
                packet_file.write("\n")
            packet_path = packet_file.name

        try:
            subprocess.run(
                [
                    "swift",
                    str(self.helper_path),
                    "--send",
                    "--name",
                    self.device_name,
                    "--delay",
                    str(self.packet_delay),
                    "--packets",
                    packet_path,
                ],
                check=True,
            )
        finally:
            Path(packet_path).unlink(missing_ok=True)


def make_backend(kind: str, device_name: str, show_packets: bool = False) -> DisplayBackend:
    if kind == "dry-run":
        return DryRunBackend(show_packets=show_packets)
    if kind == "serial":
        return SerialBackend()
    if kind == "swift-ble":
        return SwiftBLEBackend(device_name=device_name)
    raise ValueError(f"unknown backend {kind!r}")

