"""Stage 1 of the InSAR pipeline: TOPSAR-Split + Apply-Orbit-File.

For every Sentinel-1 SLC scene this extracts the relevant subswath and the
VV+VH polarizations, applies precise orbit information and stores the result as
BEAM-DIMAP for fast subsequent reading.

It also provides two helpers used to set up the run:
  - find_subswath:   determine which subswath (IW1/IW2/IW3) covers the AOI
  - find_aoi_bursts: determine the burst index range that overlaps the AOI

Run as a script to process all scenes defined in config.ALL_DATES:

    python preprocess.py
"""

from __future__ import annotations

from pathlib import Path

import config
from snap import GPF, GeoPos, HashMap, Integer, PixelPos, ProductIO


def find_subswath(safe_zip: Path, target_lon: float, target_lat: float) -> str | None:
    """Return the subswath (IW1/IW2/IW3) that contains the target coordinate."""
    print(f"Reading: {safe_zip.name[:65]}")
    product = ProductIO.readProduct(str(safe_zip))

    covering_subswath = None
    for subswath in ("IW1", "IW2", "IW3"):
        split_params = HashMap()
        split_params.put("subswath", subswath)
        split_params.put("selectedPolarisations", "VV")
        split = GPF.createProduct("TOPSAR-Split", split_params, product)

        geocoding = split.getSceneGeoCoding()
        width = split.getSceneRasterWidth()
        height = split.getSceneRasterHeight()

        pixel = PixelPos()
        geocoding.getPixelPos(GeoPos(float(target_lat), float(target_lon)), pixel)
        split.dispose()

        if 0 <= pixel.x <= width and 0 <= pixel.y <= height:
            print(f"  {subswath}: target at pixel ({pixel.x:.0f}, {pixel.y:.0f})")
            covering_subswath = subswath
        else:
            print(f"  {subswath}: outside ({pixel.x:.0f}, {pixel.y:.0f})")

    product.dispose()
    return covering_subswath


def find_aoi_bursts(split_dim: Path) -> list[int]:
    """Return the 1-based burst indices in a split product that overlap the AOI."""
    bounds = config.load_aoi_bounds()
    product = ProductIO.readProduct(str(split_dim))

    geocoding = product.getSceneGeoCoding()
    width = product.getSceneRasterWidth()
    height = product.getSceneRasterHeight()
    lines_per_burst = height // config.NUM_BURSTS

    aoi_bursts: list[int] = []
    for burst in range(config.NUM_BURSTS):
        y_start = burst * lines_per_burst
        y_end = y_start + lines_per_burst - 1

        geo_top, geo_bottom = GeoPos(), GeoPos()
        geocoding.getGeoPos(PixelPos(float(width // 2), float(y_start)), geo_top)
        geocoding.getGeoPos(PixelPos(float(width // 2), float(y_end)), geo_bottom)

        burst_north = max(geo_top.lat, geo_bottom.lat)
        burst_south = min(geo_top.lat, geo_bottom.lat)
        overlaps = burst_north >= bounds["south"] and burst_south <= bounds["north"]

        marker = "  <-- AOI" if overlaps else ""
        print(f"  Burst {burst + 1}: {burst_south:.4f} - {burst_north:.4f} N{marker}")
        if overlaps:
            aoi_bursts.append(burst + 1)

    product.dispose()
    return aoi_bursts


def split_and_apply_orbit(date: str, safe_zip: Path, output_dir: Path) -> Path | None:
    """Run TOPSAR-Split + Apply-Orbit-File for one scene, saved as BEAM-DIMAP."""
    output_base = output_dir / f"split_orbit_{date}"
    output_dim = output_dir / f"split_orbit_{date}.dim"
    if output_dim.exists():
        print(f"  {date}: already present, skipped")
        return output_base

    print(f"  {date}: reading SAFE...")
    product = ProductIO.readProduct(str(safe_zip))

    print(f"  {date}: TOPSAR-Split ({config.SUBSWATH}, {config.POLARISATIONS})...")
    split_params = HashMap()
    split_params.put("subswath", config.SUBSWATH)
    split_params.put("selectedPolarisations", config.POLARISATIONS)
    split_product = GPF.createProduct("TOPSAR-Split", split_params, product)

    print(f"  {date}: Apply-Orbit-File...")
    orbit_params = HashMap()
    orbit_params.put("orbitType", "Sentinel Precise (Auto Download)")
    orbit_params.put("polyDegree", Integer(3))
    orbit_params.put("continueOnFail", True)
    orbit_product = GPF.createProduct("Apply-Orbit-File", orbit_params, split_product)

    print(f"  {date}: writing...")
    ProductIO.writeProduct(orbit_product, str(output_base), "BEAM-DIMAP")

    for disposable in (product, split_product, orbit_product):
        disposable.dispose()

    size_mb = sum(
        f.stat().st_size for f in output_dir.glob(f"split_orbit_{date}*") if f.is_file()
    ) / 1e6
    print(f"  {date}: done ({size_mb:.0f} MB)")
    return output_base


def main() -> None:
    config.ensure_processing_dirs()

    print("=" * 60)
    print("Stage 1 - TOPSAR-Split + Apply-Orbit-File")
    print(f"Subswath: {config.SUBSWATH}  |  Polarisations: {config.POLARISATIONS}")
    print(f"Scenes: {len(config.ALL_DATES)}  |  Output: {config.SPLIT_DIR}")
    print("Note: orbit download requires an internet connection")
    print("=" * 60)

    processed = 0
    for index, date in enumerate(config.ALL_DATES, start=1):
        print(f"\n[{index}/{len(config.ALL_DATES)}] {date}")
        if split_and_apply_orbit(date, config.safe_path(date), config.SPLIT_DIR):
            processed += 1

    print(f"\n{processed}/{len(config.ALL_DATES)} scenes processed -> {config.SPLIT_DIR}")


if __name__ == "__main__":
    main()
