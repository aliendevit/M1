"""Utility CLI to initialise the SQLite cache and ingest demo data."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

from ..config import load_config
from ..evidence.sqlite_cache import SQLiteChartCache
from ..fhir.reader import iter_observations, load_bundle, load_ndjson


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest FHIR bundles or NDJSON into the local cache")
    parser.add_argument("paths", nargs="+", type=Path, help="FHIR bundle (.json) or NDJSON file to ingest")
    parser.add_argument("--config", type=Path, default=Path("config.yaml"), help="Path to configuration file")
    return parser


def load_resources(path: Path):
    if path.suffix == ".json":
        return load_bundle(path)
    if path.suffix == ".ndjson":
        return load_ndjson(path)
    raise ValueError(f"Unsupported file type: {path}")


def ingest(paths: Iterable[Path], config_path: Path) -> int:
    config = load_config(config_path)
    cache = SQLiteChartCache(Path(config.cache.db))
    cache.initialise()
    total = 0
    for path in paths:
        resources = load_resources(path)
        observations = list(iter_observations(resources))
        cache.ingest_observations(observations)
        total += len(observations)
    chips = cache.context_window(config.cache.window_hours)
    print(f"Ingested {total} observations. Available chips: {len(chips)}")
    for chip in chips[:5]:
        print(f" - {chip.name}: {chip.value} {chip.delta or ''} @ {chip.time}")
    return 0


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        return ingest(args.paths, args.config)
    except Exception as exc:  # pragma: no cover - CLI guard
        print(f"Failed to ingest data: {exc}")
        return 1


if __name__ == "__main__":  # pragma: no cover - manual execution only
    raise SystemExit(main())
