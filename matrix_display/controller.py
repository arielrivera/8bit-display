"""Local display controller modes."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from PIL import Image

from matrix_display.backends import DisplayBackend
from matrix_display.clock import clock_image
from matrix_display.config import AppConfig
from matrix_display.image_tools import image_to_pixels, load_display_image
from matrix_display.protocol import image_packets

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}


@dataclass
class DisplayState:
    mode: str
    last_sent: str
    sent_at: str


def list_images(folder: Path) -> list[Path]:
    if not folder.exists():
        folder.mkdir(parents=True, exist_ok=True)
    return sorted(path for path in folder.iterdir() if path.suffix.lower() in IMAGE_EXTENSIONS and path.is_file())


class DisplayController:
    def __init__(self, config: AppConfig, backend: DisplayBackend):
        self.config = config
        self.backend = backend

    def send_image(self, image: Image.Image, label: str) -> None:
        pixels = image_to_pixels(image)
        packets = image_packets(pixels, gamma=self.config.device.gamma)
        self.backend.send_packets(packets)
        self.write_state(label)

    def send_file(self, path: Path) -> None:
        self.send_image(load_display_image(path), str(path))

    def write_state(self, last_sent: str) -> None:
        state = DisplayState(
            mode=self.config.mode.type,
            last_sent=last_sent,
            sent_at=datetime.now().isoformat(timespec="seconds"),
        )
        self.config.paths.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.config.paths.state_file.write_text(json.dumps(asdict(state), indent=2), encoding="utf-8")

    def run_once(self) -> None:
        mode = self.config.mode.type
        if mode == "carousel":
            images = list_images(self.config.paths.image_folder)
            if not images:
                print(f"no images found in {self.config.paths.image_folder}")
                return
            self.send_file(images[0])
            return
        if mode == "single":
            self.send_file(self.config.mode.single_image)
            return
        if mode == "clock":
            now = datetime.now()
            image = clock_image(self.config.mode.clock_style, now, clock_24h=self.config.mode.clock_24h)
            self.send_image(image, f"clock:{self.config.mode.clock_style}:{now:%Y-%m-%d %H:%M}")
            return
        raise ValueError(f"unknown mode {mode!r}")

    def run_forever(self) -> None:
        mode = self.config.mode.type
        if mode == "carousel":
            self._run_carousel()
            return
        if mode == "single":
            self._run_single()
            return
        if mode == "clock":
            self._run_clock()
            return
        raise ValueError(f"unknown mode {mode!r}")

    def _run_carousel(self) -> None:
        index = 0
        while True:
            images = list_images(self.config.paths.image_folder)
            if not images:
                print(f"no images found in {self.config.paths.image_folder}; sleeping")
                time.sleep(10)
                continue

            path = images[index % len(images)]
            print(f"carousel: sending {path}")
            self.send_file(path)
            index += 1
            time.sleep(self.config.mode.carousel_seconds)

    def _run_single(self) -> None:
        path = self.config.mode.single_image
        last_mtime: float | None = None
        while True:
            if not path.exists():
                print(f"single image does not exist: {path}")
                time.sleep(10)
                continue

            mtime = path.stat().st_mtime
            if last_mtime != mtime:
                print(f"single: sending {path}")
                self.send_file(path)
                last_mtime = mtime
            time.sleep(5)

    def _run_clock(self) -> None:
        last_minute = None
        while True:
            now = datetime.now()
            minute_key = now.strftime("%Y-%m-%d %H:%M")
            if minute_key != last_minute:
                print(f"clock: sending {minute_key}")
                image = clock_image(self.config.mode.clock_style, now, clock_24h=self.config.mode.clock_24h)
                self.send_image(image, f"clock:{self.config.mode.clock_style}:{minute_key}")
                last_minute = minute_key
            time.sleep(1)

