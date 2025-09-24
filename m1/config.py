"""Configuration helpers for the M1 application."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import yaml

from . import package_path

DEFAULT_CONFIG_PATH = Path("config.yaml")


@dataclass(slots=True)
class Config:
    """Minimal strongly-typed view of the YAML config."""

    data: Dict[str, Any]

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        config_path = path or DEFAULT_CONFIG_PATH
        with config_path.open("r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle) or {}
        return cls(data=loaded)

    def get(self, key: str, default: Any | None = None) -> Any:
        return self.data.get(key, default)


def load_package_config() -> Config:
    """Load the default config shipped alongside the package."""
    return Config.load(package_path().parent / DEFAULT_CONFIG_PATH)
