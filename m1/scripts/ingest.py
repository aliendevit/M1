from __future__ import annotations

import argparse
from pathlib import Path

from m1.config import load_config
from m1.evidence.sqlite_cache import SQLiteChartCache
from m1.fhir.reader import load_bundle


def ingest(bundle_path: Path, db_path: Path) -> None:
    cache = SQLiteChartCache(db_path)
    cache.initialise()
    bundle = load_bundle(bundle_path)
    cache.ingest_bundle(bundle)
    print(f"Ingested bundle {bundle_path} into {db_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest demo bundle into cache")
    parser.add_argument("bundle", type=Path, help="Path to JSON bundle")
    parser.add_argument("--db", type=Path, default=None, help="Override cache db path")
    args = parser.parse_args()

    config = load_config()
    db_path = args.db or Path(config.get("cache", {}).get("db", "m1_cache.db"))
    ingest(args.bundle, db_path)


if __name__ == "__main__":
    main()
