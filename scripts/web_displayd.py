#!/usr/bin/env python3
"""Serve the local Web Bluetooth controller and image APIs."""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
from datetime import datetime
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from PIL import Image, ImageSequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from matrix_display.clock import clock_image
from matrix_display.config import AppConfig, load_config
from matrix_display.controller import list_images


class DisplayWebHandler(SimpleHTTPRequestHandler):
    config: AppConfig

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / "web"), **kwargs)

    def log_message(self, format: str, *args) -> None:
        print(format % args, flush=True)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/config":
            self._send_json(
                {
                    "device": {
                        "name": self.config.device.name,
                        "gamma": self.config.device.gamma,
                        "save": self.config.device.save,
                    },
                    "mode": {
                        "type": self.config.mode.type,
                        "carousel_seconds": self.config.mode.carousel_seconds,
                        "single_image": str(self.config.mode.single_image),
                        "clock_style": self.config.mode.clock_style,
                        "clock_24h": self.config.mode.clock_24h,
                    },
                }
            )
            return

        if parsed.path == "/api/images":
            images = list_images(self.config.paths.image_folder)
            self._send_json(
                [
                    {
                        "name": str(path.relative_to(self.config.paths.image_folder)),
                        "url": f"/api/image/{path.relative_to(self.config.paths.image_folder).as_posix()}",
                    }
                    for path in images
                ]
            )
            return

        if parsed.path.startswith("/api/image/"):
            relative = Path(unquote(parsed.path.removeprefix("/api/image/")))
            target = self._resolve_image(relative)
            if target is None:
                self.send_error(HTTPStatus.FORBIDDEN)
                return
            self._send_file(target)
            return

        if parsed.path.startswith("/api/animation/"):
            relative = Path(unquote(parsed.path.removeprefix("/api/animation/")))
            target = self._resolve_image(relative)
            if target is None:
                self.send_error(HTTPStatus.FORBIDDEN)
                return
            if not target.is_file():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            with Image.open(target) as image:
                frame_count = min(getattr(image, "n_frames", 1), 8)
                durations = []
                for frame in ImageSequence.Iterator(image):
                    durations.append(frame.info.get("duration", image.info.get("duration", 100)))
                    if len(durations) == frame_count:
                        break
            self._send_json(
                {
                    "animated": frame_count > 1,
                    "frames": frame_count,
                    "durations_ms": durations,
                    "urls": [
                        f"/api/frame/{relative.as_posix()}?index={index}"
                        for index in range(frame_count)
                    ],
                }
            )
            return

        if parsed.path.startswith("/api/frame/"):
            relative = Path(unquote(parsed.path.removeprefix("/api/frame/")))
            target = self._resolve_image(relative)
            if target is None:
                self.send_error(HTTPStatus.FORBIDDEN)
                return
            if not target.is_file():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            try:
                index = int(parse_qs(parsed.query).get("index", ["0"])[0])
            except ValueError:
                self.send_error(HTTPStatus.BAD_REQUEST)
                return
            with Image.open(target) as image:
                frame_count = getattr(image, "n_frames", 1)
                if not 0 <= index < frame_count:
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                image.seek(index)
                frame = image.convert("RGBA")
                buffer = BytesIO()
                frame.save(buffer, format="PNG")
            self._send_bytes(buffer.getvalue(), "image/png")
            return

        if parsed.path == "/api/clock.png":
            params = parse_qs(parsed.query)
            style = params.get("style", [self.config.mode.clock_style])[0]
            clock_24h = params.get("clock_24h", [str(self.config.mode.clock_24h)])[0].lower() in {
                "1",
                "true",
                "yes",
                "on",
            }
            image = clock_image(style, datetime.now(), clock_24h=clock_24h)
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            self._send_bytes(buffer.getvalue(), "image/png")
            return

        super().do_GET()

    def _send_json(self, payload: object) -> None:
        self._send_bytes(json.dumps(payload).encode("utf-8"), "application/json")

    def _send_file(self, path: Path) -> None:
        if not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self._send_bytes(path.read_bytes(), content_type)

    def _resolve_image(self, relative: Path) -> Path | None:
        target = (self.config.paths.image_folder / relative).resolve()
        image_root = self.config.paths.image_folder.resolve()
        if image_root not in target.parents and target != image_root:
            return None
        return target

    def _send_bytes(self, body: bytes, content_type: str) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("config.local.yaml"))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    config = load_config(args.config)
    DisplayWebHandler.config = config

    server = ThreadingHTTPServer((args.host, args.port), DisplayWebHandler)
    print(f"web-displayd: http://{args.host}:{args.port}", flush=True)
    print(f"web-displayd: config={args.config}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
