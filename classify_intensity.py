"""Stage 3g: intensity log-ratio false-positive filter.

The drift-corrected coherence classification (correct_baseline_drift.py) still
rests on a single physical signal, decorrelation, and the rainy season lowers
coherence over the built environment more than the unbuilt reference used for the
correction can fully account for. The backscatter intensity is an independent,
incoherent channel: it responds to structural change (standing walls collapsing
to rubble) rather than to phase stability, and barely reacts to the seasonal
moisture that drives the coherence drift. It therefore confirms which of the
coherence-flagged cells carry a real structural change.

For each epoch the mean sigma0 per grid cell is taken over the epoch's scenes
(per polarisation), and the change against the pre-conflict reference E1 is the
log-ratio

    LR = 10 * log10(sigma0_epoch / sigma0_E1)

averaged over the polarisations. Collapse can raise or lower backscatter, so the
filter is unsigned and tests |LR|. The significance threshold is calibrated on
the unbuilt reference cells: |LR| must exceed INTENSITY_CHANGE_SIGMA robust
standard deviations (1.4826 * MAD) of the unbuilt log-ratio. Because the noise is
measured on bare ground, ordinary seasonal backscatter variation is absorbed
into the threshold.

The filter keeps a drift-corrected affected cell only when the intensity confirms
the change; unconfirmed affected cells are reset to "no damage". This is a
conservative false-positive filter, not a new damage score: it can only remove
coherence calls, never add them.

Caveat: El Geneina is built of mud brick, whose rubble is radiometrically close
to the surrounding bare soil, so some genuine collapses produce only a weak
backscatter change and are filtered out. The intensity-filtered extent is thus a
strict lower bound, complementing the drift-corrected lower bound.

    python classify_intensity.py           full run (zonal extraction + figure)
    python classify_intensity.py figure    re-render the figure from the cache only

Outputs:
  config.INTENSITY_FILTERED_FILE   built-up cells with intensity + filtered classes
  config.INTENSITY_GRID_CACHE      full grid cache for fast figure re-renders
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from exactextract import exact_extract

import config
from check_baseline import pearson_correlation
from classify_damage import load_buildings
from correct_baseline_drift import grid_with_counts


def zonal_intensity(
    grid_gdf: gpd.GeoDataFrame, tif_path: Path, band: int
) -> np.ndarray:
    """Area-weighted mean sigma0 of one band over each grid cell.

    Pixels at or below config.INTENSITY_VALID_MIN and the raster no-data value
    are masked before averaging. Mirrors classify_damage.zonal_coherence so the
    intensity and coherence statistics use the same aggregation.
    """
    with rasterio.open(tif_path) as intensity_src:
        intensity = intensity_src.read(band).astype("float32")
        if intensity_src.nodata is not None:
            intensity[intensity == intensity_src.nodata] = np.nan
        intensity[intensity < config.INTENSITY_VALID_MIN] = np.nan
        profile = intensity_src.profile.copy()

    profile.update(count=1, dtype="float32", nodata=float("nan"))
    with rasterio.MemoryFile() as memfile:
        with memfile.open(**profile) as masked_ds:
            masked_ds.write(intensity, 1)
        with memfile.open() as masked_ds:
            stats_df = exact_extract(masked_ds, grid_gdf, ["mean"], output="pandas")
    return stats_df["mean"].to_numpy(dtype=float)


def add_epoch_intensity(grid_gdf: gpd.GeoDataFrame) -> None:
    """Add per-epoch mean sigma0 columns per polarisation (int_<epoch>_<pol>).

    For each epoch the per-scene cell means are averaged. The polarisation band
    index follows config.COH_POLARISATIONS (band 1 = VV, band 2 = VH), the order
    run_intensity.py wrote.
    """
    print("Aggregating intensity over grid cells...")
    for epoch, dates in config.EPOCH_INTENSITY_DATES.items():
        print(f"  {epoch}...")
        for band, polarisation in enumerate(config.COH_POLARISATIONS, start=1):
            scene_means = []
            for date in dates:
                tif_path = config.INTENSITY_DIR / config.intensity_tif_name(date)
                start = time.time()
                scene_means.append(zonal_intensity(grid_gdf, tif_path, band))
                print(f"    {tif_path.name} [{polarisation}]: {time.time() - start:.0f}s")
            grid_gdf[f"int_{epoch}_{polarisation}"] = np.nanmean(scene_means, axis=0)


def add_log_ratio(grid_gdf: gpd.GeoDataFrame) -> None:
    """Add lr_<epoch>: the dual-pol mean intensity log-ratio against E1.

    Each polarisation is normalised against its own E1 baseline (VH sits below
    VV), then the per-polarisation log-ratios are averaged, matching the dual-pol
    fusion of the coherence channel.
    """
    for epoch in config.DAMAGE_EPOCHS:
        per_pol = []
        for polarisation in config.COH_POLARISATIONS:
            reference = grid_gdf[f"int_E1_{polarisation}"]
            compared = grid_gdf[f"int_{epoch}_{polarisation}"]
            ratio = compared / reference
            per_pol.append(10.0 * np.log10(ratio.where(ratio > 0)))
        grid_gdf[f"lr_{epoch}"] = pd.concat(per_pol, axis=1).mean(axis=1)


def change_thresholds(grid_gdf: gpd.GeoDataFrame) -> dict[str, float]:
    """Per-epoch |log-ratio| significance threshold from unbuilt cells.

    The threshold is INTENSITY_CHANGE_SIGMA robust standard deviations
    (1.4826 * MAD around the unbuilt median) of the log-ratio over unbuilt cells,
    so it reflects the natural, non-conflict backscatter variability of bare
    ground for that epoch.
    """
    unbuilt = grid_gdf[grid_gdf["building_count"] == 0]
    thresholds: dict[str, float] = {}
    for epoch in config.DAMAGE_EPOCHS:
        log_ratio = unbuilt[f"lr_{epoch}"].to_numpy()
        log_ratio = log_ratio[np.isfinite(log_ratio)]
        median = np.median(log_ratio)
        robust_std = 1.4826 * np.median(np.abs(log_ratio - median))
        thresholds[epoch] = config.INTENSITY_CHANGE_SIGMA * robust_std
    return thresholds


def add_intensity_filter(
    grid_gdf: gpd.GeoDataFrame, thresholds: dict[str, float]
) -> None:
    """Add intensity_change_<epoch> and the filtered damage class damagef_<epoch>.

    intensity_change_<epoch> is True where |lr_<epoch>| exceeds the epoch
    threshold. damagef_<epoch> takes the drift-corrected class damagec_<epoch> but
    resets an affected cell (class >= 1) to 0 when the intensity does not confirm
    the change. No-data and no-damage cells are passed through unchanged.
    """
    for epoch in config.DAMAGE_EPOCHS:
        confirmed = grid_gdf[f"lr_{epoch}"].abs() >= thresholds[epoch]
        grid_gdf[f"intensity_change_{epoch}"] = confirmed.fillna(False)

        corrected = grid_gdf[f"damagec_{epoch}"].to_numpy()
        filtered = corrected.copy()
        unconfirmed_affected = (corrected >= 1) & ~confirmed.fillna(False).to_numpy()
        filtered[unconfirmed_affected] = 0
        grid_gdf[f"damagef_{epoch}"] = filtered


def _share(series: pd.Series, threshold_class: int) -> float:
    """Percentage of classified cells at or above a damage class."""
    classified = series[series >= 0]
    if len(classified) == 0:
        return float("nan")
    return (classified >= threshold_class).sum() / len(classified) * 100.0


def report(grid_gdf: gpd.GeoDataFrame, thresholds: dict[str, float]) -> None:
    """Print the thresholds and the drift-corrected vs intensity-filtered extent."""
    built_up = grid_gdf[grid_gdf["building_count"] > 0]

    print("\n" + "=" * 64)
    print("Intensity log-ratio change thresholds (unbuilt-cell noise)")
    print("=" * 64)
    for epoch in config.DAMAGE_EPOCHS:
        confirmed = built_up[f"intensity_change_{epoch}"].sum()
        total = len(built_up)
        print(f"  {epoch}: |LR| >= {thresholds[epoch]:.2f} dB  "
              f"-> {confirmed:,}/{total:,} built-up cells show intensity change "
              f"({confirmed / total * 100:.0f} %)")

    print("\n" + "=" * 64)
    print("Affected of built-up cells: drift-corrected vs intensity-filtered")
    print("=" * 64)
    print("  epoch | drift-corrected | intensity-filtered | removed")
    for epoch in config.DAMAGE_EPOCHS:
        corrected = _share(built_up[f"damagec_{epoch}"], 1)
        filtered = _share(built_up[f"damagef_{epoch}"], 1)
        print(f"  {epoch:5s} | {corrected:14.1f} % | {filtered:17.1f} % | "
              f"{corrected - filtered:6.1f} pp")


def make_figure(grid_gdf: gpd.GeoDataFrame, thresholds: dict[str, float]) -> None:
    """Diagnostic figure: the intensity channel does not corroborate coherence.

    Three panels for the peak epoch E2b: (1) corrected coherence loss vs the
    absolute intensity log-ratio (a flat blob = no relation), (2) the log-ratio
    over built-up vs unbuilt cells (the two distributions overlap, so the channel
    barely separates damage from bare ground), (3) the per-epoch agreement counts
    (coherence-only, both, intensity-only).
    """
    import matplotlib.pyplot as plt

    built_up = grid_gdf[grid_gdf["building_count"] > 0]
    unbuilt = grid_gdf[grid_gdf["building_count"] == 0]
    epoch = "E2b"

    relative_loss = built_up[f"relc_{epoch}"].to_numpy(dtype=float) * 100
    log_ratio = built_up[f"lr_{epoch}"].abs().to_numpy(dtype=float)
    finite = np.isfinite(relative_loss) & np.isfinite(log_ratio)
    correlation = pearson_correlation(relative_loss[finite], log_ratio[finite])

    fig, axes = plt.subplots(1, 3, figsize=(17, 5.5), facecolor=config.COLOR_BG)
    ax_scatter, ax_hist, ax_bar = axes
    fig.subplots_adjust(left=0.05, right=0.98, top=0.79, bottom=0.13, wspace=0.26)
    fig.text(0.5, 0.965,
             "Intensity cross-check  -  SAR coherence loss vs backscatter log-ratio",
             ha="center", va="center", color=config.COLOR_FG,
             fontsize=16, fontweight="bold")
    fig.text(0.5, 0.90,
             f"50 m built-up cells, epoch {epoch}  |  correlation {correlation:.2f}  "
             "|  mud-brick rubble scatters like bare soil, so intensity does not "
             "confirm the coherence extent",
             ha="center", color=config.COLOR_SUB, fontsize=9)

    for ax in axes:
        ax.set_facecolor(config.COLOR_BG)
        ax.tick_params(colors=config.COLOR_SUB, labelsize=8)
        for spine in ax.spines.values():
            spine.set_visible(False)

    ax_scatter.scatter(relative_loss[finite], log_ratio[finite],
                       s=4, alpha=0.25, color=config.COLOR_VH, edgecolors="none")
    ax_scatter.axhline(thresholds[epoch], color="#d62728", linewidth=1.0,
                       linestyle="--", alpha=0.8,
                       label=f"change threshold {thresholds[epoch]:.1f} dB")
    ax_scatter.set_xlabel("Drift-corrected coherence loss (%)",
                          color=config.COLOR_FG, fontsize=9)
    ax_scatter.set_ylabel("|Intensity log-ratio| (dB)",
                          color=config.COLOR_FG, fontsize=9)
    ax_scatter.set_title("No relationship between the two signals",
                         color=config.COLOR_FG, fontsize=10)
    ax_scatter.legend(fontsize=8, frameon=True, facecolor=config.COLOR_PANEL,
                      edgecolor=config.COLOR_LINE, labelcolor=config.COLOR_FG)

    built_lr = built_up[f"lr_{epoch}"].to_numpy(dtype=float)
    unbuilt_lr = unbuilt[f"lr_{epoch}"].to_numpy(dtype=float)
    bins = np.linspace(-12, 12, 60)
    ax_hist.hist(unbuilt_lr[np.isfinite(unbuilt_lr)], bins=bins, density=True,
                 color=config.COLOR_SUB, alpha=0.55, label="unbuilt (reference)")
    ax_hist.hist(built_lr[np.isfinite(built_lr)], bins=bins, density=True,
                 color=config.COLOR_VH, alpha=0.65, label="built-up")
    ax_hist.set_xlabel("Intensity log-ratio (dB)", color=config.COLOR_FG, fontsize=9)
    ax_hist.set_ylabel("Density", color=config.COLOR_FG, fontsize=9)
    ax_hist.set_title("Built-up barely separates from bare ground",
                      color=config.COLOR_FG, fontsize=10)
    ax_hist.legend(fontsize=8, frameon=True, facecolor=config.COLOR_PANEL,
                   edgecolor=config.COLOR_LINE, labelcolor=config.COLOR_FG)

    epochs = config.DAMAGE_EPOCHS
    coh_only, both, int_only = [], [], []
    for ep in epochs:
        affected = built_up[f"damagec_{ep}"] >= 1
        change = built_up[f"intensity_change_{ep}"]
        both_count = int((affected & change).sum())
        coh_only.append(int((affected & ~change).sum()))
        int_only.append(int((~affected & change).sum()))
        both.append(both_count)
    positions = np.arange(len(epochs))
    width = 0.6
    ax_bar.bar(positions, coh_only, width, color=config.COLOR_VV, label="coherence only")
    ax_bar.bar(positions, both, width, bottom=coh_only, color="#d62728",
               label="both (confirmed)")
    ax_bar.bar(positions, int_only, width,
               bottom=np.array(coh_only) + np.array(both),
               color=config.COLOR_VH, label="intensity only")
    ax_bar.set_xticks(positions)
    ax_bar.set_xticklabels(epochs, color=config.COLOR_FG)
    ax_bar.set_ylabel("Built-up cells flagged", color=config.COLOR_FG, fontsize=9)
    ax_bar.set_title("The two channels rarely agree", color=config.COLOR_FG, fontsize=10)
    ax_bar.legend(fontsize=8, frameon=True, facecolor=config.COLOR_PANEL,
                  edgecolor=config.COLOR_LINE, labelcolor=config.COLOR_FG)

    config.ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(config.INTENSITY_FIGURE, dpi=200,
                facecolor=config.COLOR_BG, bbox_inches="tight")
    plt.close(fig)
    print(f"Figure: {config.INTENSITY_FIGURE}")


def main() -> None:
    config.configure_gdal_proj_env()
    config.ensure_processing_dirs()

    drift_path = config.grid_drift_file(config.GRID_CELL_SIZE_M)
    if not drift_path.exists():
        raise SystemExit(
            f"Drift-corrected grid missing: {drift_path}\n"
            "Run correct_baseline_drift.py first."
        )

    buildings_gdf = load_buildings()
    cell_size_m = config.GRID_CELL_SIZE_M
    grid_gdf = grid_with_counts(buildings_gdf, cell_size_m)
    print(f"  cells: {len(grid_gdf):,} "
          f"(built-up {int((grid_gdf['building_count'] > 0).sum()):,}, "
          f"unbuilt {int((grid_gdf['building_count'] == 0).sum()):,})")

    add_epoch_intensity(grid_gdf)
    add_log_ratio(grid_gdf)

    # Bring in the drift-corrected coherence classes for the built-up cells.
    drift_gdf = gpd.read_file(drift_path)
    damagec_columns = [f"damagec_{epoch}" for epoch in config.DAMAGE_EPOCHS]
    relc_columns = [f"relc_{epoch}" for epoch in config.DAMAGE_EPOCHS]
    grid_gdf = grid_gdf.merge(
        drift_gdf[["cell_id", *damagec_columns, *relc_columns]],
        on="cell_id", how="left",
    )
    for column in damagec_columns:
        grid_gdf[column] = grid_gdf[column].fillna(config.DAMAGE_NODATA).astype(int)

    thresholds = change_thresholds(grid_gdf)
    add_intensity_filter(grid_gdf, thresholds)
    report(grid_gdf, thresholds)
    make_figure(grid_gdf, thresholds)

    # Cache the full grid so the figure can be re-rendered without recomputing
    # the slow zonal extraction (python classify_intensity.py figure).
    grid_gdf.to_pickle(config.INTENSITY_GRID_CACHE)
    print(f"Cached full grid: {config.INTENSITY_GRID_CACHE}")

    built_up = grid_gdf[grid_gdf["building_count"] > 0].copy()
    built_up.to_file(config.INTENSITY_FILTERED_FILE, driver="GPKG")
    print(f"\nSaved: {config.INTENSITY_FILTERED_FILE}")


def render_from_cache() -> None:
    """Re-render the figure from the cached full grid (seconds, no extraction)."""
    if not config.INTENSITY_GRID_CACHE.exists():
        raise SystemExit(
            f"No cache at {config.INTENSITY_GRID_CACHE}\n"
            "Run a full pass first: python classify_intensity.py"
        )
    grid_gdf = pd.read_pickle(config.INTENSITY_GRID_CACHE)
    thresholds = change_thresholds(grid_gdf)
    make_figure(grid_gdf, thresholds)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "figure":
        render_from_cache()
    else:
        main()
