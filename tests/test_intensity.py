"""Smoke tests for the intensity log-ratio logic in classify_intensity.py.

Only the pure functions are tested. The SNAP calibration (run_intensity.py) and
the raster zonal statistics need the large data and SNAP, so they are exercised
by running the stage, not in the test suite.
"""

import numpy as np
import pandas as pd

import config
import classify_intensity


def _frame_with_intensity(epochs):
    """Minimal frame carrying per-epoch, per-polarisation intensity columns."""
    frame = pd.DataFrame(index=range(3))
    for epoch in epochs:
        for polarisation in config.COH_POLARISATIONS:
            frame[f"int_{epoch}_{polarisation}"] = 1.0
    return frame


def test_log_ratio_is_dual_pol_mean_in_decibels():
    epochs = ["E1", *config.DAMAGE_EPOCHS]
    frame = _frame_with_intensity(epochs)
    # E2b: VV drops to a tenth (-10 dB), VH unchanged (0 dB) -> mean -5 dB.
    frame["int_E2b_VV"] = 0.1
    frame["int_E2b_VH"] = 1.0

    classify_intensity.add_log_ratio(frame)
    assert np.allclose(frame["lr_E2b"], -5.0)
    # Unchanged epochs sit at 0 dB.
    assert np.allclose(frame["lr_E2a"], 0.0)


def test_change_threshold_is_robust_std_of_unbuilt_cells():
    epochs = config.DAMAGE_EPOCHS
    # Unbuilt cells (count 0) carry a symmetric log-ratio with MAD 1.0; built-up
    # cells (count 1) must not influence the threshold.
    unbuilt = np.array([-1.0, 0.0, 1.0])
    frame = pd.DataFrame({"building_count": [0, 0, 0, 1]})
    for epoch in epochs:
        frame[f"lr_{epoch}"] = np.append(unbuilt, 99.0)

    thresholds = classify_intensity.change_thresholds(frame)
    expected = config.INTENSITY_CHANGE_SIGMA * 1.4826 * 1.0
    assert np.isclose(thresholds["E2b"], expected)


def test_filter_only_removes_unconfirmed_affected_cells():
    epochs = config.DAMAGE_EPOCHS
    # classes: nodata, none, affected-unconfirmed, affected-confirmed, severe-confirmed
    frame = pd.DataFrame({"building_count": [1, 1, 1, 1, 1]})
    for epoch in epochs:
        frame[f"damagec_{epoch}"] = [config.DAMAGE_NODATA, 0, 1, 2, 3]
        frame[f"lr_{epoch}"] = [0.0, 0.0, 1.0, 5.0, 5.0]

    thresholds = {epoch: 2.0 for epoch in epochs}
    classify_intensity.add_intensity_filter(frame, thresholds)

    # The unconfirmed affected cell (class 1, |LR| 1 < 2) drops to no damage;
    # confirmed cells and the no-data / no-damage cells are unchanged.
    assert list(frame["damagef_E2b"]) == [config.DAMAGE_NODATA, 0, 0, 2, 3]
    assert list(frame["intensity_change_E2b"]) == [False, False, False, True, True]


def test_filter_never_adds_damage():
    epochs = config.DAMAGE_EPOCHS
    # A strong intensity change on a no-damage cell must not create damage.
    frame = pd.DataFrame({"building_count": [1, 1]})
    for epoch in epochs:
        frame[f"damagec_{epoch}"] = [0, config.DAMAGE_NODATA]
        frame[f"lr_{epoch}"] = [10.0, 10.0]

    classify_intensity.add_intensity_filter(frame, {e: 2.0 for e in epochs})
    assert list(frame["damagef_E2b"]) == [0, config.DAMAGE_NODATA]
