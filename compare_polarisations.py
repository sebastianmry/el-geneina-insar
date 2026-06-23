"""Stage 3e: dual-polarisation (VV/VH) diagnostic.

The coherence change detection runs on two polarisations. VV is the primary
co-pol channel; VH is the cross-pol channel, dominated by volume scattering and
therefore lower in absolute coherence. This stage characterises what the second
channel contributes before it is fused into the damage classification:

  1. How correlated VV and VH coherence are. A low correlation means VH carries
     information independent of VV, so averaging the two relative losses reduces
     noise rather than just repeating the same signal.
  2. How differently each channel decorrelates in the rainy season, measured as
     the per-polarisation environmental retention R_env over unbuilt cells. The
     key result for this site is that VH is far more robust to the seasonal
     decorrelation that inflates the VV-based damage extent for E2b and E3.

The fusion itself (mean of the per-polarisation relative loss) lives in
classify_damage.py and correct_baseline_drift.py; this script only reports the
relationship.

    python compare_polarisations.py
"""

from __future__ import annotations

import numpy as np

import config
from check_baseline import pearson_correlation
from classify_damage import add_epoch_coherence, load_buildings
from correct_baseline_drift import environmental_retention, grid_with_counts

EPOCHS = ["E1", *config.DAMAGE_EPOCHS]


def paired_coherence(built_up_gdf, epoch: str) -> tuple[np.ndarray, np.ndarray]:
    """Finite VV/VH coherence pairs for one epoch over built-up cells."""
    vv = built_up_gdf[f"coh_{epoch}_{config.COH_POLARISATIONS[0]}"].to_numpy(float)
    vh = built_up_gdf[f"coh_{epoch}_{config.COH_POLARISATIONS[1]}"].to_numpy(float)
    finite = np.isfinite(vv) & np.isfinite(vh)
    return vv[finite], vh[finite]


def print_summary(built_up_gdf, retention: dict) -> None:
    """Print the per-epoch correlation and the per-polarisation retention."""
    print("\n" + "=" * 60)
    print("VV/VH coherence correlation (built-up cells)")
    print("=" * 60)
    for epoch in EPOCHS:
        vv, vh = paired_coherence(built_up_gdf, epoch)
        print(f"  {epoch}: mean VV {vv.mean():.3f}  mean VH {vh.mean():.3f}  "
              f"r {pearson_correlation(vv, vh):.3f}  n {len(vv):,}")

    primary, cross = config.COH_POLARISATIONS[0], config.COH_POLARISATIONS[1]
    print("\nPer-polarisation environmental retention R_env (unbuilt cells)")
    for epoch in config.DAMAGE_EPOCHS:
        print(f"  {epoch}: {primary} {retention[epoch][primary]:.3f}  "
              f"{cross} {retention[epoch][cross]:.3f}")


def main() -> None:
    config.configure_gdal_proj_env()
    config.ensure_processing_dirs()
    buildings_gdf = load_buildings()

    cell_size_m = config.GRID_CELL_SIZE_M
    min_pixels = config.grid_min_pixels(cell_size_m)
    grid_gdf = grid_with_counts(buildings_gdf, cell_size_m)
    add_epoch_coherence(grid_gdf)

    retention, _ = environmental_retention(grid_gdf, min_pixels)
    built_up_gdf = grid_gdf[grid_gdf["building_count"] > 0]
    print_summary(built_up_gdf, retention)


if __name__ == "__main__":
    main()
