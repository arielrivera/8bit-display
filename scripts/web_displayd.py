#!/usr/bin/env python3
"""Serve the local Web Bluetooth controller and image APIs."""

from __future__ import annotations

import argparse
import json
import mimetypes
import subprocess
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

from matrix_display.clock import clock_frames, clock_image
from matrix_display.config import AppConfig, load_config
from matrix_display.controller import list_images


class DisplayWebHandler(SimpleHTTPRequestHandler):
    config: AppConfig
    config_path: Path
    label = "org.arielrivera.8bit-display"

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

        if parsed.path == "/api/service/status":
            self._send_json(self._service_status())
            return

        if parsed.path == "/api/config-file":
            self._send_json(
                {
                    "path": str(self.config_path),
                    "text": self.config_path.read_text(encoding="utf-8") if self.config_path.exists() else "",
                }
            )
            return

        if parsed.path == "/api/logs":
            params = parse_qs(parsed.query)
            lines = int(params.get("lines", ["80"])[0])
            self._send_json(
                {
                    "stdout": self._tail(ROOT / "logs" / "displayd.out.log", lines),
                    "stderr": self._tail(ROOT / "logs" / "displayd.err.log", lines),
                }
            )
            return

        if parsed.path == "/api/project":
            self._send_json(
                {
                    "root": str(ROOT),
                    "config": str(self.config_path),
                    "image_folder": str((ROOT / self.config.paths.image_folder).resolve()),
                    "launch_agent": str(Path.home() / "Library" / "LaunchAgents" / f"{self.label}.plist"),
                    "logs": str(ROOT / "logs"),
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

        if parsed.path == "/api/clock-animation":
            params = parse_qs(parsed.query)
            style = params.get("style", [self.config.mode.clock_style])[0]
            clock_24h = params.get("clock_24h", [str(self.config.mode.clock_24h)])[0].lower() in {
                "1",
                "true",
                "yes",
                "on",
            }
            frames = clock_frames(style, datetime.now(), clock_24h=clock_24h)
            self._send_json(
                {
                    "animated": len(frames) > 1,
                    "frames": len(frames),
                    "urls": [
                        f"/api/clock-frame.png?style={style}&clock_24h={str(clock_24h).lower()}&index={index}"
                        for index in range(len(frames))
                    ],
                }
            )
            return

        if parsed.path == "/api/clock-frame.png":
            params = parse_qs(parsed.query)
            style = params.get("style", [self.config.mode.clock_style])[0]
            clock_24h = params.get("clock_24h", [str(self.config.mode.clock_24h)])[0].lower() in {
                "1",
                "true",
                "yes",
                "on",
            }
            try:
                index = int(params.get("index", ["0"])[0])
            except ValueError:
                self.send_error(HTTPStatus.BAD_REQUEST)
                return
            frames = clock_frames(style, datetime.now(), clock_24h=clock_24h)
            if not 0 <= index < len(frames):
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            buffer = BytesIO()
            frames[index].save(buffer, format="PNG")
            self._send_bytes(buffer.getvalue(), "image/png")
            return

        super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/config-file":
            payload = self._read_json()
            text = str(payload.get("text", ""))
            old_text = self.config_path.read_text(encoding="utf-8") if self.config_path.exists() else ""
            self.config_path.write_text(text, encoding="utf-8")
            try:
                self.__class__.config = load_config(self.config_path)
            except Exception as exc:
                self.config_path.write_text(old_text, encoding="utf-8")
                self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return
            self._send_json({"ok": True, "message": "Configuration saved"})
            return

        if parsed.path.startswith("/api/service/"):
            action = parsed.path.removeprefix("/api/service/")
            commands = {
                "install": [str(ROOT / "scripts" / "install_launch_agent.sh")],
                "uninstall": [str(ROOT / "scripts" / "uninstall_launch_agent.sh")],
                "stop": ["launchctl", "bootout", f"gui/{self._uid()}", str(self._plist_path())],
                "restart": ["launchctl", "kickstart", "-k", f"gui/{self._uid()}/{self.label}"],
            }
            if action == "start":
                result = self._run_many(
                    [
                        ["launchctl", "enable", f"gui/{self._uid()}/{self.label}"],
                        ["launchctl", "bootstrap", f"gui/{self._uid()}", str(self._plist_path())],
                    ]
                )
            elif action in commands:
                result = self._run(commands[action])
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            self._send_json({"ok": result.returncode == 0, "action": action, **self._result_payload(result)})
            return

        self.send_error(HTTPStatus.NOT_FOUND)

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

    def _send_bytes(self, body: bytes, content_type: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _send_json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        self._send_bytes(json.dumps(payload).encode("utf-8"), "application/json", status=status)

    def _service_status(self) -> dict[str, object]:
        result = self._run(["launchctl", "print", f"gui/{self._uid()}/{self.label}"])
        text = result.stdout + result.stderr
        state = "running" if "\n\tstate = running" in text else "not loaded"
        return {
            "label": self.label,
            "state": state,
            "loaded": result.returncode == 0,
            "plist_exists": self._plist_path().exists(),
            "pid": self._extract_value(text, "pid"),
            "runs": self._extract_value(text, "runs"),
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    def _run(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)

    def _run_many(self, commands: list[list[str]]) -> subprocess.CompletedProcess[str]:
        stdout = []
        stderr = []
        last = subprocess.CompletedProcess(commands[-1], 0, "", "")
        for command in commands:
            last = self._run(command)
            stdout.append(last.stdout)
            stderr.append(last.stderr)
            if last.returncode != 0:
                break
        return subprocess.CompletedProcess(commands[-1], last.returncode, "".join(stdout), "".join(stderr))

    def _result_payload(self, result: subprocess.CompletedProcess[str]) -> dict[str, object]:
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    def _tail(self, path: Path, lines: int) -> str:
        if not path.exists():
            return ""
        content = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(content[-max(1, min(lines, 500)):])

    def _plist_path(self) -> Path:
        return Path.home() / "Library" / "LaunchAgents" / f"{self.label}.plist"

    def _uid(self) -> int:
        return int(subprocess.run(["id", "-u"], text=True, capture_output=True, check=True).stdout.strip())

    def _extract_value(self, text: str, key: str) -> str | None:
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith(f"{key} = "):
                return stripped.removeprefix(f"{key} = ")
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("config.local.yaml"))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    config = load_config(args.config)
    DisplayWebHandler.config = config
    DisplayWebHandler.config_path = args.config if args.config.is_absolute() else ROOT / args.config

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
