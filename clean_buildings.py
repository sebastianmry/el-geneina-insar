"""Stage 0: quality control of the HOT OSM building footprints.

The damage statistics rest on the footprint layer, so the raw HOT OSM download
is screened once before any coherence is sampled. The screening is intentionally
conservative: it removes only geometries that cannot represent a real standing
building inside the study area, which keeps the damage percentages unbiased.

Each filter is applied in a fixed order and every removed feature is counted by
category. The counts are written to a Markdown report (config.CLEANING_REPORT_PATH)
so the cleaning is fully reproducible and transparent.

Filters, in order:
  1. invalid geometries        repaired with make_valid, dropped if still broken
  2. empty or missing geometry  no usable outline
  3. non-polygonal geometry     points or lines that are not building outlines
  4. duplicate geometry         exact geometric duplicates of an earlier feature
  5. micro polygons             area below config.MIN_BUILDING_AREA_M2
  6. line-like slivers          compactness below config.MIN_BUILDING_COMPACTNESS
  7. excluded building tags     config.EXCLUDED_BUILDING_TAGS (e.g. construction)
  8. outside the AOI            footprints that do not intersect the study area

    python clean_buildings.py

Outputs:
  config.BUILDINGS_CLEAN_FILE     quality-controlled footprints
  config.CLEANING_REPORT_PATH     removal report (counts per category)
"""

from __future__ import annotations

from datetime import date

import geopandas as gpd
import numpy as np
from shapely.geometry import box

import config


def _aoi_polygon(target_crs) -> "gpd.GeoSeries":
    """Return the AOI bounding box as a single polygon in the target CRS."""
    bounds = config.load_aoi_bounds()
    aoi_box = box(bounds["west"], bounds["south"], bounds["east"], bounds["north"])
    return gpd.GeoSeries([aoi_box], crs="EPSG:4326").to_crs(target_crs).iloc[0]


def clean_buildings(
    buildings_gdf: gpd.GeoDataFrame,
) -> tuple[gpd.GeoDataFrame, list[tuple[str, int]]]:
    """Apply the quality filters and return the clean layer and a removal log.

    The input is expected in config.OUTPUT_CRS. The returned log is a list of
    (category, removed_count) pairs in the order the filters ran.
    """
    removal_log: list[tuple[str, int]] = []
    start_count = len(buildings_gdf)

    def record(category: str, keep_mask) -> None:
        removed = int((~keep_mask).sum())
        removal_log.append((category, removed))

    # 1. Invalid geometries: repair, then drop anything still broken.
    invalid_mask = ~buildings_gdf.geometry.is_valid
    if invalid_mask.any():
        buildings_gdf.loc[invalid_mask, "geometry"] = buildings_gdf.loc[
            invalid_mask, "geometry"
        ].make_valid()
    valid_mask = buildings_gdf.geometry.is_valid
    record("invalid geometry (unrepairable)", valid_mask)
    buildings_gdf = buildings_gdf[valid_mask].copy()

    # 2. Empty or missing geometry.
    nonempty_mask = ~(buildings_gdf.geometry.is_empty | buildings_gdf.geometry.isna())
    record("empty or missing geometry", nonempty_mask)
    buildings_gdf = buildings_gdf[nonempty_mask].copy()

    # 3. Non-polygonal geometry (points, lines, or mixed collections).
    polygon_mask = buildings_gdf.geom_type.isin(["Polygon", "MultiPolygon"])
    record("non-polygonal geometry", polygon_mask)
    buildings_gdf = buildings_gdf[polygon_mask].copy()

    # 4. Exact duplicate geometries (keep the first occurrence).
    duplicate_mask = buildings_gdf.geometry.duplicated(keep="first")
    record("duplicate geometry", ~duplicate_mask)
    buildings_gdf = buildings_gdf[~duplicate_mask].copy()

    # 5. Micro polygons below any plausible building footprint.
    area = buildings_gdf.geometry.area
    area_mask = area >= config.MIN_BUILDING_AREA_M2
    record(f"micro polygon (< {config.MIN_BUILDING_AREA_M2:g} m2)", area_mask)
    buildings_gdf = buildings_gdf[area_mask].copy()

    # 6. Line-like slivers (low compactness, typically a traced wall).
    area = buildings_gdf.geometry.area
    perimeter = buildings_gdf.geometry.length
    compactness = (4.0 * np.pi * area) / (perimeter ** 2)
    compact_mask = compactness >= config.MIN_BUILDING_COMPACTNESS
    record(
        f"line-like sliver (compactness < {config.MIN_BUILDING_COMPACTNESS:g})",
        compact_mask,
    )
    buildings_gdf = buildings_gdf[compact_mask].copy()

    # 7. Excluded building tags (e.g. sites still under construction).
    tag_mask = ~buildings_gdf["building"].isin(config.EXCLUDED_BUILDING_TAGS)
    record(
        "excluded building tag (" + ", ".join(sorted(config.EXCLUDED_BUILDING_TAGS)) + ")",
        tag_mask,
    )
    buildings_gdf = buildings_gdf[tag_mask].copy()

    # 8. Footprints outside the study area.
    aoi_polygon = _aoi_polygon(buildings_gdf.crs)
    inside_mask = buildings_gdf.geometry.intersects(aoi_polygon)
    record("outside AOI", inside_mask)
    buildings_gdf = buildings_gdf[inside_mask].copy()

    buildings_gdf = buildings_gdf.reset_index(drop=True)
    total_removed = start_count - len(buildings_gdf)
    removal_log.append(("TOTAL removed", total_removed))
    return buildings_gdf, removal_log


