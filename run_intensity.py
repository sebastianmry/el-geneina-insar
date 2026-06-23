"""Stage 2b: calibrated backscatter (sigma0) per scene.

The interferometric coherence (run_insar.py) measures decorrelation, which the
Sahel rains drive down over the whole scene regardless of the conflict. The
backscatter intensity is an independent, incoherent change channel: it reacts to
the physical structure of a surface (standing walls vs. rubble) rather than to
phase stability, so it is far less sensitive to the seasonal drift that inflates
the coherence damage signal for the June and July epochs.

For each scene this runs a short SNAP graph on the orbit-applied SLC split:
Calibration (sigma0, both polarisations) -> TOPSAR-Deburst -> Subset to AOI ->
Terrain-Correction -> GeoTIFF. The result is one geocoded raster per scene with
the polarisations as bands (config.COH_POLARISATIONS order: band 1 = VV,
band 2 = VH), on the same 10 m / EPSG:32634 grid as the coherence rasters.

Each scene writes its own GeoTIFF and an already-present output is skipped, so an
interrupted run resumes where it stopped (at most the scene in progress is lost).

    python run_intensity.py

The JVM heap and the JAI tile cache are raised before SNAP starts so the terrain
correction can use the available memory; tune INTENSITY_JVM_HEAP for the host.
"""

from __future__ import annotations

import os

# The JVM reads -Xmx once, at start-up, which happens on the first SNAP import.
# Raise the heap (and below the JAI tile cache) before importing snap so the
# terrain correction is not capped at the default heap on a 16 GB host.
INTENSITY_JVM_HEAP = os.environ.get("INTENSITY_JVM_HEAP", "12g")
os.environ.setdefault("_JAVA_OPTIONS", f"-Xmx{INTENSITY_JVM_HEAP}")

from datetime import datetime  # noqa: E402
from pathlib import Path  # noqa: E402

from tqdm import tqdm  # noqa: E402

import config  # noqa: E402
from snap import GPF, HashMap, JavaSystem, ProductIO, jpy  # noqa: E402


def configure_tile_cache(megabytes: int = 4096) -> None:
    """Enlarge the JAI tile cache so SNAP keeps more raster tiles in memory."""
    try:
        jai = jpy.get_type("javax.media.jai.JAI")
        jai.getDefaultInstance().getTileCache().setMemoryCapacity(
            jpy.get_type("java.lang.Long")(megabytes * 1024 * 1024).longValue()
        )
    except Exception as error:  # pragma: no cover - environment dependent
        print(f"  note: could not set JAI tile cache ({error})")


def process_scene(date: str, output_dir: Path) -> Path | None:
    """Calibrate one scene to sigma0 and write a terrain-corrected GeoTIFF.

    Calibration carries both polarisations through in a single pass, so one
    terrain correction (the expensive step) produces a multi-band intensity
    raster per scene. Returns the output path, or None if the split is missing.
    """
    output_tif = output_dir / config.intensity_tif_name(date)
    if output_tif.exists():
        print(f"  {date}: already present, skipped")
        return output_tif

    split_dim = config.SPLIT_DIR / f"split_orbit_{date}.dim"
    if not split_dim.exists():
        print(f"  ERROR: split product missing for {date}")
        return None

    print(f"  Reading split: {date}")
    source = ProductIO.readProduct(str(split_dim))

    # 1. Radiometric calibration to sigma0 (both polarisations, detected power).
    print("  Calibration (sigma0)...")
    cal_params = HashMap()
    cal_params.put("selectedPolarisations", config.POLARISATIONS)
    cal_params.put("outputSigmaBand", True)
    cal_params.put("outputImageInComplex", False)
    calibrated = GPF.createProduct("Calibration", cal_params, source)

    # 2. TOPSAR Deburst (merge the bursts into a continuous image).
    print("  TOPSAR-Deburst...")
    deburst_params = HashMap()
    deburst_params.put("selectedPolarisations", config.POLARISATIONS)
    deburst = GPF.createProduct("TOPSAR-Deburst", deburst_params, calibrated)

    # 3. Subset to the AOI.
    print("  Subset to AOI...")
    subset_params = HashMap()
    subset_params.put("geoRegion", config.aoi_wkt())
    subset_params.put("copyMetadata", True)
    subset = GPF.createProduct("Subset", subset_params, deburst)

    # 4. Terrain Correction (geocode to the coherence grid). Source bands are
    # listed in COH_POLARISATIONS order so the output band order is stable.
    print("  Terrain-Correction...")
    source_bands = ",".join(
        f"Sigma0_{config.SUBSWATH}_{pol}" for pol in config.COH_POLARISATIONS
    )
    tc_params = HashMap()
    tc_params.put("sourceBands", source_bands)
    tc_params.put("demName", config.DEM_NAME)
    tc_params.put("pixelSpacingInMeter", config.PIXEL_SPACING_M)
    tc_params.put("mapProjection", config.OUTPUT_CRS)
    tc_params.put("nodataValueAtSea", False)
    terrain_corrected = GPF.createProduct("Terrain-Correction", tc_params, subset)

    # 5. Write GeoTIFF.
    output_base = output_tif.with_suffix("")
    print(f"  Writing: {output_tif.name}")
    ProductIO.writeProduct(terrain_corrected, str(output_base), "GeoTIFF-BigTIFF")

    for disposable in (terrain_corrected, subset, deburst, calibrated, source):
        disposable.dispose()
    JavaSystem.gc()

    size_mb = output_tif.stat().st_size / 1e6 if output_tif.exists() else 0
    print(f"  Done: {size_mb:.0f} MB")
    return output_tif


def main() -> None:
    config.ensure_processing_dirs()
    configure_tile_cache()

    print("=" * 60)
    print("Stage 2b - backscatter intensity (Calibration -> TC -> GeoTIFF)")
    print(f"Scenes:        {len(config.ALL_DATES)}")
    print(f"Polarisations: {config.COH_POLARISATIONS}")
    print(f"JVM heap:      {INTENSITY_JVM_HEAP}")
    print(f"Input:  {config.SPLIT_DIR}")
    print(f"Output: {config.INTENSITY_DIR}")
    print("=" * 60)

    processed = 0
    for index, date in enumerate(
        tqdm(config.ALL_DATES, desc="Total", unit="scene"), start=1
    ):
        print(f"\n[{index}/{len(config.ALL_DATES)}] {date}")
        start = datetime.now()
        if process_scene(date, config.INTENSITY_DIR):
            processed += 1
        print(f"  Elapsed: {(datetime.now() - start).seconds // 60} min")

    print(f"\n{processed}/{len(config.ALL_DATES)} scenes processed "
          f"-> {config.INTENSITY_DIR}")


if __name__ == "__main__":
    main()
