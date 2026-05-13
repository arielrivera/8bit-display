"""Configuration loading for the local controller."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class DeviceConfig:
    name: str = "MI Matrix Display"
    backend: str = "native-ble"
    gamma: float = 0.6


@dataclass(frozen=True)
class PathConfig:
    image_folder: Path = Path("./images")
    state_file: Path = Path("./state.json")


@dataclass(frozen=True)
class ModeConfig:
    type: str = "carousel"
    carousel_seconds: int = 300
    single_image: Path = Path("./images/current.png")
    clock_style: str = "digital"
    clock_24h: bool = False


@dataclass(frozen=True)
class AppConfig:
    device: DeviceConfig = DeviceConfig()
    paths: PathConfig = PathConfig()
    mode: ModeConfig = ModeConfig()


def _expand_path(value: str | Path) -> Path:
    return Path(value).expanduser()


def load_config(path: Path) -> AppConfig:
    raw: dict[str, Any] = {}
    if path.exists():
        with path.open("r", encoding="utf-8") as config_file:
            raw = yaml.safe_load(config_file) or {}

    device_raw = raw.get("device", {})
    paths_raw = raw.get("paths", {})
    mode_raw = raw.get("mode", {})

    return AppConfig(
        device=DeviceConfig(
            name=device_raw.get("name", DeviceConfig.name),
            backend=device_raw.get("backend", DeviceConfig.backend),
            gamma=float(device_raw.get("gamma", DeviceConfig.gamma)),
        ),
        paths=PathConfig(
            image_folder=_expand_path(paths_raw.get("image_folder", PathConfig.image_folder)),
            state_file=_expand_path(paths_raw.get("state_file", PathConfig.state_file)),
        ),
        mode=ModeConfig(
            type=mode_raw.get("type", ModeConfig.type),
            carousel_seconds=int(mode_raw.get("carousel_seconds", ModeConfig.carousel_seconds)),
            single_image=_expand_path(mode_raw.get("single_image", ModeConfig.single_image)),
            clock_style=mode_raw.get("clock_style", ModeConfig.clock_style),
            clock_24h=bool(mode_raw.get("clock_24h", ModeConfig.clock_24h)),
        ),
    )
