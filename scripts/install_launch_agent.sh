#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABEL="org.arielrivera.8bit-display"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
PYTHON="$ROOT/.venv/bin/python"
CONFIG="$ROOT/config.local.yaml"
LOG_DIR="$ROOT/logs"

if [[ ! -x "$PYTHON" ]]; then
  echo "Missing virtual environment at $ROOT/.venv"
  echo "Create it first:"
  echo "  python3 -m venv .venv"
  echo "  .venv/bin/python -m pip install -r requirements.txt"
  exit 1
fi

if [[ ! -f "$CONFIG" ]]; then
  cp "$ROOT/config.local.example.yaml" "$CONFIG"
  echo "Created $CONFIG from config.local.example.yaml"
fi

"$ROOT/scripts/build_native.sh"
mkdir -p "$HOME/Library/LaunchAgents" "$LOG_DIR"

cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PYTHON</string>
    <string>$ROOT/scripts/displayd.py</string>
    <string>--config</string>
    <string>$CONFIG</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$ROOT</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$LOG_DIR/displayd.out.log</string>
  <key>StandardErrorPath</key>
  <string>$LOG_DIR/displayd.err.log</string>
</dict>
</plist>
PLIST

launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl enable "gui/$(id -u)/$LABEL"
launchctl kickstart -k "gui/$(id -u)/$LABEL"

echo "Installed and started $LABEL"
echo "Config: $CONFIG"
echo "Logs: $LOG_DIR"

