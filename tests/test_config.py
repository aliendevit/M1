from pathlib import Path

import pytest

from m1.config import AppConfig, load_config


def test_load_config(tmp_path: Path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
        asr: {model: faster-whisper-small-int8, vad: silero, segment_ms: 20000}
        llm: {path: models/llm.gguf, threads: 4, ctx: 1024, n_gpu_layers: 4, temperature: 0.2}
        cache: {window_hours: 48, db: data/chart.sqlite}
        confidence:
          weights: {rule_hit:0.35, p_llm:0.25, asr:0.15, ontology:0.10, context:0.15}
          thresholds: {auto_accept:0.9, soft_confirm:0.7, must_confirm:0.45}
          risk_bumps: {high:0.05, medium:0.03}
        localization: {discharge_languages: ["en", "es"], default: "en"}
        pathways: {enabled: ["chest_pain"]}
        privacy: {offline_only: true, log_retention_days: 7, auto_lock_idle_min: 3}
        """,
        encoding="utf-8",
    )

    config = load_config(config_path)
    assert isinstance(config, AppConfig)
    assert config.asr.model == "faster-whisper-small-int8"
    assert config.localization.default == "en"


def test_invalid_default_language(tmp_path: Path):
    config_path = tmp_path / "bad.yaml"
    config_path.write_text(
        """
        asr: {model: faster-whisper-small-int8, vad: silero}
        llm: {path: models/llm.gguf, threads: 4, ctx: 1024, n_gpu_layers: 4, temperature: 0.2}
        cache: {window_hours: 48, db: data/chart.sqlite}
        localization: {discharge_languages: ["en"], default: "es"}
        """,
        encoding="utf-8",
    )

    with pytest.raises(Exception):
        load_config(config_path)
