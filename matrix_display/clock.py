"""16x16 clock image generation."""

from __future__ import annotations

import math
from datetime import datetime

from PIL import Image, ImageDraw

from matrix_display.protocol import HEIGHT, WIDTH


DIGITS: dict[str, tuple[str, ...]] = {
    "0": ("111", "101", "101", "101", "111"),
    "1": ("010", "110", "010", "010", "111"),
    "2": ("111", "001", "111", "100", "111"),
    "3": ("111", "001", "111", "001", "111"),
    "4": ("101", "101", "111", "001", "001"),
    "5": ("111", "100", "111", "001", "111"),
    "6": ("111", "100", "111", "101", "111"),
    "7": ("111", "001", "010", "010", "010"),
    "8": ("111", "101", "111", "101", "111"),
    "9": ("111", "101", "111", "001", "111"),
}


def _draw_digit(draw: ImageDraw.ImageDraw, digit: str, x: int, y: int, color: tuple[int, int, int]) -> None:
    for row_i, row in enumerate(DIGITS[digit]):
        for col_i, value in enumerate(row):
            if value == "1":
                draw.point((x + col_i, y + row_i), fill=color)


def _draw_number(draw: ImageDraw.ImageDraw, value: int, x: int, y: int, color: tuple[int, int, int]) -> None:
    text = f"{value:02d}"
    _draw_digit(draw, text[0], x, y, color)
    _draw_digit(draw, text[1], x + 4, y, color)


def digital_clock(now: datetime, clock_24h: bool = False) -> Image.Image:
    hour = now.hour if clock_24h else (now.hour % 12 or 12)
    minute = now.minute
    image = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
    draw = ImageDraw.Draw(image)

    _draw_number(draw, hour, 4, 1, (255, 80, 40))
    _draw_number(draw, minute, 4, 10, (60, 180, 255))

    # Minute-change pulse dots.
    if now.second < 30:
        draw.point((7, 7), fill=(255, 220, 60))
        draw.point((8, 8), fill=(255, 220, 60))
    return image


def pixel_art_clock(now: datetime) -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), (3, 3, 8))
    draw = ImageDraw.Draw(image)
    center = (7, 7)

    draw.ellipse((1, 1, 14, 14), outline=(50, 90, 140))
    draw.ellipse((2, 2, 13, 13), outline=(110, 190, 230))
    for point in [(7, 1), (14, 7), (7, 14), (1, 7)]:
        draw.point(point, fill=(255, 220, 90))

    minute_angle = (now.minute / 60.0) * math.tau - math.pi / 2
    hour_angle = ((now.hour % 12 + now.minute / 60.0) / 12.0) * math.tau - math.pi / 2

    minute_end = (
        round(center[0] + math.cos(minute_angle) * 6),
        round(center[1] + math.sin(minute_angle) * 6),
    )
    hour_end = (
        round(center[0] + math.cos(hour_angle) * 4),
        round(center[1] + math.sin(hour_angle) * 4),
    )
    draw.line((center, hour_end), fill=(255, 100, 80))
    draw.line((center, minute_end), fill=(80, 220, 255))
    draw.point(center, fill=(255, 255, 255))
    return image


def clock_image(style: str, now: datetime, clock_24h: bool = False) -> Image.Image:
    if style == "digital":
        return digital_clock(now, clock_24h=clock_24h)
    if style == "pixel-art":
        return pixel_art_clock(now)
    raise ValueError(f"unknown clock style {style!r}")