def write_report(
    start_count: int, clean_count: int, removal_log: list[tuple[str, int]]
) -> None:
    """Write the Markdown removal report next to the documentation."""
    lines = [
        "# Footprint cleaning report",
        "",
        f"Generated by `clean_buildings.py` on {date.today().isoformat()}.",
        "",
        "Quality control of the HOT OSM building footprints before damage",
        "classification. Filters run in the order listed and remove only",
        "geometries that cannot represent a real standing building, so the",
        "damage percentages stay unbiased.",
        "",
        f"Source: `{config.BUILDINGS_FILE.name}` ({start_count:,} features)  ",
        f"Output: `{config.BUILDINGS_CLEAN_FILE.name}` ({clean_count:,} features)  ",
        f"Reprojected to {config.OUTPUT_CRS}.",
        "",
        "| Filter | Features removed |",
        "| :--- | ---: |",
    ]
    for category, removed in removal_log:
        if category == "TOTAL removed":
            continue
        lines.append(f"| {category} | {removed:,} |")
    total_removed = start_count - clean_count
    retained_pct = clean_count / start_count * 100.0
    lines.append(f"| **Total removed** | **{total_removed:,}** |")
    lines.append("")
    lines.append(
        f"Retained {clean_count:,} of {start_count:,} footprints "
        f"({retained_pct:.2f} %)."
    )
    lines.append("")

    config.CLEANING_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.CLEANING_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    config.configure_gdal_proj_env()
    print("Loading raw footprints...")
    buildings_gdf = gpd.read_file(config.BUILDINGS_FILE).to_crs(config.OUTPUT_CRS)
    start_count = len(buildings_gdf)
    print(f"  raw footprints: {start_count:,}")

    clean_gdf, removal_log = clean_buildings(buildings_gdf)

    print("\nRemoval summary:")
    for category, removed in removal_log:
        print(f"  {category:45s} {removed:>8,}")
    print(f"  clean footprints: {len(clean_gdf):,}")

    config.BUILDINGS_CLEAN_FILE.parent.mkdir(parents=True, exist_ok=True)
    clean_gdf.to_file(config.BUILDINGS_CLEAN_FILE, driver="GPKG")
    print(f"\nSaved: {config.BUILDINGS_CLEAN_FILE}")

    write_report(start_count, len(clean_gdf), removal_log)
    print(f"Report: {config.CLEANING_REPORT_PATH}")


if __name__ == "__main__":
    main()
