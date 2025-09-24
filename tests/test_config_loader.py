from m1.config import Config, load_layered_config


def test_environment_override(monkeypatch):
    monkeypatch.setenv("M1_CACHE_DB", "custom.db")

    data, sources = load_layered_config()

    assert data["cache"]["db"] == "custom.db"
    assert "env:M1_*" in sources

    config = Config.load()
    assert config.get("cache", {}).get("db") == "custom.db"

    monkeypatch.delenv("M1_CACHE_DB", raising=False)
