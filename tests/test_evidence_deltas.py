from pathlib import Path

from m1.evidence.sqlite_cache import SQLiteChartCache
from m1.fhir.reader import iter_observations, load_bundle


def test_ingest_bundle_and_compute_deltas(tmp_path):
    db_path = tmp_path / "chart.sqlite"
    cache = SQLiteChartCache(db_path)
    cache.initialise()
    resources = load_bundle(Path("demo/patient_bundle.json"))
    observations = list(iter_observations(resources))
    cache.ingest_observations(observations)
    chips = cache.context_window(0)

    chip_map = {chip.id: chip for chip in chips}
    assert chip_map["obs/trop-2"].delta == "+0.02"
    assert chip_map["obs/lactate-2"].delta == "-0.3"
    assert chip_map["obs/creatinine-2"].delta == "+0.3"
    assert len({chip.name for chip in chips}) >= 3
