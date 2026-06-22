"""Smoke tests for the damage classification and statistics logic.

Uses small synthetic frames so no raster or GeoPackage data is required.
"""

import pandas as pd

import classify_damage
import config
import viz_common


def _synthetic_buildings():
    """Four buildings with E2a relative losses of 0.00, 0.21, 0.41, 0.61.

    All carry enough valid pixels (n_*) to be classified.
    """
    enough = config.MIN_BUILDING_PIXELS
    return pd.DataFrame({
        "coh_E1": [1.0, 1.0, 1.0, 1.0],
        "coh_E2a": [1.0, 0.79, 0.59, 0.39],
        "coh_E2b": [1.0, 1.0, 1.0, 1.0],
        "coh_E3": [1.0, 1.0, 1.0, 1.0],
        "n_E1": [enough] * 4,
        "n_E2a": [enough] * 4,
        "n_E2b": [enough] * 4,
        "n_E3": [enough] * 4,
    })


def test_damage_classes_follow_thresholds():
    buildings = _synthetic_buildings()
    classify_damage.add_damage_classes(buildings)
    # Losses 0.00, 0.21, 0.41, 0.61 -> classes 0, 1, 2, 3.
    assert list(buildings["damage_E2a"]) == [0, 1, 2, 3]
    # An unchanged epoch stays at class 0 everywhere.
    assert list(buildings["damage_E2b"]) == [0, 0, 0, 0]


def test_insufficient_coverage_is_flagged():
    buildings = _synthetic_buildings()
    # Starve the second building of valid pixels in the compared epoch and the
    # third building in the reference epoch.
    buildings.loc[1, "n_E2a"] = config.MIN_BUILDING_PIXELS - 1
    buildings.loc[2, "n_E1"] = config.MIN_BUILDING_PIXELS - 1
    classify_damage.add_damage_classes(buildings)
    assert buildings.loc[1, "damage_E2a"] == config.DAMAGE_NODATA
    assert buildings.loc[2, "damage_E2a"] == config.DAMAGE_NODATA
    # Flagged buildings carry a NaN relative loss, not a misleading 0.
    assert buildings.loc[1, "rel_E2a"] != buildings.loc[1, "rel_E2a"]


def test_relative_loss_column_added():
    buildings = _synthetic_buildings()
    classify_damage.add_damage_classes(buildings)
    for epoch in config.DAMAGE_EPOCHS:
        assert f"rel_{epoch}" in buildings.columns


def _dualpol_buildings():
    """Two cells with per-polarisation coherence for every epoch.

    Only E2a changes: the second cell loses 0.4 in VV and 0.2 in VH, so the
    fused relative loss is their mean, 0.3.
    """
    enough = config.MIN_BUILDING_PIXELS
    frame = {f"n_{epoch}": [enough, enough] for epoch in ["E1", *config.DAMAGE_EPOCHS]}
    for pol in config.COH_POLARISATIONS:
        for epoch in ["E1", "E2b", "E3"]:
            frame[f"coh_{epoch}_{pol}"] = [1.0, 1.0]
    frame["coh_E2a_VV"] = [1.0, 0.6]   # VV loss 0.0, 0.4
    frame["coh_E2a_VH"] = [1.0, 0.8]   # VH loss 0.0, 0.2
    return pd.DataFrame(frame)


def test_dual_pol_fusion_averages_relative_loss():
    buildings = _dualpol_buildings()
    classify_damage.add_damage_classes(buildings)
    # Fused loss is the mean of the per-channel losses: (0.4 + 0.2) / 2 = 0.3.
    assert abs(buildings.loc[1, "rel_E2a"] - 0.3) < 1e-6
    assert buildings.loc[0, "damage_E2a"] == 0
    assert buildings.loc[1, "damage_E2a"] == 1   # 0.3 crosses the 0.20 light threshold


def test_damage_percentages():
    buildings = pd.DataFrame({"damage_E2a": [0, 0, 1, 3]})
    affected_pct, severe_pct = viz_common.damage_percentages(buildings, "E2a")
    assert affected_pct == 50.0   # two of four are class >= 1
    assert severe_pct == 25.0     # one of four is class >= 3


def test_damage_percentages_empty():
    buildings = pd.DataFrame({"damage_E2a": []})
    affected_pct, severe_pct = viz_common.damage_percentages(buildings, "E2a")
    assert affected_pct != affected_pct  # NaN for an empty set
    assert severe_pct != severe_pct
