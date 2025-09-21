from __future__ import annotations

from pathlib import Path

import pytest

from m1.ui import app


def test_headless_launch_loads_config(tmp_path: Path):
    # Copy the default config to a temporary location to avoid accidental mutation.
    config_copy = tmp_path / "config.yaml"
    config_copy.write_text(Path("config.yaml").read_text(encoding="utf-8"), encoding="utf-8")

    exit_code = app.main(["--config", str(config_copy), "--headless"])

    assert exit_code == 0


@pytest.mark.parametrize("missing", ["config.yaml", "nonexistent.yaml"])
def test_main_handles_missing_config(tmp_path: Path, missing: str):
    # Run against a directory without the config to ensure graceful failure.
    exit_code = app.main(["--config", str(tmp_path / missing), "--headless"])
    assert exit_code == 1
