# 8bit-display

Tools and notes for controlling a Merkury Innovations / MI Matrix Display
from a Mac.

## What we know

- Product: Merkury Innovations Multicolor Matrix LED Display
- Official app: Matrix Panel Plus, formerly MI Matrix Display
- Display: 16x16 color LED matrix
- macOS Bluetooth serial port: `/dev/cu.MIMatrixDisplay`
- USB appears to be power-only on this Mac; it did not expose a usable serial
  device.

## Current goal

Discover the serial protocol used by the official app, then build scripts that
can upload images, text, and animations from a computer.

## Quick connection check

With the device paired and connected in macOS Bluetooth settings:

```sh
python3 scripts/probe_serial.py
```

The first milestone is simply opening the serial port reliably. Sending display
commands comes after the protocol is understood.

## Generate a test image command sequence

This prints the packets without writing to the display:

```sh
python3 scripts/send_test_pattern.py
```

This sends a temporary 16x16 gradient to the display:

```sh
python3 scripts/send_test_pattern.py --send
```

If the display does not visibly change, test whether the macOS serial port is
actually connected to the display command channel:

```sh
python3 scripts/serial_command.py power-off
python3 scripts/serial_command.py power-on
```

The known working implementations use BLE GATT rather than the macOS serial
pseudo-port. To test that path:

```sh
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 scripts/ble_scan.py
python3 scripts/ble_send_test_pattern.py --send
```

If Python BLE crashes on macOS, use the native Swift/CoreBluetooth sender:

```sh
swift swift/BLESendTestPattern.swift --send
```

You can also send a solid color:

```sh
python3 scripts/send_test_pattern.py --pattern solid --color 255,0,0 --send
```

## Recommended reverse engineering path

1. Validate that the serial port accepts the same packets documented by the BLE
   implementations.
2. Add PNG/JPG import and resize to 16x16.
3. Add animation/slideshow support.
4. Add scheduling or a small desktop/web controller.

## References

- https://github.com/offe/mi-led-display
- https://github.com/LostBeard/SpawnDev.MatrixLEDDisplay
- https://lostbeard.github.io/SpawnDev.MatrixLEDDisplay/
