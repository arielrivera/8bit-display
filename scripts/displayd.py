#!/usr/bin/env python3
"""Run the local 8bit-display controller."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from matrix_display.backends import make_backend
from matrix_display.config import load_config
from matrix_display.controller import DisplayController


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("config.example.yaml"))
    parser.add_argument("--backend", choices=["dry-run", "serial", "native-ble", "swift-ble"])
    parser.add_argument("--once", action="store_true", help="send one update and exit")
    parser.add_argument("--show-packets", action="store_true", help="print packet hex in dry-run mode")
    args = parser.parse_args()

    config = load_config(args.config)
    backend_name = args.backend or config.device.backend
    backend = make_backend(backend_name, config.device.name, show_packets=args.show_packets)
    controller = DisplayController(config, backend)

    if args.once:
        controller.run_once()
    else:
        controller.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
