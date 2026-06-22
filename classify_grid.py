"""Stage 3b: resolution-matched grid damage classification.

Individual HOT OSM footprints (median ~15 m2) are far smaller than a 10 m
Sentinel-1 pixel (100 m2), so per-building coherence is a sub-pixel sample and
adjacent buildings share pixels. This stage moves the statistic onto a grid
whose cells each average several independent coherence estimates, which is the
defensible unit for reporting (and matches Sentinel-1 coherence damage-density
products such as UNOSAT).

The grid carries the same per-epoch coherence, valid-pixel count, spread,
relative loss and damage class as the building layer, computed with the shared
logic in classify_damage.py. Each building then inherits the damage class of the
cell it falls in, so the map keeps the footprint view while the headline numbers
rest on the grid. Statistics are reported over built-up cells only (cells that
contain at least one footprint).

    python classify_grid.py            # primary cell size + sensitivity table

Outputs:
  config.grid_damage_file(size)        per cell size
  config.DAMAGE_BUILDINGS_GRID_FILE    buildings with the inherited class
"""

from __future__ import annotations

import numpy as np
import geopandas as gpd
import rasterio
from shapely.geometry import box

import config
from classify_damage import add_epoch_coherence, add_damage_classes, load_buildings


def reference_grid(cell_size_m: float) -> gpd.GeoDataFrame:
    """Build a grid of square cells over the reference raster, aligned to it.

    Cells are snapped to the raster origin so they tile whole pixels, and the
    grid spans the full reference extent. Cells are filtered to the built-up
    area later.
    """
    with rasterio.open(config.REFERENCE_COH_TIF) as reference_src:
        bounds = reference_src.bounds
        crs = reference_src.crs

    x_edges = np.arange(bounds.left, bounds.right + cell_size_m, cell_size_m)
    y_edges = np.arange(bounds.bottom, bounds.top + cell_size_m, cell_size_m)
    cells = [
        box(x, y, x + cell_size_m, y + cell_size_m)
        for x in x_edges[:-1]
        for y in y_edges[:-1]
    ]
    grid_gdf = gpd.GeoDataFrame({"cell_id": range(len(cells))}, geometry=cells, crs=crs)
    return grid_gdf


def built_up_cells(
    grid_gdf: gpd.GeoDataFrame, buildings_gdf: gpd.GeoDataFrame
) -> gpd.GeoDataFrame:
    """Keep only cells that contain at least one building, with a count column."""
    centroids_gdf = buildings_gdf.copy()
    centroids_gdf["geometry"] = buildings_gdf.geometry.centroid
    joined = gpd.sjoin(centroids_gdf, grid_gdf, how="inner", predicate="within")
    counts = joined.groupby("cell_id").size()

    grid_gdf = grid_gdf.set_index("cell_id")
    grid_gdf["building_count"] = counts
    grid_gdf = grid_gdf[grid_gdf["building_count"].notna()].reset_index()
    grid_gdf["building_count"] = grid_gdf["building_count"].astype(int)
    print(f"  built-up cells: {len(grid_gdf):,}")
    return grid_gdf


def classify_grid(
    cell_size_m: float, buildings_gdf: gpd.GeoDataFrame
) -> gpd.GeoDataFrame:
    """Classify damage on a grid of the given cell size over built-up cells."""
    print(f"\n=== Grid {int(cell_size_m)} m ===")
    grid_gdf = reference_grid(cell_size_m)
    grid_gdf = built_up_cells(grid_gdf, buildings_gdf)

    add_epoch_coherence(grid_gdf)
    add_damage_classes(grid_gdf, min_pixels=config.grid_min_pixels(cell_size_m))
    return grid_gdf


def attribute_to_buildings(
    buildings_gdf: gpd.GeoDataFrame, grid_gdf: gpd.GeoDataFrame
) -> gpd.GeoDataFrame:
    """Assign each building the attributes of the grid cell it falls in.

    The building inherits the cell coherence, valid-pixel count, relative loss
    and damage class for every epoch, so the footprint layer is self-contained
    for all figures while the underlying statistic stays grid-based.
    """
    coh_columns = [f"coh_{epoch}" for epoch in config.EPOCH_COH_TIFS]
    n_columns = [f"n_{epoch}" for epoch in config.EPOCH_COH_TIFS]
    damage_columns = [f"damage_{epoch}" for epoch in config.DAMAGE_EPOCHS]
    rel_columns = [f"rel_{epoch}" for epoch in config.DAMAGE_EPOCHS]
    inherited = [*coh_columns, *n_columns, *damage_columns, *rel_columns]
    cell_attributes = grid_gdf[["geometry", *inherited]]

    centroids_gdf = buildings_gdf.copy()
    centroids_gdf["geometry"] = buildings_gdf.geometry.centroid
    joined = gpd.sjoin(
        centroids_gdf, cell_attributes, how="left", predicate="within"
    )

    result_gdf = buildings_gdf.copy()
    for column in inherited:
        result_gdf[column] = joined[column].to_numpy()
    # Buildings outside any built-up cell (none expected) are flagged.
    for column in damage_columns:
        result_gdf[column] = (
            result_gdf[column].fillna(config.DAMAGE_NODATA).astype(int)
        )
    return result_gdf


def sensitivity_row(grid_gdf: gpd.GeoDataFrame, epoch: str) -> tuple[float, float]:
    """Return (affected_pct, severe_pct) over classified cells for an epoch."""
    damage = grid_gdf[f"damage_{epoch}"]
    classified = damage[damage >= 0]
    total = len(classified)
    if total == 0:
        return float("nan"), float("nan")
    return (
        (classified >= 1).sum() / total * 100.0,
        (classified >= 3).sum() / total * 100.0,
    )


def print_sensitivity_table(results: dict[float, gpd.GeoDataFrame]) -> None:
    """Print affected / severe percentages per epoch across cell sizes."""
    print("\n" + "=" * 60)
    print("Sensitivity to grid cell size (affected% / severe%)")
    print("=" * 60)
    header = "  epoch | " + " | ".join(f"{int(s)} m" for s in results)
    print(header)
    for epoch in config.DAMAGE_EPOCHS:
        cells = []
        for grid_gdf in results.values():
            affected, severe = sensitivity_row(grid_gdf, epoch)
            cells.append(f"{affected:5.1f}/{severe:4.1f}")
        print(f"  {epoch:5s} | " + " | ".join(cells))


def main() -> None:
    config.ensure_processing_dirs()
    buildings_gdf = load_buildings()

    results: dict[float, gpd.GeoDataFrame] = {}
    for cell_size_m in config.GRID_CELL_SIZES_M:
        grid_gdf = classify_grid(cell_size_m, buildings_gdf)
        grid_gdf.to_file(config.grid_damage_file(cell_size_m), driver="GPKG")
        print(f"  saved: {config.grid_damage_file(cell_size_m)}")
        results[cell_size_m] = grid_gdf

    primary_grid = results[config.GRID_CELL_SIZE_M]
    buildings_from_grid = attribute_to_buildings(buildings_gdf, primary_grid)
    buildings_from_grid.to_file(config.DAMAGE_BUILDINGS_GRID_FILE, driver="GPKG")
    print(f"\nSaved buildings (class from {int(config.GRID_CELL_SIZE_M)} m grid): "
          f"{config.DAMAGE_BUILDINGS_GRID_FILE}")

    print_sensitivity_table(results)


if __name__ == "__main__":
    main()
