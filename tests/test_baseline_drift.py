"""Smoke tests for the baseline QA and rainy-season drift correction.

Uses small synthetic frames so no raster or GeoPackage data is required.
"""

import numpy as np
import pandas as pd

import check_baseline
import config
import correct_baseline_drift


def test_pearson_matches_known_correlation():
    first = np.array([0.1, 0.2, 0.3, 0.4, 0.5])
    second = 2.0 * first + 0.05  # perfectly linear, positive slope
    assert check_baseline.pearson_correlation(first, second) == 1.0


def test_pearson_handles_constant_input():
    first = np.array([0.3, 0.3, 0.3])
    second = np.array([0.1, 0.2, 0.3])
    # Zero variance -> undefined correlation, reported as NaN, not a crash.
    assert np.isnan(check_baseline.pearson_correlation(first, second))


def _reference_cells():
    """Unbuilt reference cells plus one built-up cell.

    Unbuilt E1 median is 0.40 and E2b median 0.20, so R_env(E2b) = 0.50. E2a and
    E3 unbuilt medians equal E1, so their retention is 1.0 (no seasonal drift).
    """
    enough = config.MIN_BUILDING_PIXELS
    return pd.DataFrame({
        "building_count": [0, 0, 0, 5],
        "coh_E1": [0.40, 0.30, 0.50, 1.00],
        "coh_E2a": [0.40, 0.30, 0.50, 1.00],
        "coh_E2b": [0.20, 0.15, 0.25, 0.50],
        "coh_E3": [0.40, 0.30, 0.50, 1.00],
        "n_E1": [enough] * 4,
        "n_E2a": [enough] * 4,
        "n_E2b": [enough] * 4,
        "n_E3": [enough] * 4,
    })


def test_environmental_retention_from_unbuilt_cells():
    cells = _reference_cells()
    retention, reference_median = correct_baseline_drift.environmental_retention(
        cells, config.MIN_BUILDING_PIXELS
    )
    assert reference_median == 0.40            # median of unbuilt E1 (0.40, 0.30, 0.50)
    assert retention["E2a"] == 1.0
    assert np.isclose(retention["E2b"], 0.50)  # 0.20 / 0.40
    assert retention["E3"] == 1.0


def _confidence_cells():
    """One stable cell and one with a clear coherence drop, with spatial spread."""
    enough = config.MIN_BUILDING_PIXELS
    frame = {"building_count": [5, 5]}
    for epoch in ["E1", *config.DAMAGE_EPOCHS]:
        frame[f"n_{epoch}"] = [25.0, 25.0]
        frame[f"coh_{epoch}"] = [1.0, 1.0]
        frame[f"std_{epoch}"] = [0.10, 0.10]
    frame["coh_E2b"] = [1.0, 0.5]   # second cell drops 0.5 against E1
    return pd.DataFrame(frame)


def test_confidence_high_for_clear_drop_zero_for_stable():
    cells = _confidence_cells()
    retention = {epoch: 1.0 for epoch in config.DAMAGE_EPOCHS}
    correct_baseline_drift.add_confidence(cells, retention, config.MIN_BUILDING_PIXELS)
    # Stable cell: no drop -> z ~ 0. Dropped cell: large signal-to-noise z.
    assert abs(cells.loc[0, "z_E2b"]) < 1e-6
    assert cells.loc[1, "z_E2b"] > config.Z_HIGH_CONFIDENCE


def test_correction_removes_seasonal_loss():
    cells = _reference_cells()
    retention = {"E2a": 1.0, "E2b": 0.50, "E3": 1.0}
    correct_baseline_drift.add_corrected_classes(
        cells, retention, config.MIN_BUILDING_PIXELS
    )
    # Built-up cell: coh_E1 1.0, R_env 0.50 -> expected 0.50, observed coh_E2b
    # 0.50 -> corrected loss 0, so a drop that exactly matches the season is not
    # counted as damage.
    assert cells.loc[3, "damagec_E2b"] == 0
    assert np.isclose(cells.loc[3, "relc_E2b"], 0.0, atol=1e-3)
