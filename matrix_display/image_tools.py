"""Image loading and conversion for a 16x16 RGB display."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps, ImageSequence

from matrix_display.protocol import HEIGHT, WIDTH


def load_display_image(path: Path) -> Image.Image:
    with Image.open(path) as image:
        return fit_to_display(image.convert("RGBA")).convert("RGB")


def load_display_frames(path: Path, limit: int = 8) -> list[Image.Image]:
    """Load up to `limit` display-sized frames from an animated image."""
    with Image.open(path) as image:
        frames: list[Image.Image] = []
        for frame in ImageSequence.Iterator(image):
            frames.append(fit_to_display(frame.convert("RGBA")).convert("RGB"))
            if len(frames) == limit:
                break
        return frames


def fit_to_display(image: Image.Image) -> Image.Image:
    image = ImageOps.contain(image, (WIDTH, HEIGHT), method=Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 255))
    x = (WIDTH - image.width) // 2
    y = (HEIGHT - image.height) // 2
    canvas.alpha_composite(image, (x, y))
    return canvas


def image_to_pixels(image: Image.Image) -> list[tuple[int, int, int]]:
    if image.size != (WIDTH, HEIGHT):
        image = fit_to_display(image.convert("RGBA")).convert("RGB")
    else:
        image = image.convert("RGB")
    return list(image.getdata())
