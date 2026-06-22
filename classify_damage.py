"""Stage 3: building-level damage classification from coherence loss.

For each building footprint the InSAR coherence is aggregated over every raster
pixel touching the polygon (zonal statistics, not a single centroid sample).
This uses the full footprint area, yields a per-building pixel count and spread
as an uncertainty measure, and is robust to small geolocation offsets.

Damage is derived from the relative coherence loss against the pre-conflict
reference epoch E1 and binned into four classes. Buildings with too few valid
pixels (config.MIN_BUILDING_PIXELS) in the reference or the compared epoch are
flagged as insufficient coverage (config.DAMAGE_NODATA) and excluded from the
damage statistics.

Output: a GeoPackage of building footprints with, per epoch, mean coherence,
valid-pixel count, coherence spread, relative loss and damage class columns
(config.DAMAGE_BUILDINGS_FILE).

    python classify_damage.py
"""

from __future__ import annotations

import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from exactextract import exact_extract

import config


def zonal_coherence(
    buildings_gdf: gpd.GeoDataFrame, tif_path: Path
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Aggregate the coherence band (band 2) over each building footprint.

    Returns per-building (area-weighted mean, covered-pixel count, standard
    deviation). Pixels outside [0, 1] or equal to the raster no-data value are
    masked first. exactextract weights each pixel by its fractional overlap with
    the polygon, which matters at this footprint size (~9.5 pixels per building)
    and is far faster than per-feature rasterization.
    """
    with rasterio.open(tif_path) as coherence_src:
        coherence = coherence_src.read(2).astype("float32")
        if coherence_src.nodata is not None:
            coherence[coherence == coherence_src.nodata] = np.nan
        coherence[(coherence > 1) | (coherence < config.COH_VALID_MIN)] = np.nan
        profile = coherence_src.profile.copy()

    profile.update(count=1, dtype="float32", nodata=float("nan"))
    with rasterio.MemoryFile() as memfile:
        with memfile.open(**profile) as masked_ds:
            masked_ds.write(coherence, 1)
        with memfile.open() as masked_ds:
            stats_df = exact_extract(
                masked_ds, buildings_gdf, ["mean", "count", "stdev"],
                output="pandas",
            )

    mean = stats_df["mean"].to_numpy(dtype=float)
    count = stats_df["count"].to_numpy(dtype=float)
    std = stats_df["stdev"].to_numpy(dtype=float)
    return mean, count, std


def load_buildings() -> gpd.GeoDataFrame:
    """Load building footprints in the output CRS, preferring the cleaned layer.

    When the quality-controlled file from clean_buildings.py is present it is
    used directly. Otherwise the raw HOT OSM download is read and only the
    minimal validity filter is applied, so the pipeline still runs end to end.
    """
    if config.BUILDINGS_CLEAN_FILE.exists():
        print(f"Loading cleaned buildings: {config.BUILDINGS_CLEAN_FILE.name}")
        buildings_gdf = gpd.read_file(config.BUILDINGS_CLEAN_FILE)
        buildings_gdf = buildings_gdf.to_crs(config.OUTPUT_CRS)
        print(f"Buildings: {len(buildings_gdf):,}")
        return buildings_gdf

    print("Loading raw buildings (run clean_buildings.py for the QA layer)...")
    buildings_gdf = gpd.read_file(config.BUILDINGS_FILE)
    buildings_gdf = buildings_gdf.to_crs(config.OUTPUT_CRS)
    buildings_gdf = buildings_gdf[buildings_gdf.geometry.is_valid].copy()
    buildings_gdf = buildings_gdf.reset_index(drop=True)
    print(f"Buildings: {len(buildings_gdf):,}")
    return buildings_gdf


def add_epoch_coherence(features_gdf: gpd.GeoDataFrame) -> None:
    """Add coh_<epoch>, n_<epoch> and std_<epoch> columns via zonal statistics.

    Works on any polygon layer (building footprints or grid cells). For epochs
    with several coherence pairs the per-pair means are averaged; the valid-pixel
    count is taken as the minimum across pairs (the conservative coverage), and
    the spread is averaged.
    """
    print("Aggregating coherence over footprints...")
    for epoch, tif_names in config.EPOCH_COH_TIFS.items():
        print(f"  {epoch}...")
        pair_means, pair_counts, pair_stds = [], [], []
        for tif_name in tif_names:
            start = time.time()
            mean, count, std = zonal_coherence(
                features_gdf, config.COH_DIR / tif_name
            )
            print(f"    {tif_name}: {time.time() - start:.0f}s")
            pair_means.append(mean)
            pair_counts.append(count)
            pair_stds.append(std)

        features_gdf[f"coh_{epoch}"] = np.nanmean(pair_means, axis=0)
        features_gdf[f"n_{epoch}"] = np.min(pair_counts, axis=0)
        features_gdf[f"std_{epoch}"] = np.nanmean(pair_stds, axis=0)

        print(f"    mean coherence: {np.nanmean(features_gdf[f'coh_{epoch}']):.3f}")


def add_damage_classes(
    features_gdf: gpd.GeoDataFrame, min_pixels: float = config.MIN_BUILDING_PIXELS
) -> None:
    """Add rel_<epoch> and damage_<epoch> columns from relative coherence loss.

    A feature is classified only where both the reference epoch E1 and the
    compared epoch have at least ``min_pixels`` valid pixels. Otherwise the
    damage class is config.DAMAGE_NODATA and the relative loss NaN. The same
    logic serves the building footprints and the resolution-matched grid; only
    the coverage threshold differs (see classify_grid.py).
    """
    print("\nComputing damage classes...")
    has_coverage = _coverage_columns(features_gdf, min_pixels)
    reference_covered = has_coverage("E1")

    for epoch in config.DAMAGE_EPOCHS:
        covered = reference_covered & has_coverage(epoch)

        relative_loss = (features_gdf["coh_E1"] - features_gdf[f"coh_{epoch}"]) / (
            features_gdf["coh_E1"] + 1e-6
        )
        relative_loss = relative_loss.where(covered, other=np.nan)
        features_gdf[f"rel_{epoch}"] = relative_loss

        damage_class = np.full(len(features_gdf), config.DAMAGE_NODATA, dtype=int)
        damage_class[covered.to_numpy()] = 0
        for class_value, threshold in sorted(config.DAMAGE_THRESHOLDS.items()):
            damage_class[(relative_loss >= threshold).to_numpy()] = class_value
        features_gdf[f"damage_{epoch}"] = damage_class

        print_damage_summary(features_gdf, epoch)


def _coverage_columns(features_gdf: gpd.GeoDataFrame, min_pixels: float):
    """Return a predicate that tests an epoch for sufficient pixel coverage."""
    def has_coverage(epoch: str):
        return features_gdf[f"n_{epoch}"] >= min_pixels
    return has_coverage


def print_damage_summary(buildings_gdf: gpd.GeoDataFrame, epoch: str) -> None:
    """Print the affected / severe percentages for one epoch (covered buildings)."""
    damage = buildings_gdf[f"damage_{epoch}"]
    classified = damage[damage >= 0]
    total = len(classified)
    if total == 0:
        print(f"  {epoch}: no buildings with sufficient coverage")
        return
    affected = (classified >= 1).sum()
    severe = (classified >= 3).sum()
    excluded = int((damage == config.DAMAGE_NODATA).sum())
    print(f"  {epoch}: {affected / total * 100:.1f}% affected, "
          f"{severe / total * 100:.1f}% severe  "
          f"(classified: {total:,} | excluded: {excluded:,})")


def main() -> None:
    config.ensure_processing_dirs()

    if config.DAMAGE_BUILDINGS_FILE.exists():
        print(f"Already present, loading: {config.DAMAGE_BUILDINGS_FILE}")
        buildings_gdf = gpd.read_file(config.DAMAGE_BUILDINGS_FILE)
        print(f"Buildings: {len(buildings_gdf):,}")
        for epoch in config.DAMAGE_EPOCHS:
            print_damage_summary(buildings_gdf, epoch)
        return

    buildings_gdf = load_buildings()
    add_epoch_coherence(buildings_gdf)
    add_damage_classes(buildings_gdf)

    buildings_gdf.to_file(config.DAMAGE_BUILDINGS_FILE, driver="GPKG")
    print(f"\nSaved: {config.DAMAGE_BUILDINGS_FILE}")


if __name__ == "__main__":
    main()
