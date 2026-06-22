"""Smoke tests for the central configuration and scene catalog.

These run without the large data: the AOI definition is version-controlled in
the repository, and everything else here is metadata.
"""

import config


def test_aoi_bounds_are_ordered_and_in_region():
    bounds = config.load_aoi_bounds()
    assert bounds["west"] < bounds["east"]
    assert bounds["south"] < bounds["north"]
    # El Geneina sits near 22.4 E, 13.4 N.
    assert 22.0 < bounds["west"] < 23.0
    assert 13.0 < bounds["south"] < 14.0


def test_aoi_wkt_is_a_closed_polygon():
    wkt = config.aoi_wkt()
    assert wkt.startswith("POLYGON((") and wkt.endswith("))")
    ring = wkt[len("POLYGON(("):-2].split(", ")
    assert len(ring) >= 4
    assert ring[0] == ring[-1]  # ring must close


def test_aoi_size_is_positive():
    width_km, height_km = config.aoi_size_km()
    assert width_km > 0
    assert height_km > 0


def test_scene_catalog_is_consistent():
    assert len(config.SAFE_FILENAMES) == 10
    assert set(config.ALL_DATES) == set(config.SAFE_FILENAMES)
    for date in config.ALL_DATES:
        assert config.safe_path(date).name.endswith(".SAFE.zip")


def test_coherence_pairs_reference_known_dates():
    known_dates = set(config.ALL_DATES)
    for reference_date, secondary_date, label in config.COH_PAIRS:
        assert reference_date in known_dates
        assert secondary_date in known_dates
        assert label


def test_epoch_tifs_match_pair_labels():
    pair_tifs = {f"{label}.tif" for _ref, _sec, label in config.COH_PAIRS}
    for tif_names in config.EPOCH_COH_TIFS.values():
        for tif_name in tif_names:
            assert tif_name in pair_tifs


def test_damage_thresholds_are_increasing():
    classes = sorted(config.DAMAGE_THRESHOLDS)
    thresholds = [config.DAMAGE_THRESHOLDS[c] for c in classes]
    assert thresholds == sorted(thresholds)
    assert all(0 < t < 1 for t in thresholds)
