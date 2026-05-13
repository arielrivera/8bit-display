#!/usr/bin/env bash
set -euo pipefail

LABEL="org.arielrivera.8bit-display"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
rm -f "$PLIST"

echo "Uninstalled $LABEL LaunchAgent"
echo "Project files, config.local.yaml, logs, .venv, and build artifacts were left in place."
echo "Remove them manually if you want a full cleanup."

