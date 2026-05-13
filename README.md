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

## Current Goal

Run a local controller that can update the display from a folder, a selected
image, or a generated clock image.

## Local Controller

Create a virtual environment and install dependencies:

```sh
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Generate sample images and build the native macOS BLE helper:

```sh
.venv/bin/python scripts/make_sample_images.py
scripts/build_native.sh
```

Create a local config you can edit without committing machine-specific changes:

```sh
cp config.local.example.yaml config.local.yaml
```

Run one dry-run update:

```sh
.venv/bin/python scripts/displayd.py --config config.local.yaml --backend dry-run --once --show-packets
```

Send one image to the display:

```sh
.venv/bin/python scripts/displayd.py --config config.single.example.yaml --backend native-ble --once
```

Run the daemon loop:

```sh
.venv/bin/python scripts/displayd.py --config config.local.yaml
```

Modes are configured in `config.local.yaml`:

- `carousel`: sends each image in `paths.image_folder` sequentially.
- `single`: sends `mode.single_image` and re-sends when that file changes.
- `clock`: generates a new clock image each minute.

Example configs:

- `config.example.yaml`: carousel mode.
- `config.local.example.yaml`: local machine template.
- `config.single.example.yaml`: single-image mode.
- `config.clock.example.yaml`: clock mode.
- `config.clock-pixel-art.example.yaml`: stylized analog clock mode.

Backends:

- `dry-run`: prints packet info without touching Bluetooth.
- `serial`: diagnostic only; the macOS pseudo-port did not visibly update the
  display in local tests.
- `native-ble`: macOS CoreBluetooth backend. This is the working path on this
  Mac.

Build the native macOS BLE helper:

```sh
scripts/build_native.sh
```

The helper is packaged as a small macOS `.app` so Bluetooth privacy permission
works correctly. The first run may prompt for Bluetooth access.

Send one image through the native BLE backend:

```sh
.venv/bin/python scripts/displayd.py --config config.single.example.yaml --backend native-ble --once
```

## Run at Login

Install the macOS LaunchAgent:

```sh
scripts/install_launch_agent.sh
```

The installer:

- creates `config.local.yaml` from `config.local.example.yaml` if needed;
- builds `build/BLEWritePackets.app`;
- creates `~/Library/LaunchAgents/org.arielrivera.8bit-display.plist`;
- starts the controller immediately;
- writes logs to `logs/displayd.out.log` and `logs/displayd.err.log`.

Check service status:

```sh
launchctl print gui/$(id -u)/org.arielrivera.8bit-display
```

Restart after editing `config.local.yaml`:

```sh
launchctl kickstart -k gui/$(id -u)/org.arielrivera.8bit-display
```

Stop without uninstalling:

```sh
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/org.arielrivera.8bit-display.plist
```

## Uninstall

Unload and remove the LaunchAgent:

```sh
scripts/uninstall_launch_agent.sh
```

Optional full local cleanup:

```sh
rm -rf build logs .venv .venv312
rm -f config.local.yaml state.json
```

To remove the repository too:

```sh
cd ..
rm -rf 8bit-display
```

The uninstall script intentionally leaves project files, `config.local.yaml`,
logs, virtual environments, and build artifacts in place so it does not delete
anything you may want to inspect or reuse.

## Quick connection check

With the device paired and connected in macOS Bluetooth settings:

```sh
python3 scripts/probe_serial.py
```

This serial path was useful for diagnostics, but visible display updates now go
through BLE GATT with the `native-ble` backend.

## Generate a test image command sequence

This prints the packets without writing to the display:

```sh
python3 scripts/send_test_pattern.py
```

This sends a temporary 16x16 gradient over the diagnostic serial path, which did
not visibly update this display in local tests:

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
pseudo-port. Python BLE currently crashes on this macOS setup, so the local
controller uses the native CoreBluetooth helper above.

Python BLE diagnostic scripts are kept here for comparison:

```sh
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 scripts/ble_scan.py
python3 scripts/ble_send_test_pattern.py --send
```

You can also generate serial diagnostic packets for a solid color:

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
