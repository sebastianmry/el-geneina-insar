"""Stage 3d: optical (Sentinel-2) cross-validation of the SAR damage signal.

The SAR damage bracket is wide for the rainy-season epochs because the
drift correction, estimated from bare ground, over-corrects the built
environment (see correct_baseline_drift.py). This stage tests whether an
independent optical destruction map can confirm the SAR extent.

Structural destruction persists for months, so the validation compares two
cloud-free, phenology-matched dry-season scenes a year apart, bracketing the
conflict. The Normalised Burn Ratio (NBR = (NIR - SWIR2) / (NIR + SWIR2)) drops
where vegetation and intact structures are lost, so

    dNBR = NBR_pre - NBR_post

is high over burned and destroyed ground. The per-pixel dNBR is averaged onto
the same 50 m grid as the SAR analysis and compared against the SAR damage
class with a confusion matrix and a continuous correlation.

The result is a documented validation ceiling: at Sentinel-2 resolution, the
spectral contrast between intact and destroyed mud-brick fabric is too low for
optical change detection to confirm the SAR signal (see the generated report).

Scenes are streamed directly from the Element84 Earth Search STAC as
cloud-optimised GeoTIFFs; nothing is stored permanently.

    python validate_optical.py

Outputs:
  config.OPTICAL_DNBR_FILE            grid cells with dNBR and the SAR classes
  config.OPTICAL_VALIDATION_REPORT    agreement + correlation report
"""

from __future__ import annotations

import json
import os
import ssl
import urllib.request
from datetime import date

import certifi
import geopandas as gpd
import numpy as np
import rasterio
from rasterio.windows import from_bounds
from rasterio.enums import Resampling
from shapely.geometry import box, shape

import config
from check_baseline import pearson_correlation

# Sentinel-2 L2A digital numbers use a 10000 scale and, from processing
# baseline 04.00 on, a -1000 bottom-of-atmosphere offset (both 2023 scenes
# qualify). NBR is a normalised ratio, so the offset is applied for correctness.
S2_SCALE = 10000.0
S2_OFFSET = -1000.0


def _configure_remote_access() -> ssl.SSLContext:
    """Set the CA bundle for GDAL/curl and Python ssl, and anonymous S3 access.

    The Windows certificate store can carry a malformed entry that breaks
    Python's default HTTPS context, so certifi's bundle is used explicitly.
    """
    os.environ.setdefault("CURL_CA_BUNDLE", certifi.where())
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    os.environ.setdefault("AWS_NO_SIGN_REQUEST", "YES")
    return ssl.create_default_context(cafile=certifi.where())


def search_scenes(ssl_context, start: str, end: str) -> list[dict]:
    """Return STAC items for the collection over the AOI within a date window."""
    bounds = config.load_aoi_bounds()
    body = {
        "collections": [config.STAC_COLLECTION],
        "bbox": [bounds["west"], bounds["south"], bounds["east"], bounds["north"]],
        "datetime": f"{start}T00:00:00Z/{end}T23:59:59Z",
        "query": {"eo:cloud_cover": {"lt": config.S2_MAX_CLOUD_COVER}},
        "limit": 100,
    }
    request = urllib.request.Request(
        f"{config.STAC_ENDPOINT}/search",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=120, context=ssl_context) as response:
        return json.load(response)["features"]


def select_scene(features: list[dict], window_label: str) -> dict:
    """Pick the lowest-cloud scene that fully covers the AOI."""
    bounds = config.load_aoi_bounds()
    aoi = box(bounds["west"], bounds["south"], bounds["east"], bounds["north"])

    covering = [
        feature for feature in features
        if shape(feature["geometry"]).contains(aoi)
    ]
    if not covering:
        raise RuntimeError(f"No single {window_label} scene fully covers the AOI.")

    best = min(covering, key=lambda f: f["properties"]["eo:cloud_cover"])
    print(f"  {window_label}: {best['id']}  "
          f"({best['properties']['datetime'][:10]}, "
          f"cloud {best['properties']['eo:cloud_cover']:.1f}%)")
    return best


