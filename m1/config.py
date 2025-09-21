"""Configuration loading utilities for MinuteOne.

The application reads a YAML configuration file that mirrors the
specification documented in the RFP.  We prefer an explicit schema so
operators receive fast feedback when a field is missing or mis-typed.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List

import yaml
from pydantic import BaseModel, Field, ConfigDict, ValidationInfo, field_validator


class ASRConfig(BaseModel):
    """Parameters for the local ASR service."""

    model: str = Field(..., description="Model identifier or path for faster-whisper")
    vad: str = Field(..., description="Voice activity detector identifier")
    segment_ms: int = Field(20_000, description="Segment size in milliseconds")

    @field_validator("segment_ms")
    @classmethod
    def validate_segment_ms(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("segment_ms must be positive")
        return value


class LLMConfig(BaseModel):
    """Settings for the tiny local LLM used during extraction."""

    path: str = Field(..., description="Filesystem path to the quantised GGUF file")
    threads: int = Field(8, ge=1)
    ctx: int = Field(2048, ge=512)
    n_gpu_layers: int = Field(0, ge=0)
    temperature: float = Field(0.2, ge=0.0, le=1.0)


class CacheConfig(BaseModel):
    """Configuration for the SQLite chart cache."""

    window_hours: int = Field(72, ge=1)
    db: str = Field(..., description="Path to the SQLite database containing the FHIR subset")


class ConfidenceWeights(BaseModel):
    rule_hit: float = 0.35
    p_llm: float = 0.25
    asr: float = Field(0.15, alias="c_asr")
    ontology: float = Field(0.10, alias="s_ont")
    context: float = Field(0.15, alias="s_ctx")

    model_config = ConfigDict(populate_by_name=True)


class ConfidenceThresholds(BaseModel):
    auto_accept: float = 0.90
    soft_confirm: float = 0.70
    must_confirm: float = 0.45


class RiskBumps(BaseModel):
    high: float = 0.05
    medium: float = 0.03


class ConfidenceConfig(BaseModel):
    weights: ConfidenceWeights = Field(default_factory=ConfidenceWeights)
    thresholds: ConfidenceThresholds = Field(default_factory=ConfidenceThresholds)
    risk_bumps: RiskBumps = Field(default_factory=RiskBumps)


class LocalizationConfig(BaseModel):
    discharge_languages: List[str] = Field(default_factory=lambda: ["en", "es"])
    default: str = "en"

    @field_validator("default")
    @classmethod
    def ensure_default_supported(cls, value: str, info: ValidationInfo):
        languages = info.data.get("discharge_languages", [])
        if languages and value not in languages:
            raise ValueError("default language must be one of discharge_languages")
        return value


class PathwayConfig(BaseModel):
    enabled: List[str] = Field(default_factory=list)


class PrivacyConfig(BaseModel):
    offline_only: bool = True
    log_retention_days: int = Field(30, ge=0)
    auto_lock_idle_min: int = Field(5, ge=1)


class AppConfig(BaseModel):
    asr: ASRConfig
    llm: LLMConfig
    cache: CacheConfig
    confidence: ConfidenceConfig = Field(default_factory=ConfidenceConfig)
    localization: LocalizationConfig = Field(default_factory=LocalizationConfig)
    pathways: PathwayConfig = Field(default_factory=PathwayConfig)
    privacy: PrivacyConfig = Field(default_factory=PrivacyConfig)


def load_config(path: Path | str = "config.yaml") -> AppConfig:
    """Load and validate configuration from disk."""

    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with config_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return AppConfig.model_validate(data)


@lru_cache(maxsize=1)
def get_cached_config(path: Path | str = "config.yaml") -> AppConfig:
    """Cached config loader suitable for FastAPI dependency injection."""

    return load_config(path)
