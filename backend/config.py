# path: backend/config.py
from __future__ import annotations

import json
import logging
import os
import socket
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None


# -------- Defaults per brief (Appendix C) --------
_DEFAULT_CFG: Dict[str, Any] = {
    "asr": {"model_dir": "models/asr/faster-whisper-small-int8", "vad": "silero", "segment_ms": 20000},
    "llm": {
        "path": "models/llm/llama-3.2-3b-instruct-q4_ks.gguf",
        "threads": 8,
        "ctx": 2048,
        "n_gpu_layers": 8,
        "temperature": 0.2,
    },
    "cache": {"window_hours": 72, "db": "data/chart.sqlite"},
    "confidence": {
        "weights": {"rule_hit": 0.35, "p_llm": 0.25, "asr": 0.15, "ontology": 0.10, "context": 0.15},
        "thresholds": {"auto_accept": 0.90, "soft_confirm": 0.70, "must_confirm": 0.45},
        "risk_bumps": {"high": 0.05, "medium": 0.03},
    },
    "localization": {"discharge_languages": ["en", "es"], "default": "en"},
    "pathways": {"enabled": ["chest_pain", "seizure", "sepsis"]},
    "privacy": {"offline_only": True, "log_retention_days": 30},
}


def _merge(dst: Dict[str, Any], src: Dict[str, Any]) -> Dict[str, Any]:
    out = deepcopy(dst)
    for k, v in (src or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path: str | Path = "config/config.yaml") -> Dict[str, Any]:
    cfg = deepcopy(_DEFAULT_CFG)
    p = Path(path)
    if yaml and p.exists():
        try:
            with p.open("r", encoding="utf-8") as f:
                file_cfg = yaml.safe_load(f) or {}
            cfg = _merge(cfg, file_cfg)
        except Exception:
            # keep defaults; log warning once app logger is up
            pass
    # Env overrides (simple: JSON in M1_CONFIG env or single fields like M1_OFFLINE=1)
    env_json = os.getenv("M1_CONFIG")
    if env_json:
        try:
            cfg = _merge(cfg, json.loads(env_json))
        except Exception:
            pass
    if os.getenv("M1_OFFLINE") == "0":
        cfg["privacy"]["offline_only"] = False
    return cfg


def setup_logging():
    # If config/logging.yaml exists, try to load it; else use basicConfig.
    log_cfg = Path("config/logging.yaml")
    if yaml and log_cfg.exists():
        try:
            import logging.config as _lc

            with log_cfg.open("r", encoding="utf-8") as f:
                _lc.dictConfig(yaml.safe_load(f))
            return
        except Exception:
            pass
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


# --------- Offline network guard ---------
_ORIG_CONNECT = None  # type: ignore


def enforce_offline(cfg: Dict[str, Any]) -> bool:
    """
    Prevent outbound network connections when privacy.offline_only is True.
    Allows loopback (127.0.0.0/8, ::1) so local FastAPI can run.
    """
    global _ORIG_CONNECT
    offline = bool(cfg.get("privacy", {}).get("offline_only", True))
    if not offline or _ORIG_CONNECT is not None:
        return False

    _ORIG_CONNECT = socket.socket.connect

    def _guarded_connect(self, address):
        try:
            host, port = address
        except Exception:
            # unknown structure; deny
            raise OSError("Network disabled by M1 offline mode")
        try:
            ip = socket.gethostbyname(host)
        except Exception:
            ip = str(host)
        if ip.startswith("127.") or ip == "::1":
            return _ORIG_CONNECT(self, address)
        raise OSError("Network disabled by M1 offline mode")

    socket.socket.connect = _guarded_connect  # type: ignore
    os.environ["M1_OFFLINE"] = "1"
    return True