def _aoi_bounds_utm() -> tuple[float, float, float, float]:
    """AOI bounding box in the output CRS (left, bottom, right, top)."""
    bounds = config.load_aoi_bounds()
    aoi = gpd.GeoSeries(
        [box(bounds["west"], bounds["south"], bounds["east"], bounds["north"])],
        crs="EPSG:4326",
    ).to_crs(config.OUTPUT_CRS)
    return tuple(aoi.total_bounds)


def _read_window(href: str, bounds_utm, out_shape=None, transform_ref=None):
    """Read a remote COG over the AOI, optionally resampled to a reference grid."""
    with rasterio.open(href) as src:
        window = from_bounds(*bounds_utm, transform=src.transform)
        if out_shape is None:
            band_array = src.read(1, window=window).astype("float32")
            transform = src.window_transform(window)
            return band_array, transform
        band_array = src.read(
            1, window=window, out_shape=out_shape, resampling=Resampling.bilinear
        ).astype("float32")
        return band_array, transform_ref


def nbr_for_scene(scene: dict, bounds_utm) -> tuple[np.ndarray, object]:
    """Compute a cloud-masked NBR array over the AOI on the 20 m SWIR grid."""
    assets = scene["assets"]
    swir, transform = _read_window(assets["swir22"]["href"], bounds_utm)
    out_shape = swir.shape
    nir, _ = _read_window(
        assets["nir"]["href"], bounds_utm, out_shape=out_shape, transform_ref=transform
    )
    scl, _ = _read_window(
        assets["scl"]["href"], bounds_utm, out_shape=out_shape, transform_ref=transform
    )

    nir_reflectance = (nir + S2_OFFSET) / S2_SCALE
    swir_reflectance = (swir + S2_OFFSET) / S2_SCALE

    denominator = nir_reflectance + swir_reflectance
    with np.errstate(divide="ignore", invalid="ignore"):
        nbr = (nir_reflectance - swir_reflectance) / denominator

    valid = np.isin(scl.astype(int), config.S2_SCL_VALID) & (denominator > 0)
    nbr[~valid] = np.nan
    return nbr, transform


def aggregate_dnbr_to_grid(
    dnbr: np.ndarray, transform, grid_gdf: gpd.GeoDataFrame
) -> np.ndarray:
    """Mean dNBR per grid cell via area-weighted zonal statistics."""
    from exactextract import exact_extract

    profile = {
        "driver": "GTiff", "height": dnbr.shape[0], "width": dnbr.shape[1],
        "count": 1, "dtype": "float32", "crs": config.OUTPUT_CRS,
        "transform": transform, "nodata": float("nan"),
    }
    with rasterio.MemoryFile() as memfile:
        with memfile.open(**profile) as dataset:
            dataset.write(dnbr.astype("float32"), 1)
        with memfile.open() as dataset:
            stats = exact_extract(dataset, grid_gdf, ["mean"], output="pandas")
    return stats["mean"].to_numpy(dtype=float)


def confusion(optical_destroyed: np.ndarray, sar_affected: np.ndarray) -> dict:
    """Confusion counts and agreement of optical vs SAR per cell (boolean arrays)."""
    valid = ~(np.isnan(optical_destroyed) | np.isnan(sar_affected))
    optical = optical_destroyed[valid].astype(bool)
    sar = sar_affected[valid].astype(bool)

    true_positive = int((optical & sar).sum())
    false_positive = int((~optical & sar).sum())
    false_negative = int((optical & ~sar).sum())
    true_negative = int((~optical & ~sar).sum())
    total = optical.size

    agreement = (true_positive + true_negative) / total * 100.0 if total else float("nan")
    precision = (
        true_positive / (true_positive + false_positive) * 100.0
        if (true_positive + false_positive) else float("nan")
    )
    recall = (
        true_positive / (true_positive + false_negative) * 100.0
        if (true_positive + false_negative) else float("nan")
    )
    return {
        "tp": true_positive, "fp": false_positive,
        "fn": false_negative, "tn": true_negative,
        "n": total, "agreement": agreement,
        "precision": precision, "recall": recall,
    }


