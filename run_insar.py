"""Stage 2 of the InSAR pipeline: interferometric coherence per pair.

For each coherence pair it runs the full SNAP graph in a single pass:
Back-Geocoding -> Interferogram + Coherence -> TOPSAR-Deburst ->
Goldstein Phase Filtering -> Subset to AOI -> Terrain-Correction -> GeoTIFF.

Output: one GeoTIFF per pair (coherence + interferogram phase) in COH_DIR.

Run as a script to process all pairs defined in config.COH_PAIRS:

    python run_insar.py
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from tqdm import tqdm

import config
from snap import GPF, HashMap, Integer, JavaSystem, ProductArray, ProductIO, jpy


def process_pair(ref_date: str, sec_date: str, label: str, output_dir: Path) -> Path | None:
    """Run the complete InSAR graph for one coherence pair and write a GeoTIFF."""
    output_tif = output_dir / f"{label}.tif"
    if output_tif.exists():
        print(f"  {label}: already present, skipped")
        return output_tif

    ref_dim = config.SPLIT_DIR / f"split_orbit_{ref_date}.dim"
    sec_dim = config.SPLIT_DIR / f"split_orbit_{sec_date}.dim"
    if not ref_dim.exists() or not sec_dim.exists():
        print(f"  ERROR: split products missing for {ref_date} or {sec_date}")
        return None

    print(f"  Reading reference: {ref_date}")
    reference = ProductIO.readProduct(str(ref_dim))
    print(f"  Reading secondary: {sec_date}")
    secondary = ProductIO.readProduct(str(sec_dim))

    # 1. Back-Geocoding (coregistration onto the reference geometry).
    # ESD is intentionally omitted: it is not required for coherence change
    # detection and a SNAP date-format bug ("31Mar2023") breaks it here.
    print("  Back-Geocoding...")
    bg_params = HashMap()
    bg_params.put("demName", config.DEM_NAME)
    bg_params.put("demResamplingMethod", "BICUBIC_INTERPOLATION")
    bg_params.put("imgResamplingMethod", "BICUBIC_INTERPOLATION")
    bg_params.put("disableReramp", False)
    back_geocoded = GPF.createProduct(
        "Back-Geocoding",
        bg_params,
        jpy.array(ProductArray, [reference, secondary]),
    )

    # 2. Interferogram + coherence estimation.
    print("  Interferogram + coherence...")
    ifg_params = HashMap()
    ifg_params.put("subtractFlatEarthPhase", True)
    ifg_params.put("srpPolynomialDegree", Integer(5))
    ifg_params.put("srpNumberPoints", Integer(501))
    ifg_params.put("orbitDegree", Integer(3))
    ifg_params.put("cohWinAz", Integer(config.COH_WIN_AZIMUTH))
    ifg_params.put("cohWinRg", Integer(config.COH_WIN_RANGE))
    ifg_params.put("subtractTopographicPhase", True)
    ifg_params.put("demName", config.DEM_NAME)
    interferogram = GPF.createProduct("Interferogram", ifg_params, back_geocoded)

    # 3. TOPSAR Deburst.
    print("  TOPSAR-Deburst...")
    deburst_params = HashMap()
    deburst_params.put("selectedPolarisations", "VV")
    deburst = GPF.createProduct("TOPSAR-Deburst", deburst_params, interferogram)

    # 4. Goldstein phase filtering.
    print("  Goldstein phase filtering...")
    goldstein_params = HashMap()
    goldstein_params.put("alpha", 0.5)
    goldstein_params.put("numBlockRows", 32)
    goldstein_params.put("numBlockCols", 32)
    filtered = GPF.createProduct("GoldsteinPhaseFiltering", goldstein_params, deburst)

    # 5. Subset to the AOI.
    print("  Subset to AOI...")
    subset_params = HashMap()
    subset_params.put("geoRegion", config.aoi_wkt())
    subset_params.put("copyMetadata", True)
    subset = GPF.createProduct("Subset", subset_params, filtered)

    # 6. Terrain Correction (geocoding).
    print("  Terrain-Correction...")
    tc_params = HashMap()
    tc_params.put("demName", config.DEM_NAME)
    tc_params.put("pixelSpacingInMeter", config.PIXEL_SPACING_M)
    tc_params.put("mapProjection", config.OUTPUT_CRS)
    tc_params.put("nodataValueAtSea", False)
    terrain_corrected = GPF.createProduct("Terrain-Correction", tc_params, subset)

    # 7. Write GeoTIFF.
    print(f"  Writing: {label}.tif")
    ProductIO.writeProduct(terrain_corrected, str(output_dir / label), "GeoTIFF-BigTIFF")

    for disposable in (
        terrain_corrected, subset, filtered, deburst,
        interferogram, back_geocoded, secondary, reference,
    ):
        disposable.dispose()
    JavaSystem.gc()

    size_mb = output_tif.stat().st_size / 1e6 if output_tif.exists() else 0
    print(f"  Done: {size_mb:.0f} MB")
    return output_tif


def main() -> None:
    config.ensure_processing_dirs()

    print("=" * 60)
    print("Stage 2 - InSAR pipeline (Back-Geocoding -> TC -> GeoTIFF)")
    print(f"Pairs:  {len(config.COH_PAIRS)}")
    print(f"Input:  {config.SPLIT_DIR}")
    print(f"Output: {config.COH_DIR}")
    print("Note: roughly 20-40 min per pair - best run overnight")
    print("=" * 60)

    processed = 0
    for index, (ref_date, sec_date, label) in enumerate(
        tqdm(config.COH_PAIRS, desc="Total", unit="pair"), start=1
    ):
        print(f"\n[{index}/{len(config.COH_PAIRS)}] {label}")
        start = datetime.now()
        if process_pair(ref_date, sec_date, label, config.COH_DIR):
            processed += 1
        print(f"  Elapsed: {(datetime.now() - start).seconds // 60} min")

    print(f"\n{processed}/{len(config.COH_PAIRS)} pairs processed -> {config.COH_DIR}")


if __name__ == "__main__":
    main()
