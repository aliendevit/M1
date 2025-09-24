"""Configuration helpers for the M1 application."""
from __future__ import annotations

import os
import platform
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import yaml

DEFAULT_CONFIG_NAME = "config.yaml"
PACKAGE_DEFAULT_PATH = "defaults/config.yaml"


@dataclass(slots=True)
class Config:
    """Strongly-typed view of configuration content."""

    data: Dict[str, Any]

    @classmethod
    def load(cls, path: Path | None = None, *, layered: bool = True) -> "Config":
        """Load configuration from a specific path or using the layered strategy."""
        if path is not None:
            return cls(data=_load_yaml(Path(path)))
        if layered:
            data, _ = load_layered_config()
            return cls(data=data)
        return cls(data=_load_yaml(Path(DEFAULT_CONFIG_NAME)))

    def get(self, key: str, default: Any | None = None) -> Any:
        return self.data.get(key, default)


def load_package_config() -> Config:
    """Load only the defaults bundled with the package."""
    return Config(data=_load_package_defaults())


def load_layered_config() -> Tuple[Dict[str, Any], List[str]]:
    """Return the effective layered configuration and the sources applied."""
    sources: List[str] = []
    data: Dict[str, Any] = {}

    package_defaults = _load_package_defaults()
    if package_defaults:
        data = package_defaults
        sources.append("package:" + PACKAGE_DEFAULT_PATH)

    for path in _default_overlay_paths():
        overlay = _load_yaml(path)
        if overlay:
            data = _deep_merge(data, overlay)
            sources.append(str(path))

    env_path = os.environ.get("M1_CONFIG")
    if env_path:
        overlay = _load_yaml(Path(env_path))
        if overlay:
            data = _deep_merge(data, overlay)
            sources.append(env_path)

    env_overlay = _environment_overrides()
    if env_overlay:
        data = _deep_merge(data, env_overlay)
        sources.append("env:M1_*")

    return data, sources


def _load_package_defaults() -> Dict[str, Any]:
    try:
        resource = resources.files("m1").joinpath(PACKAGE_DEFAULT_PATH)
    except (FileNotFoundError, ModuleNotFoundError):  # pragma: no cover - packaging guard
        return {}
    if not resource.is_file():  # pragma: no cover - packaging guard
        return {}
    with resource.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    return loaded if isinstance(loaded, dict) else {}


def _load_yaml(path: Path) -> Dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle) or {}
    except FileNotFoundError:
        return {}
    except OSError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _deep_merge(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    merged: Dict[str, Any] = {**base}
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _default_overlay_paths() -> List[Path]:
    paths: List[Path] = []
    system_path = _system_config_path()
    if system_path is not None:
        paths.append(system_path)
    user_path = _user_config_path()
    if user_path is not None:
        paths.append(user_path)
    paths.append(Path.cwd() / DEFAULT_CONFIG_NAME)
    return paths


def _system_config_path() -> Path | None:
    if platform.system().lower().startswith("win"):
        base = Path(os.environ.get("PROGRAMDATA", r"C:\\ProgramData"))
        return base / "m1" / DEFAULT_CONFIG_NAME
    return Path("/etc/m1") / DEFAULT_CONFIG_NAME


def _user_config_path() -> Path | None:
    if platform.system().lower().startswith("win"):
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
        return base / "m1" / DEFAULT_CONFIG_NAME
    return Path.home() / ".config" / "m1" / DEFAULT_CONFIG_NAME


def _environment_overrides() -> Dict[str, Any]:
    overrides: Dict[str, Any] = {}
    env_specs = {
        "M1_CACHE_DB": (("cache", "db"), str),
        "M1_LLM_PATH": (("llm", "path"), str),
        "M1_LLM_THREADS": (("llm", "threads"), int),
        "M1_LLM_CTX": (("llm", "ctx"), int),
        "M1_LLM_N_GPU_LAYERS": (("llm", "n_gpu_layers"), int),
        "M1_DISCHARGE_LANGUAGES": (("localization", "discharge_languages"), _parse_languages),
        "M1_OFFLINE_ONLY": (("privacy", "offline_only"), _parse_bool),
        "M1_AUDIT_LOG": (("logging", "audit_log"), str),
    }

    for env_var, (path, caster) in env_specs.items():
        if env_var not in os.environ:
            continue
        raw_value = os.environ[env_var]
        try:
            value = caster(raw_value)
        except (TypeError, ValueError):
            continue
        _set_nested(overrides, path, value)
    return overrides


def _set_nested(target: Dict[str, Any], path: Iterable[str], value: Any) -> None:
    current = target
    keys = list(path)
    for key in keys[:-1]:
        if key not in current or not isinstance(current[key], dict):
            current[key] = {}
        current = current[key]
    current[keys[-1]] = value


def _parse_languages(raw: str) -> List[str]:
    parts = [part.strip() for part in raw.split(",") if part.strip()]
    return parts or ["en"]


def _parse_bool(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "on"}