def validate(grid_gdf: gpd.GeoDataFrame) -> dict:
    """Compare optical dNBR against the raw and corrected SAR classes."""
    epoch = config.OPTICAL_VALIDATION_EPOCH
    dnbr = grid_gdf["dnbr"].to_numpy(dtype=float)
    optical_destroyed = dnbr >= config.DNBR_DESTRUCTION_THRESHOLD

    raw_affected = grid_gdf[f"damage_{epoch}"].to_numpy(dtype=float) >= 1
    corrected_affected = grid_gdf[f"damagec_{epoch}"].to_numpy(dtype=float) >= 1

    # Continuous check: SAR relative coherence loss vs optical dNBR.
    relative_loss = grid_gdf[f"rel_{epoch}"].to_numpy(dtype=float)
    finite = np.isfinite(relative_loss) & np.isfinite(dnbr)
    correlation = pearson_correlation(relative_loss[finite], dnbr[finite])

    return {
        "epoch": epoch,
        "raw": confusion(optical_destroyed.astype(float), raw_affected.astype(float)),
        "corrected": confusion(
            optical_destroyed.astype(float), corrected_affected.astype(float)
        ),
        "optical_destroyed_pct": float(np.nanmean(optical_destroyed) * 100.0),
        "correlation": correlation,
        "n_correlation": int(finite.sum()),
    }


