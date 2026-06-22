"""Quality assurance for the pre-conflict reference (E1) baseline.

Damage is defined as the coherence drop relative to E1, so the reference itself
has to be stable. E1 spans two consecutive pre-conflict 12-day pairs
(0319-0331 and 0331-0412). Comparing them measures the natural decorrelation of
the intact city: the apparent coherence loss with no conflict at all. That sets
the false-positive floor for the damage thresholds, so it states how much of the
later "damage" could be baseline noise rather than destruction.

The check runs on the built-up grid cells (the statistical unit, see
classify_grid.py), not on individual sub-pixel footprints.

    python check_baseline.py
"""

from __future__ import annotations

import numpy as np

import config
from classify_damage import load_buildings, zonal_coherence
from classify_grid import built_up_cells, reference_grid


def e1_pair_coherence(grid_gdf, min_pixels: float):
    """Return the two pre-conflict pair means and a shared validity mask.

    Each E1 pair is aggregated separately (add_epoch_coherence would average
    them away). A cell is kept only where both pairs carry enough valid pixels.
    """
    pair_names = config.EPOCH_COH_TIFS["E1"]
    means, counts = [], []
    for tif_name in pair_names:
        mean, count, _ = zonal_coherence(grid_gdf, config.COH_DIR / tif_name)
        means.append(mean)
        counts.append(count)

    valid = (counts[0] >= min_pixels) & (counts[1] >= min_pixels)
    return means[0][valid], means[1][valid], pair_names, int(valid.sum())


def pearson_correlation(first, second) -> float:
    """Pearson correlation, computed directly to avoid np.corrcoef.

    np.corrcoef routes through a BLAS path that crashes in this conda
    environment, so the coefficient is built from centred sums instead.
    """
    centred_first = first - first.mean()
    centred_second = second - second.mean()
    denominator = np.sqrt((centred_first ** 2).sum() * (centred_second ** 2).sum())
    if denominator == 0:
        return float("nan")
    return float((centred_first * centred_second).sum() / denominator)


def report_baseline(first, second, pair_names, n_cells: int) -> None:
    """Print the E1 baseline-stability statistics."""
    apparent_loss = (first - second) / (first + 1e-6)

    print("\n" + "=" * 60)
    print("E1 baseline stability (built-up grid cells)")
    print("=" * 60)
    print(f"  pairs: {pair_names[0]} vs {pair_names[1]}")
    print(f"  cells with valid coverage in both: {n_cells:,}")
    print(f"  median coherence: {np.median(first):.3f} | {np.median(second):.3f}")
    print(f"  correlation between the two pre-conflict pairs: "
          f"{pearson_correlation(first, second):.3f}")
    print(f"  mean absolute difference: {np.mean(np.abs(first - second)):.3f}")
    print(f"  median relative difference: "
          f"{np.median(np.abs(first - second) / ((first + second) / 2)) * 100:.1f}%")

    print("\n  False-positive floor (intact city flagged as damaged):")
    for class_value, threshold in sorted(config.DAMAGE_THRESHOLDS.items()):
        label = config.DAMAGE_CLASS_LABELS[class_value].split()[0].lower()
        rate = (apparent_loss >= threshold).mean() * 100
        print(f"    >= {int(threshold * 100)}% loss ({label}): {rate:.1f}% of cells")


def main() -> None:
    config.configure_gdal_proj_env()
    config.ensure_processing_dirs()
    buildings_gdf = load_buildings()
    grid_gdf = reference_grid(config.GRID_CELL_SIZE_M)
    grid_gdf = built_up_cells(grid_gdf, buildings_gdf)

    min_pixels = config.grid_min_pixels(config.GRID_CELL_SIZE_M)
    first, second, pair_names, n_cells = e1_pair_coherence(grid_gdf, min_pixels)
    report_baseline(first, second, pair_names, n_cells)


if __name__ == "__main__":
    main()
