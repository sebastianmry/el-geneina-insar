"""Shared helpers for the visualization scripts.

Loads the classified building footprints and the reference coherence raster,
clips buildings to the area with valid coherence and derives damage statistics.
Keeping this in one place avoids duplicating the loading/clipping logic across
the individual figure scripts.
"""

from __future__ import annotations

from dataclasses import dataclass

import geopandas as gpd
import matplotlib.patheffects as pe
import numpy as np
from matplotlib.patches import Polygon
import rasterio
from rasterio import features as rio_features
from shapely.geometry import box, shape
from shapely.ops import unary_union

import config

# Human-readable label for the projected coordinate reference system.
CRS_LABEL = "EPSG:32634 (UTM zone 34N)"


def add_scale_bar(
    ax, length_m: float = 2000.0, divisions: int = 2, location=(0.06, 0.05)
) -> None:
    """Draw a divided projected scale bar in kilometres at an axes-fraction spot.

    The map axes are in metres (config.OUTPUT_CRS), so the bar length is exact
    rather than an approximation. ``divisions`` splits the bar into equal
    kilometre segments with a tick and label at each boundary (0, 1, 2 km for the
    default 2 km bar). ``location`` is the bar's left end as a fraction of the axes.
    """
    x_min, x_max = ax.get_xlim()
    y_min, y_max = ax.get_ylim()
    span_x, span_y = x_max - x_min, y_max - y_min
    bar_x = x_min + location[0] * span_x
    bar_y = y_min + location[1] * span_y

    stroke = [pe.withStroke(linewidth=2.5, foreground=config.COLOR_BG)]
    ax.plot([bar_x, bar_x + length_m], [bar_y, bar_y], color=config.COLOR_FG,
            linewidth=2.5, solid_capstyle="butt", zorder=10, path_effects=stroke)
    for step in range(divisions + 1):
        tick_x = bar_x + length_m * step / divisions
        ax.plot([tick_x, tick_x], [bar_y, bar_y + 0.012 * span_y],
                color=config.COLOR_FG, linewidth=2.5, zorder=10, path_effects=stroke)
        kilometres = length_m / 1000.0 * step / divisions
        label = f"{kilometres:g} km" if step == divisions else f"{kilometres:g}"
        ax.text(tick_x, bar_y + 0.02 * span_y, label, ha="center", va="bottom",
                color=config.COLOR_FG, fontsize=7.5, fontweight="bold",
                zorder=10, path_effects=stroke)


def draw_coherence_backdrop(ax, reference, alpha: float = 0.30) -> None:
    """Draw the E1 coherence raster as a faint grayscale context layer.

    Higher coherence reads as lighter gray, sketching the stable urban fabric
    behind the footprints without competing with the glowing damage colours.
    Centralised here so every figure shares one backdrop style.
    """
    ax.imshow(reference.coherence, cmap="gray", vmin=0, vmax=0.9,
              extent=reference.extent, origin="upper",
              interpolation="bilinear", alpha=alpha, zorder=0)


def add_attribution(fig, text: str, location=(0.99, 0.015)) -> None:
    """Print a small data-attribution credit in the figure's bottom-right corner.

    The OpenStreetMap footprints are ODbL, which requires the credit to travel
    with the produced map itself, not only the README. Kept as a single muted
    line so it satisfies the licence without cluttering the dark cartography.
    """
    fig.text(location[0], location[1], text, ha="right", va="bottom",
             color=config.COLOR_SUB, fontsize=6.5,
             path_effects=[pe.withStroke(linewidth=1.5, foreground=config.COLOR_BG)],
             zorder=10)


def add_north_arrow(ax, location=(0.955, 0.90)) -> None:
    """Draw a cartographic compass needle: a split diamond with an N above it.

    The north half is filled and the south half is left as an outline, the
    classic two-tone needle. The map is projected with north up
    (config.OUTPUT_CRS), so the needle is a fixed marker, not a computed bearing.
    """
    x, y = location
    top, bottom, waist, half_width = y + 0.050, y - 0.030, y + 0.004, 0.013
    apex, tail = (x, top), (x, bottom)

    north_half = Polygon(
        [apex, (x - half_width, waist), tail], closed=True,
        facecolor=config.COLOR_FG, edgecolor=config.COLOR_BG, linewidth=0.8,
        transform=ax.transAxes, clip_on=False, zorder=10, joinstyle="miter",
    )
    south_half = Polygon(
        [apex, (x + half_width, waist), tail], closed=True,
        facecolor="none", edgecolor=config.COLOR_FG, linewidth=1.0,
        transform=ax.transAxes, clip_on=False, zorder=10, joinstyle="miter",
    )
    ax.add_patch(north_half)
    ax.add_patch(south_half)

    stroke = [pe.withStroke(linewidth=2.0, foreground=config.COLOR_BG)]
    ax.text(x, top + 0.028, "N", transform=ax.transAxes, ha="center", va="center",
            color=config.COLOR_FG, fontsize=11, fontweight="bold",
            path_effects=stroke, zorder=10)


@dataclass
class ReferenceRaster:
    """Reference coherence raster and its plotting extent."""

    coherence: np.ndarray
    extent: list[float]  # [left, right, bottom, top] for imshow
    crs: object
    transform: object


def load_reference_raster() -> ReferenceRaster:
    """Load the E1 reference coherence band, clipped to [0, 1]."""
    with rasterio.open(config.REFERENCE_COH_TIF) as reference_src:
        coherence = np.clip(reference_src.read(2).astype(float), 0, 1)
        bounds = reference_src.bounds
        return ReferenceRaster(
            coherence=coherence,
            extent=[bounds.left, bounds.right, bounds.bottom, bounds.top],
            crs=reference_src.crs,
            transform=reference_src.transform,
        )


