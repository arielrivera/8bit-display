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

The recommended unattended transport on macOS is the native CoreBluetooth
backend, which now supports saved still images, animated GIF slideshows,
carousel mode, selected-image mode, and generated clocks. A Chrome Web Bluetooth
controller is also included as an interactive browser-based option.

## Quick Start

0. Clone the repository and enter it:

```sh
git clone https://github.com/arielrivera/8bit-display.git
cd 8bit-display
```

1. Create the Python environment and install dependencies:

```sh
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
```

2. Install the macOS background service:

```sh
scripts/install_launch_agent.sh
```

3. Edit `config.local.yaml` for the mode you want: `carousel`, `single`, or
   `clock`.

4. Put your images in `images/`, or set `mode.single_image` to the file you want
   shown.

5. After changing `config.local.yaml`, restart the controller:

```sh
launchctl kickstart -k gui/$(id -u)/org.arielrivera.8bit-display
```

The installer creates `config.local.yaml` from `config.local.example.yaml` if it
does not already exist.

## That's it !

You should be set on your mac.
Continue reading if you want more details or if you want to get the web based GUI up and running.

## Web UI / Browser Controller

Start the local Web Bluetooth controller server:

```sh
.venv/bin/python scripts/web_displayd.py --config config.local.yaml
```

Open this in Chrome:

```text
http://127.0.0.1:8765
```

Then:

1. click `Connect`;
2. choose `MI Matrix Display`;
3. use `Send now`, `Start`, or `Power off` from the local page.

The browser controller reads the same `config.local.yaml`, image folder, and
clock settings as the Python controller. Keep the Chrome tab open while a mode
is running, because the browser tab is the Bluetooth transport.

Animated GIFs are sent through the display's slideshow mode. The controller uses
up to the first 8 frames, matching the frame count used by the reference web
implementation. This works in both the browser controller and the native
background service.

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
- `native-ble`: macOS CoreBluetooth backend. This is working for power,
  temporary-image writes, and saved still-image writes on this Mac. The helper
  enables notifications and intentionally paces writes to match the timing the
  display expects.

`device.save: true` stores a still image on the panel so it remains visible after
disconnecting. `device.save: false` sends a temporary image that appears briefly
and then returns to whatever image is already stored on the panel.

Verified native modes on this panel:

- `carousel`: rotates saved still images from the configured folder.
- `single`: watches one file and resends it when the file changes.
- `clock`: updates on minute boundaries in both `digital` and `pixel-art`
  styles.

Build the native macOS BLE helper:

```sh
scripts/build_native.sh
```

The helper is packaged as a small macOS `.app` so Bluetooth privacy permission
works correctly. It is marked as a background accessory app, so sends do not add
an icon to the Dock. The first run may prompt for Bluetooth access.

Send one image through the native BLE backend:

```sh
.venv/bin/python scripts/displayd.py --config config.single.example.yaml --backend native-ble --once
```

## Browser Controller

Start the local Web Bluetooth controller server:

```sh
.venv/bin/python scripts/web_displayd.py --config config.local.yaml
```

Open this in Chrome:

```text
http://127.0.0.1:8765
```

Then:

1. click `Connect`;
2. choose `MI Matrix Display`;
3. use `Send now`, `Start`, or `Power off` from the local page.

The browser controller reads the same `config.local.yaml`, image folder, and
clock settings as the Python controller. Keep the Chrome tab open while a mode
is running, because the browser tab is the Bluetooth transport.

The `Advanced Settings` tab can manage the local macOS service without leaving
the browser:

- view LaunchAgent status, PID, run count, and install state;
- install, start, stop, restart, or uninstall the service;
- edit `config.local.yaml` with validation before saving;
- save the config and restart the service in one step;
- inspect project paths and recent service logs.

Animated GIFs are sent through the display's slideshow mode. The controller uses
up to the first 8 frames, matching the frame count used by the reference web
implementation. This works in both the browser controller and the native
background service.

## Run at Login

Install the macOS LaunchAgent:

```sh
scripts/install_launch_agent.sh
```

Run this as your normal logged-in user, not with `sudo`. LaunchAgents belong to
the user's GUI domain; using `sudo` can leave root-owned files behind and prevent
the agent from loading correctly.

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

The browser controller does not install any system files. Stop it with `Ctrl-C`
in the terminal where `scripts/web_displayd.py` is running.

## Image Assets

The carousel scans `paths.image_folder` recursively, so image packs can live in
subfolders under `images/`.

`images/rpg_potions_16x16/` contains extracted 16x16 RPG food and potion tiles
from a CC BY-SA 3.0 asset pack by Bonsaiheldin. See
`images/rpg_potions_16x16/CREDITS.txt` for attribution and license details.

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
pseudo-port. Python BLE currently crashes on this macOS setup, so the browser
controller is the recommended path while the native helper remains experimental.

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
