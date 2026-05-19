#!/usr/bin/env python3
"""Convert downloaded pixel-art packs into display-ready 16x16 assets."""

from __future__ import annotations

import argparse
import base64
import json
import re
import shutil
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageChops, ImageSequence


DISPLAY_SIZE = (16, 16)
DEFAULT_FRAME_MS = 180
STATIC_TILE_LIMIT = 700


def safe_name(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_") or "asset"


def relative_name(path: Path, root: Path) -> str:
    return safe_name("_".join(path.relative_to(root).with_suffix("").parts))


def fit_16(image: Image.Image) -> Image.Image:
    source = image.convert("RGBA")
    source.thumbnail(DISPLAY_SIZE, Image.Resampling.NEAREST)
    canvas = Image.new("RGBA", DISPLAY_SIZE, (0, 0, 0, 255))
    x = (DISPLAY_SIZE[0] - source.width) // 2
    y = (DISPLAY_SIZE[1] - source.height) // 2
    canvas.alpha_composite(source, (x, y))
    return canvas


def is_blank(image: Image.Image) -> bool:
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    return alpha.getbbox() is None or not ImageChops.difference(rgba, Image.new("RGBA", rgba.size)).getbbox()


def save_gif(frames: list[Image.Image], output: Path, duration_ms: int = DEFAULT_FRAME_MS) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if not frames:
        return
    prepared = [fit_16(frame).convert("P", palette=Image.Palette.ADAPTIVE) for frame in frames]
    prepared[0].save(
        output,
        save_all=True,
        append_images=prepared[1:],
        duration=duration_ms,
        loop=0,
        disposal=2,
    )


def convert_piskel(path: Path, root: Path, output_root: Path) -> list[Path]:
    created: list[Path] = []
    data = json.loads(path.read_text())
    base = relative_name(path, root)
    for layer in data.get("piskel", {}).get("layers", []):
        layer_data = json.loads(layer) if isinstance(layer, str) else layer
        name = safe_name(layer_data.get("name", "layer"))
        frame_count = int(layer_data.get("frameCount") or data.get("piskel", {}).get("fps") or 1)
        chunks = layer_data.get("chunks", [])
        for chunk_index, chunk in enumerate(chunks, start=1):
            encoded = chunk.get("base64PNG", "")
            if "," in encoded:
                encoded = encoded.split(",", 1)[1]
            strip = Image.open(BytesIO(base64.b64decode(encoded))).convert("RGBA")
            frame_width = strip.width // frame_count if frame_count else strip.width
            frames = [
                strip.crop((i * frame_width, 0, (i + 1) * frame_width, strip.height))
                for i in range(frame_count)
            ]
            output_base = output_root / "piskel" / f"{base}_{name}"
            if len(chunks) > 1:
                output_base = output_base.with_name(f"{output_base.name}_{chunk_index:02d}")
            gif_path = output_base.with_suffix(".gif")
            save_gif(frames, gif_path)
            created.append(gif_path)
            for i, frame in enumerate(frames, start=1):
                png_path = output_base.with_name(f"{output_base.name}_frame{i:02d}.png")
                fit_16(frame).save(png_path)
                created.append(png_path)
    return created


def convert_gif(path: Path, root: Path, output_root: Path) -> list[Path]:
    image = Image.open(path)
    frames = [frame.convert("RGBA") for frame in ImageSequence.Iterator(image)]
    if len(frames) == 1 and frames[0].width > frames[0].height and frames[0].width % frames[0].height == 0:
        frame_width = frames[0].height
        frames = [
            frames[0].crop((i * frame_width, 0, (i + 1) * frame_width, frames[0].height))
            for i in range(frames[0].width // frame_width)
        ]
    output = output_root / "animated_gifs" / f"{relative_name(path, root)}.gif"
    save_gif(frames[:8], output, int(image.info.get("duration") or DEFAULT_FRAME_MS))
    return [output]


def sheet_frame_width(image: Image.Image) -> int | None:
    if image.width > image.height and image.width % image.height == 0:
        return image.height
    if image.width % 32 == 0 and image.height >= 32:
        return 32
    if image.width % 16 == 0 and image.height <= 32:
        return 16
    return None


def convert_animated_sheet(path: Path, root: Path, output_root: Path) -> list[Path]:
    image = Image.open(path).convert("RGBA")
    frame_width = sheet_frame_width(image)
    if not frame_width:
        raise ValueError(f"no frame width for {image.width}x{image.height}")
    frames = [
        image.crop((x, 0, x + frame_width, min(image.height, frame_width)))
        for x in range(0, image.width - frame_width + 1, frame_width)
    ]
    output = output_root / "animated_sheets" / f"{relative_name(path, root)}.gif"
    save_gif(frames[:8], output)
    return [output]


def convert_static_sheet(path: Path, root: Path, output_root: Path, remaining: int) -> tuple[list[Path], int]:
    image = Image.open(path).convert("RGBA")
    if image.width % 16 or image.height % 16:
        raise ValueError(f"not 16-grid {image.width}x{image.height}")
    created: list[Path] = []
    base = relative_name(path, root)
    for y in range(0, image.height, 16):
        for x in range(0, image.width, 16):
            if remaining <= 0:
                return created, remaining
            tile = image.crop((x, y, x + 16, y + 16))
            if is_blank(tile):
                continue
            output = output_root / "tiles_16x16" / f"{base}_{len(created):03d}.png"
            output.parent.mkdir(parents=True, exist_ok=True)
            fit_16(tile).save(output)
            created.append(output)
            remaining -= 1
    return created, remaining


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Downloaded asset folder to scan")
    parser.add_argument("--output", type=Path, default=Path("images/imported"))
    parser.add_argument("--tile-limit", type=int, default=STATIC_TILE_LIMIT)
    args = parser.parse_args()

    source = args.source.expanduser().resolve()
    output_root = args.output.resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    created: list[Path] = []
    notes: list[str] = []
    remaining_tiles = args.tile_limit
    tile_limit_reported = False

    for terms in source.rglob("Terms.txt"):
        shutil.copy2(terms, output_root / f"{relative_name(terms.parent, source)}_TERMS.txt")

    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        try:
            if suffix == ".piskel":
                created.extend(convert_piskel(path, source, output_root))
            elif suffix == ".gif":
                created.extend(convert_gif(path, source, output_root))
            elif suffix == ".png":
                name = path.stem.lower()
                if "sheet" in name or "strip" in name:
                    created.extend(convert_animated_sheet(path, source, output_root))
                elif remaining_tiles <= 0:
                    if not tile_limit_reported:
                        notes.append(f"{path} :: static tile limit reached at {args.tile_limit}")
                        tile_limit_reported = True
                else:
                    tiles, remaining_tiles = convert_static_sheet(path, source, output_root, remaining_tiles)
                    created.extend(tiles)
                    if remaining_tiles <= 0 and not tile_limit_reported:
                        notes.append(f"{path} :: static tile limit reached at {args.tile_limit}")
                        tile_limit_reported = True
            elif suffix == ".aseprite":
                notes.append(f"{path} :: skipped .aseprite; install Aseprite CLI or use exported PNG sheets")
        except Exception as exc:  # noqa: BLE001 - importer should keep scanning packs.
            notes.append(f"{path} :: {exc}")

    summary = output_root / "CONVERSION_SUMMARY.txt"
    summary.write_text(
        "\n".join(
            [
                f"Converted assets from {source}",
                "",
                f"Converted files: {len(created)}",
                f"Skipped/notes: {len(notes)}",
                "",
                "First converted files:",
                *[str(path.relative_to(Path.cwd())) if path.is_relative_to(Path.cwd()) else str(path) for path in created[:200]],
                "",
                "Skipped/notes:",
                *notes,
                "",
            ]
        )
    )
    print(f"Converted {len(created)} files into {output_root}")
    print(f"Summary: {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
