"""Quality check for the InSAR GeoTIFF outputs.

Verifies that every coherence GeoTIFF exists, is readable, carries a projection
and contains a reasonable number of valid pixels per band.

    python check_quality.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from osgeo import gdal

import config

MIN_VALID_PIXELS = 100


def check_tif(tif_path: Path) -> bool:
    """Report band stats for one GeoTIFF and return True if it looks valid."""
    raster_ds = gdal.Open(str(tif_path))
    if raster_ds is None:
        print("  ERROR: file not readable")
        return False

    geotransform = raster_ds.GetGeoTransform()
    has_projection = bool(raster_ds.GetProjection())
    print(f"  Bands: {raster_ds.RasterCount}")
    print(f"  Raster: {raster_ds.RasterXSize} x {raster_ds.RasterYSize}")
    print(f"  Projection: {'OK' if has_projection else 'MISSING'}")
    print(f"  Pixel size: {geotransform[1]:.1f} m")

    all_ok = has_projection
    for band_index in range(1, raster_ds.RasterCount + 1):
        band = raster_ds.GetRasterBand(band_index)
        band_data = band.ReadAsArray().astype(np.float32)
        nodata = band.GetNoDataValue()
        if nodata is not None:
            band_data[band_data == nodata] = np.nan

        valid_count = int(np.sum(~np.isnan(band_data)))
        mean_value = float(np.nanmean(band_data)) if valid_count > 0 else 0.0
        status = "OK" if valid_count > MIN_VALID_PIXELS else "WARNING: too few valid pixels"
        if valid_count <= MIN_VALID_PIXELS:
            all_ok = False
        print(
            f"  Band {band_index} ({band.GetDescription()}): "
            f"{valid_count} valid pixels, mean={mean_value:.4f}  {status}"
        )

    raster_ds = None
    return all_ok


def main() -> None:
    print("=" * 60)
    print("Quality check - InSAR GeoTIFFs")
    print("=" * 60)

    all_ok = True
    for _ref, _sec, label in config.COH_PAIRS:
        tif_path = config.COH_DIR / f"{label}.tif"
        print(f"\n{label}:")
        if not tif_path.exists():
            print(f"  MISSING: {tif_path}")
            all_ok = False
            continue
        if not check_tif(tif_path):
            all_ok = False

    print("\n" + "=" * 60)
    print("All pairs OK." if all_ok else "WARNING: issues found - review before classification.")


if __name__ == "__main__":
    main()
