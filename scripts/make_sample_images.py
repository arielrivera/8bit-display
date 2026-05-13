#!/usr/bin/env python3
"""Create a few local sample images for dry-run/manual testing."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "images"


def save_gradient() -> None:
    image = Image.new("RGB", (16, 16))
    pixels = []
    for y in range(16):
        for x in range(16):
            pixels.append((x * 17, y * 17, ((x + y) // 2) * 17))
    image.putdata(pixels)
    image.save(IMAGES / "sample-gradient.png")


def save_heart() -> None:
    image = Image.new("RGB", (16, 16), (0, 0, 0))
    draw = ImageDraw.Draw(image)
    rows = [
        "0000110001100000",
        "0001111011110000",
        "0011111111111000",
        "0111111111111100",
        "0111111111111100",
        "0011111111111000",
        "0001111111110000",
        "0000111111100000",
        "0000011111000000",
        "0000001110000000",
        "0000000100000000",
    ]
    for y, row in enumerate(rows, start=2):
        for x, value in enumerate(row):
            if value == "1":
                draw.point((x, y), fill=(255, 30, 45))
    image.save(IMAGES / "sample-heart.png")


def main() -> int:
    IMAGES.mkdir(parents=True, exist_ok=True)
    save_gradient()
    save_heart()
    print(f"wrote samples to {IMAGES}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