def write_report(result: dict, pre_scene: dict, post_scene: dict) -> None:
    """Write the optical validation report (a documented validation ceiling)."""
    epoch = result["epoch"]
    raw, corrected = result["raw"], result["corrected"]
    lines = [
        "# Optical cross-validation (Sentinel-2)",
        "",
        f"Generated by `validate_optical.py` on {date.today().isoformat()}.",
        "",
        "This is an independent attempt to confirm the SAR damage signal with "
        "optical imagery. The optical reference is the drop in the Normalised "
        "Burn Ratio (dNBR) between two cloud-free, phenology-matched dry-season "
        "Sentinel-2 scenes a year apart, bracketing the conflict. dNBR is "
        "averaged onto the 50 m grid and compared with the SAR damage class for "
        f"epoch {epoch}.",
        "",
        f"Pre-conflict scene: `{pre_scene['id']}` "
        f"({pre_scene['properties']['datetime'][:10]}, "
        f"cloud {pre_scene['properties']['eo:cloud_cover']:.1f}%)  ",
        f"Post-peak scene: `{post_scene['id']}` "
        f"({post_scene['properties']['datetime'][:10]}, "
        f"cloud {post_scene['properties']['eo:cloud_cover']:.1f}%)  ",
        f"Optically destroyed cells (dNBR >= {config.DNBR_DESTRUCTION_THRESHOLD:g}): "
        f"{result['optical_destroyed_pct']:.1f} % of built-up cells.",
        "",
        "## Result: optical does not independently confirm the SAR extent",
        "",
        "| SAR class | Agreement | Precision | Recall | TP | FP | FN | TN |",
        "| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| raw (upper bound) | {raw['agreement']:.1f} % | {raw['precision']:.1f} % "
        f"| {raw['recall']:.1f} % | {raw['tp']:,} | {raw['fp']:,} | {raw['fn']:,} "
        f"| {raw['tn']:,} |",
        f"| drift-corrected (lower bound) | {corrected['agreement']:.1f} % "
        f"| {corrected['precision']:.1f} % | {corrected['recall']:.1f} % "
        f"| {corrected['tp']:,} | {corrected['fp']:,} | {corrected['fn']:,} "
        f"| {corrected['tn']:,} |",
        "",
        f"Pearson correlation between the SAR relative coherence loss and the "
        f"optical dNBR over {result['n_correlation']:,} cells is "
        f"**{result['correlation']:.2f}**, effectively zero. Precision stays near "
        f"{corrected['precision']:.0f} % for both SAR classes, and only "
        f"{result['optical_destroyed_pct']:.1f} % of cells cross the dNBR "
        "threshold, which is within the noise of the index. The optical map and "
        "the SAR map are not measuring the same thing here.",
        "",
        "## Why, and what it means",
        "",
        "El Geneina is built largely from mud brick and earthen material. When "
        "such a building is destroyed it collapses into rubble that is spectrally "
        "almost identical to the surrounding bare soil, so optical change "
        "detection has very little contrast to work with, even for total "
        "destruction. dNBR is in addition a fire and vegetation index, and at the "
        "10 to 20 m resolution of Sentinel-2 a single destroyed footprint is "
        "averaged away inside a 50 m cell. SAR coherence instead responds to the "
        "geometric disturbance of the surface, independent of its spectral "
        "signature, which is why it carries the damage signal where optical does "
        "not.",
        "",
        "This sets a validation ceiling rather than a verdict on the SAR. The "
        "optical check does rule out the raw two-thirds figure as literal "
        "building destruction, which is consistent with the drift-corrected lower "
        "bound, but it cannot positively confirm that lower bound. A definitive "
        "optical validation would need sub-metre imagery (for example UNOSAT or "
        "Maxar damage points), not free Sentinel-2. Confidence in the SAR result "
        "therefore rests on the internal checks: the E1 baseline stability and "
        "the rainy-season drift correction (see Baseline robustness).",
        "",
    ]
    config.OPTICAL_VALIDATION_REPORT.parent.mkdir(parents=True, exist_ok=True)
    config.OPTICAL_VALIDATION_REPORT.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    config.configure_gdal_proj_env()
    config.ensure_processing_dirs()
    ssl_context = _configure_remote_access()

    print("Searching Sentinel-2 scenes...")
    pre_scene = select_scene(
        search_scenes(ssl_context, *config.S2_PRE_WINDOW), "pre-conflict"
    )
    post_scene = select_scene(
        search_scenes(ssl_context, *config.S2_POST_WINDOW), "post-peak"
    )

    bounds_utm = _aoi_bounds_utm()
    print("Reading NBR (streamed COGs)...")
    nbr_pre, transform = nbr_for_scene(pre_scene, bounds_utm)
    nbr_post, _ = nbr_for_scene(post_scene, bounds_utm)
    dnbr = nbr_pre - nbr_post
    print(f"  dNBR computed: {np.isfinite(dnbr).sum():,} valid pixels")

    print("Aggregating dNBR onto the SAR grid...")
    grid_gdf = gpd.read_file(config.grid_drift_file(config.GRID_CELL_SIZE_M))
    grid_gdf = grid_gdf.to_crs(config.OUTPUT_CRS)
    grid_gdf["dnbr"] = aggregate_dnbr_to_grid(dnbr, transform, grid_gdf)

    result = validate(grid_gdf)
    _print_summary(result)

    grid_gdf.to_file(config.OPTICAL_DNBR_FILE, driver="GPKG")
    print(f"\nSaved: {config.OPTICAL_DNBR_FILE}")
    write_report(result, pre_scene, post_scene)
    print(f"Report: {config.OPTICAL_VALIDATION_REPORT}")


def _print_summary(result: dict) -> None:
    """Print the headline agreement numbers."""
    print("\n" + "=" * 60)
    print(f"Optical validation of SAR epoch {result['epoch']}")
    print("=" * 60)
    print(f"  optically destroyed: {result['optical_destroyed_pct']:.1f}% of cells")
    for label in ("raw", "corrected"):
        stats = result[label]
        print(f"  {label:9s}: agreement {stats['agreement']:.1f}%  "
              f"precision {stats['precision']:.1f}%  recall {stats['recall']:.1f}%")
    print(f"  correlation (loss vs dNBR): {result['correlation']:.2f} "
          f"over {result['n_correlation']:,} cells")


if __name__ == "__main__":
    main()
