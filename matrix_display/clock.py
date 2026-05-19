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

COLON: tuple[str, ...] = ("0", "1", "0", "1", "0")


def _draw_digit(draw: ImageDraw.ImageDraw, digit: str, x: int, y: int, color: tuple[int, int, int]) -> None:
    for row_i, row in enumerate(DIGITS[digit]):
        for col_i, value in enumerate(row):
            if value == "1":
                draw.point((x + col_i, y + row_i), fill=color)


def _draw_number(draw: ImageDraw.ImageDraw, value: int, x: int, y: int, color: tuple[int, int, int]) -> None:
    text = f"{value:02d}"
    _draw_digit(draw, text[0], x, y, color)
    _draw_digit(draw, text[1], x + 4, y, color)


def _draw_glyph(draw: ImageDraw.ImageDraw, glyph: tuple[str, ...], x: int, y: int, color: tuple[int, int, int]) -> None:
    for row_i, row in enumerate(glyph):
        for col_i, value in enumerate(row):
            if value == "1":
                draw.point((x + col_i, y + row_i), fill=color)


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


def digital_bounce_frames(now: datetime, clock_24h: bool = False) -> list[Image.Image]:
    """Generate a compact single-line clock that bounces vertically."""
    hour = now.hour if clock_24h else (now.hour % 12 or 12)
    hour_text = f"{hour:02d}" if clock_24h else str(hour)
    text = f"{hour_text}:{now.minute:02d}"
    y_positions = [2, 4, 6, 8, 10, 8, 6, 4]
    frames: list[Image.Image] = []

    for y in y_positions:
        image = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
        draw = ImageDraw.Draw(image)

        if len(text) == 5:
            # HH:MM fits by letting the colored colon touch both digit pairs.
            _draw_glyph(draw, DIGITS[text[0]], 0, y, (80, 220, 255))
            _draw_glyph(draw, DIGITS[text[1]], 4, y, (80, 220, 255))
            _draw_glyph(draw, COLON, 7, y, (255, 180, 70))
            _draw_glyph(draw, DIGITS[text[3]], 8, y, (80, 220, 255))
            _draw_glyph(draw, DIGITS[text[4]], 12, y, (80, 220, 255))
        else:
            # H:MM has room for a little breathing space around the hour.
            _draw_glyph(draw, DIGITS[text[0]], 1, y, (80, 220, 255))
            _draw_glyph(draw, COLON, 5, y, (255, 180, 70))
            _draw_glyph(draw, DIGITS[text[2]], 7, y, (80, 220, 255))
            _draw_glyph(draw, DIGITS[text[3]], 11, y, (80, 220, 255))

        frames.append(image)
    return frames


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
    if style == "digital-bounce":
        return digital_bounce_frames(now, clock_24h=clock_24h)[0]
    if style == "pixel-art":
        return pixel_art_clock(now)
    raise ValueError(f"unknown clock style {style!r}")


def clock_frames(style: str, now: datetime, clock_24h: bool = False) -> list[Image.Image]:
    if style == "digital-bounce":
        return digital_bounce_frames(now, clock_24h=clock_24h)
    return [clock_image(style, now, clock_24h=clock_24h)]
