"""Smoke tests for the optical validation statistics in validate_optical.py.

Only the pure functions are tested. The STAC search and remote COG reads need
network access and are exercised by running the stage, not in the test suite.
"""

import numpy as np

import validate_optical


def test_confusion_counts_and_rates():
    # optical: 1 1 0 0 ; sar: 1 0 0 1  -> tp=1, fn=1, tn=1, fp=1
    optical = np.array([1.0, 1.0, 0.0, 0.0])
    sar = np.array([1.0, 0.0, 0.0, 1.0])
    result = validate_optical.confusion(optical, sar)
    assert (result["tp"], result["fp"], result["fn"], result["tn"]) == (1, 1, 1, 1)
    assert result["n"] == 4
    assert result["agreement"] == 50.0
    assert result["precision"] == 50.0
    assert result["recall"] == 50.0


def test_confusion_ignores_nan_cells():
    optical = np.array([1.0, np.nan, 0.0])
    sar = np.array([1.0, 1.0, 0.0])
    result = validate_optical.confusion(optical, sar)
    # The NaN cell drops out, leaving a perfect 2-cell agreement.
    assert result["n"] == 2
    assert result["tp"] == 1
    assert result["tn"] == 1
    assert result["agreement"] == 100.0


def test_confusion_perfect_disagreement():
    optical = np.array([1.0, 1.0])
    sar = np.array([0.0, 0.0])
    result = validate_optical.confusion(optical, sar)
    assert result["tp"] == 0
    assert result["fn"] == 2
    assert result["agreement"] == 0.0
    assert result["recall"] == 0.0
