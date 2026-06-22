"""Stage 3c: rainy-season baseline-drift correction.

The Sahel rains begin in June, which lowers interferometric coherence over bare
and vegetated ground regardless of the conflict. Because the raw damage signal
is the coherence drop relative to the pre-conflict reference E1, this seasonal
decorrelation inflates the affected extent for the June (E2b) and July (E3)
epochs.

The correction estimates that seasonal signal from stable unbuilt reference
areas (grid cells that contain no building) and removes it from the built-up
cells. For each epoch the environmental retention is

    R_env = median(coh_epoch over unbuilt cells) / median(coh_E1 over unbuilt cells)

so the coherence a built-up cell would show under seasonal drift alone is
coh_E1 * R_env. Damage is then the loss beyond that expectation:

    corrected relative loss = 1 - coh_epoch / (coh_E1 * R_env)

Unbuilt surfaces are bare soil and sparse vegetation, which decorrelate more
readily than the hard targets of a built environment, so R_env is a strong
(conservative) estimate of the seasonal effect. The corrected percentages
therefore read as a lower bound on damage, and the raw percentages as an upper
bound; the truth lies between them.

    python correct_baseline_drift.py

Outputs:
  config.grid_drift_file(size)   built-up cells with raw and corrected classes
"""

from __future__ import annotations

import geopandas as gpd
import numpy as np

import config
from classify_damage import add_damage_classes, add_epoch_coherence, load_buildings
from classify_grid import reference_grid


def grid_with_counts(buildings_gdf, cell_size_m: float) -> gpd.GeoDataFrame:
    """Reference grid over the full extent with a building_count per cell.

    Unlike classify_grid.built_up_cells, unbuilt cells are kept (count 0): the
    seasonal reference is estimated from them.
    """
    grid_gdf = reference_grid(cell_size_m)
    centroids_gdf = buildings_gdf.copy()
    centroids_gdf["geometry"] = buildings_gdf.geometry.centroid
    joined = gpd.sjoin(centroids_gdf, grid_gdf, how="inner", predicate="within")
    counts = joined.groupby("cell_id").size()

    grid_gdf = grid_gdf.set_index("cell_id")
    grid_gdf["building_count"] = counts.reindex(grid_gdf.index).fillna(0).astype(int)
    return grid_gdf.reset_index()


def environmental_retention(
    grid_gdf: gpd.GeoDataFrame, min_pixels: float
) -> tuple[dict[str, float], float]:
    """Seasonal retention R_env per epoch from stable unbuilt reference cells."""
    unbuilt = grid_gdf[grid_gdf["building_count"] == 0]
    reference_valid = unbuilt["n_E1"] >= min_pixels
    reference_median = float(np.nanmedian(unbuilt.loc[reference_valid, "coh_E1"]))

    retention: dict[str, float] = {}
    for epoch in config.DAMAGE_EPOCHS:
        valid = unbuilt[f"n_{epoch}"] >= min_pixels
        epoch_median = float(np.nanmedian(unbuilt.loc[valid, f"coh_{epoch}"]))
        retention[epoch] = epoch_median / reference_median
    return retention, reference_median


def add_corrected_classes(
    grid_gdf: gpd.GeoDataFrame, retention: dict[str, float], min_pixels: float
) -> None:
    """Add relc_<epoch> and damagec_<epoch> from the drift-corrected loss."""
    reference_covered = grid_gdf["n_E1"] >= min_pixels
    for epoch in config.DAMAGE_EPOCHS:
        covered = reference_covered & (grid_gdf[f"n_{epoch}"] >= min_pixels)
        expected = grid_gdf["coh_E1"] * retention[epoch]
        relative_loss = (expected - grid_gdf[f"coh_{epoch}"]) / (expected + 1e-6)
        relative_loss = relative_loss.where(covered, other=np.nan)
        grid_gdf[f"relc_{epoch}"] = relative_loss

        damage_class = np.full(len(grid_gdf), config.DAMAGE_NODATA, dtype=int)
        damage_class[covered.to_numpy()] = 0
        for class_value, threshold in sorted(config.DAMAGE_THRESHOLDS.items()):
            damage_class[(relative_loss >= threshold).to_numpy()] = class_value
        grid_gdf[f"damagec_{epoch}"] = damage_class


def _share(series, threshold_class: int) -> float:
    """Percentage of classified cells at or above a damage class."""
    classified = series[series >= 0]
    if len(classified) == 0:
        return float("nan")
    return (classified >= threshold_class).sum() / len(classified) * 100.0


def report(grid_gdf: gpd.GeoDataFrame, retention: dict[str, float],
           reference_median: float) -> None:
    """Print the retention factors and the raw vs corrected comparison."""
    built_up = grid_gdf[grid_gdf["building_count"] > 0]

    print("\n" + "=" * 60)
    print("Rainy-season environmental retention (unbuilt reference cells)")
    print("=" * 60)
    print(f"  E1 unbuilt median coherence: {reference_median:.3f}")
    for epoch in config.DAMAGE_EPOCHS:
        print(f"  R_env({epoch}): {retention[epoch]:.3f}  "
              f"(seasonal loss {(1 - retention[epoch]) * 100:.0f}%)")

    print("\n" + "=" * 60)
    print("Affected / severe of built-up cells: raw vs drift-corrected")
    print("=" * 60)
    print("  epoch |     raw     | drift-corrected")
    for epoch in config.DAMAGE_EPOCHS:
        raw = (_share(built_up[f"damage_{epoch}"], 1),
               _share(built_up[f"damage_{epoch}"], 3))
        corrected = (_share(built_up[f"damagec_{epoch}"], 1),
                     _share(built_up[f"damagec_{epoch}"], 3))
        print(f"  {epoch:5s} | {raw[0]:5.1f} / {raw[1]:4.1f} | "
              f"{corrected[0]:5.1f} / {corrected[1]:4.1f}")


def main() -> None:
    config.configure_gdal_proj_env()
    config.ensure_processing_dirs()
    buildings_gdf = load_buildings()

    cell_size_m = config.GRID_CELL_SIZE_M
    min_pixels = config.grid_min_pixels(cell_size_m)
    grid_gdf = grid_with_counts(buildings_gdf, cell_size_m)
    print(f"  cells: {len(grid_gdf):,} "
          f"(built-up {int((grid_gdf['building_count'] > 0).sum()):,}, "
          f"unbuilt {int((grid_gdf['building_count'] == 0).sum()):,})")

    add_epoch_coherence(grid_gdf)
    add_damage_classes(grid_gdf, min_pixels=min_pixels)

    retention, reference_median = environmental_retention(grid_gdf, min_pixels)
    add_corrected_classes(grid_gdf, retention, min_pixels)
    report(grid_gdf, retention, reference_median)

    built_up = grid_gdf[grid_gdf["building_count"] > 0].copy()
    output_path = config.grid_drift_file(cell_size_m)
    built_up.to_file(output_path, driver="GPKG")
    print(f"\nSaved: {output_path}")


if __name__ == "__main__":
    main()