def load_damage_buildings(clip_to_valid: bool = True) -> gpd.GeoDataFrame:
    """Load building footprints carrying the damage class of their grid cell.

    Footprints are used for the map only; the reported percentages come from the
    grid itself (load_damage_grid), since the grid cell is the statistical unit.
    """
    print(f"Loading {config.DAMAGE_BUILDINGS_GRID_FILE.name}...")
    buildings_gdf = gpd.read_file(config.DAMAGE_BUILDINGS_GRID_FILE)
    buildings_gdf = buildings_gdf.to_crs(config.OUTPUT_CRS)
    print(f"  {len(buildings_gdf):,} buildings loaded")

    if not clip_to_valid:
        return buildings_gdf
    return clip_to_valid_footprint(buildings_gdf)


def load_damage_buildings_corrected(clip_to_valid: bool = True) -> gpd.GeoDataFrame:
    """Load footprints carrying the drift-corrected damage class of their cell.

    The footprint layer ships the raw grid class; here each building inherits the
    rainy-season-corrected class (damagec_<epoch>) from the drift grid, so the map
    shows the same corrected extent and severity that the headline percentages
    report. Buildings outside any built-up cell keep config.DAMAGE_NODATA.
    """
    buildings_gdf = gpd.read_file(config.DAMAGE_BUILDINGS_GRID_FILE).to_crs(config.OUTPUT_CRS)
    drift_gdf = load_damage_grid_corrected()

    corrected_columns = [f"damagec_{epoch}" for epoch in config.DAMAGE_EPOCHS]
    cell_attributes = drift_gdf[["geometry", *corrected_columns]]

    centroids_gdf = buildings_gdf.copy()
    centroids_gdf["geometry"] = buildings_gdf.geometry.centroid
    joined = gpd.sjoin(centroids_gdf, cell_attributes, how="left", predicate="within")
    # A duplicated index can appear if a centroid sits on a cell boundary.
    joined = joined[~joined.index.duplicated(keep="first")]

    for column in corrected_columns:
        buildings_gdf[column] = (
            joined[column].fillna(config.DAMAGE_NODATA).astype(int).to_numpy()
        )

    print(f"  {len(buildings_gdf):,} buildings with corrected class")
    if not clip_to_valid:
        return buildings_gdf
    return clip_to_valid_footprint(buildings_gdf)


def load_damage_grid() -> gpd.GeoDataFrame:
    """Load the primary classified grid (the statistical unit for percentages)."""
    grid_path = config.grid_damage_file(config.GRID_CELL_SIZE_M)
    print(f"Loading {grid_path.name}...")
    grid_gdf = gpd.read_file(grid_path)
    grid_gdf = grid_gdf.to_crs(config.OUTPUT_CRS)
    print(f"  {len(grid_gdf):,} built-up cells loaded")
    return grid_gdf


def load_damage_grid_corrected() -> gpd.GeoDataFrame:
    """Load the drift-corrected grid of built-up cells.

    Carries both the raw damage classes (damage_<epoch>, upper bound) and the
    rainy-season-corrected classes (damagec_<epoch>, lower bound), so a figure
    can report the bracket rather than a single inflated number.
    """
    grid_path = config.grid_drift_file(config.GRID_CELL_SIZE_M)
    print(f"Loading {grid_path.name}...")
    grid_gdf = gpd.read_file(grid_path)
    grid_gdf = grid_gdf.to_crs(config.OUTPUT_CRS)
    print(f"  {len(grid_gdf):,} built-up cells loaded")
    return grid_gdf


def clip_to_valid_footprint(
    buildings_gdf: gpd.GeoDataFrame, reference: ReferenceRaster | None = None
) -> gpd.GeoDataFrame:
    """Clip buildings to the area where the reference coherence is valid."""
    if reference is None:
        reference = load_reference_raster()
    valid_mask = (reference.coherence > 0.001).astype(np.uint8)
    valid_polygons = [
        shape(geom)
        for geom, value in rio_features.shapes(valid_mask, transform=reference.transform)
        if value == 1
    ]
    if valid_polygons:
        footprint = gpd.GeoDataFrame(
            geometry=[unary_union(valid_polygons)], crs=reference.crs
        )
    else:
        left, right, bottom, top = reference.extent
        footprint = gpd.GeoDataFrame(
            geometry=[box(left, bottom, right, top)], crs=reference.crs
        )

    clipped_gdf = gpd.clip(buildings_gdf, footprint)
    print(f"  {len(clipped_gdf):,} buildings after clipping")
    return clipped_gdf


def damage_percentages(
    buildings_gdf: gpd.GeoDataFrame, epoch: str, column_prefix: str = "damage"
) -> tuple[float, float]:
    """Return (affected_pct, severe_pct) for an epoch, computed from the data.

    Affected = damage class >= 1, severe = damage class >= 3. Cells flagged as
    insufficient coverage (config.DAMAGE_NODATA, negative) are excluded from the
    denominator. Values are derived from the classification, not hardcoded.
    ``column_prefix`` selects the raw ("damage") or drift-corrected ("damagec")
    classes.
    """
    damage = buildings_gdf[f"{column_prefix}_{epoch}"]
    classified = damage[damage >= 0]
    total = len(classified)
    if total == 0:
        return float("nan"), float("nan")
    affected_pct = (classified >= 1).sum() / total * 100.0
    severe_pct = (classified >= 3).sum() / total * 100.0
    return affected_pct, severe_pct
