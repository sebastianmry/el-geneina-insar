"""Smoke tests for the footprint quality control in clean_buildings.py.

Uses a small synthetic GeoDataFrame in the output CRS, so no raster or download
is required. Each test targets one filter category.
"""

import geopandas as gpd
from shapely.geometry import Polygon, Point

import clean_buildings
import config


def _square(x: float, y: float, size: float) -> Polygon:
    """Axis-aligned square footprint with a lower-left corner at (x, y)."""
    return Polygon([(x, y), (x + size, y), (x + size, y + size), (x, y + size)])


def _synthetic_footprints() -> gpd.GeoDataFrame:
    """One clean building plus one example of each removable defect.

    Coordinates sit inside the AOI (reprojected from the configured bounds), so
    only the intended defects are removed and the AOI filter keeps the rest.
    """
    bounds = config.load_aoi_bounds()
    aoi_centroid = (
        gpd.GeoSeries(
            [Point((bounds["west"] + bounds["east"]) / 2,
                   (bounds["south"] + bounds["north"]) / 2)],
            crs="EPSG:4326",
        )
        .to_crs(config.OUTPUT_CRS)
        .iloc[0]
    )
    cx, cy = aoi_centroid.x, aoi_centroid.y

    clean = _square(cx, cy, 12.0)            # ~144 m2, well-formed
    duplicate = _square(cx, cy, 12.0)        # exact duplicate of clean
    micro = _square(cx + 100, cy, 0.5)       # 0.25 m2, below the area floor
    sliver = Polygon([                       # long thin wall, low compactness
        (cx + 200, cy), (cx + 240, cy),
        (cx + 240, cy + 0.2), (cx + 200, cy + 0.2),
    ])
    construction = _square(cx + 300, cy, 12.0)
    far_away = _square(cx + 1_000_000, cy, 12.0)  # outside the AOI

    return gpd.GeoDataFrame(
        {
            "building": ["yes", "yes", "yes", "yes", "construction", "yes"],
            "geometry": [clean, duplicate, micro, sliver, construction, far_away],
        },
        crs=config.OUTPUT_CRS,
    )


def test_each_filter_removes_its_target():
    footprints = _synthetic_footprints()
    clean_gdf, removal_log = clean_buildings.clean_buildings(footprints)

    # Only the single well-formed building survives.
    assert len(clean_gdf) == 1
    assert clean_gdf.iloc[0]["building"] == "yes"

    removed = dict(removal_log)
    assert removed["duplicate geometry"] == 1
    assert removed[f"micro polygon (< {config.MIN_BUILDING_AREA_M2:g} m2)"] == 1
    assert removed["outside AOI"] == 1
    assert removed["excluded building tag (construction)"] == 1
    assert removed["TOTAL removed"] == 5


def test_clean_layer_keeps_the_output_crs():
    footprints = _synthetic_footprints()
    clean_gdf, _ = clean_buildings.clean_buildings(footprints)
    assert clean_gdf.crs == footprints.crs


def test_clean_geometries_are_all_valid():
    footprints = _synthetic_footprints()
    clean_gdf, _ = clean_buildings.clean_buildings(footprints)
    assert bool(clean_gdf.geometry.is_valid.all())
