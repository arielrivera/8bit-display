#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$ROOT/build"
mkdir -p "$ROOT/build/BLEWritePackets.app/Contents/MacOS"

clang \
  -fobjc-arc \
  -framework Foundation \
  -framework CoreBluetooth \
  -sectcreate __TEXT __info_plist "$ROOT/native/Info.plist" \
  "$ROOT/native/BLEWritePackets.m" \
  -o "$ROOT/build/BLEWritePackets.app/Contents/MacOS/BLEWritePackets"

cp "$ROOT/native/Info.plist" "$ROOT/build/BLEWritePackets.app/Contents/Info.plist"
codesign --force --sign - "$ROOT/build/BLEWritePackets.app" >/dev/null
ln -sf "$ROOT/build/BLEWritePackets.app/Contents/MacOS/BLEWritePackets" "$ROOT/build/BLEWritePackets"

echo "built $ROOT/build/BLEWritePackets.app"
