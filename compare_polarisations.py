"""Stage 3e: dual-polarisation (VV/VH) diagnostic.

The coherence change detection runs on two polarisations. VV is the primary
co-pol channel; VH is the cross-pol channel, dominated by volume scattering and
therefore lower in absolute coherence. This stage characterises what the second
channel contributes before it is fused into the damage classification:

  1. How correlated VV and VH coherence are. A low correlation means VH carries
     information independent of VV, so averaging the two relative losses reduces
     noise rather than just repeating the same signal.
  2. How differently each channel decorrelates in the rainy season, measured as
     the per-polarisation environmental retention R_env over unbuilt cells. The
     key result for this site is that VH is far more robust to the seasonal
     decorrelation that inflates the VV-based damage extent for E2b and E3.

The fusion itself (mean of the per-polarisation relative loss) lives in
classify_damage.py and correct_baseline_drift.py; this script only reports and
plots the relationship.

    python compare_polarisations.py

Output: a two-panel figure (config.POLARISATION_DIAGNOSTIC_FIGURE).
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np

import config
from check_baseline import pearson_correlation
from classify_damage import add_epoch_coherence, load_buildings
from correct_baseline_drift import environmental_retention, grid_with_counts

EPOCHS = ["E1", *config.DAMAGE_EPOCHS]


def paired_coherence(built_up_gdf, epoch: str) -> tuple[np.ndarray, np.ndarray]:
    """Finite VV/VH coherence pairs for one epoch over built-up cells."""
    vv = built_up_gdf[f"coh_{epoch}_{config.COH_POLARISATIONS[0]}"].to_numpy(float)
    vh = built_up_gdf[f"coh_{epoch}_{config.COH_POLARISATIONS[1]}"].to_numpy(float)
    finite = np.isfinite(vv) & np.isfinite(vh)
    return vv[finite], vh[finite]


def plot_scatter(ax, built_up_gdf) -> None:
    """VV against VH coherence, pooled over epochs, with a 1:1 reference."""
    vv_all, vh_all = [], []
    for epoch in EPOCHS:
        vv, vh = paired_coherence(built_up_gdf, epoch)
        vv_all.append(vv)
        vh_all.append(vh)
    vv_pooled = np.concatenate(vv_all)
    vh_pooled = np.concatenate(vh_all)

    ax.hexbin(vv_pooled, vh_pooled, gridsize=45, mincnt=1,
              cmap="magma", linewidths=0.0)
    ax.plot([0, 1], [0, 1], color=config.COLOR_SUB, linestyle="--", linewidth=1.0)

    pooled_r = pearson_correlation(vv_pooled, vh_pooled)
    ax.text(0.04, 0.93, f"pooled r = {pooled_r:.2f}", transform=ax.transAxes,
            color=config.COLOR_FG, fontsize=11, fontweight="bold")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel("VV coherence", color=config.COLOR_FG)
    ax.set_ylabel("VH coherence", color=config.COLOR_FG)
    ax.set_title("VV vs VH coherence (built-up cells)", color=config.COLOR_FG)


def plot_retention(ax, retention: dict) -> None:
    """Grouped bars of the per-polarisation R_env per epoch."""
    epochs = config.DAMAGE_EPOCHS
    positions = np.arange(len(epochs))
    width = 0.38
    primary, cross = config.COH_POLARISATIONS[0], config.COH_POLARISATIONS[1]

    vv_values = [retention[epoch][primary] for epoch in epochs]
    vh_values = [retention[epoch][cross] for epoch in epochs]

    ax.bar(positions - width / 2, vv_values, width, label=primary,
           color=config.COLOR_VV)
    ax.bar(positions + width / 2, vh_values, width, label=cross,
           color=config.COLOR_VH)
    ax.axhline(1.0, color=config.COLOR_SUB, linestyle="--", linewidth=1.0)
    ax.text(len(epochs) - 0.5, 1.005, "no seasonal drift", ha="right",
            va="bottom", color=config.COLOR_SUB, fontsize=9)

    ax.set_xticks(positions)
    ax.set_xticklabels(epochs, color=config.COLOR_FG)
    ax.set_ylim(0, 1.1)
    ax.set_ylabel("environmental retention $R_{env}$", color=config.COLOR_FG)
    ax.set_title("Rainy-season retention per channel", color=config.COLOR_FG)
    legend = ax.legend(facecolor=config.COLOR_PANEL, edgecolor=config.COLOR_LINE,
                       labelcolor=config.COLOR_FG)
    legend.get_frame().set_alpha(0.9)


def style_axes(ax) -> None:
    """Apply the shared dark theme to an axes."""
    ax.set_facecolor(config.COLOR_BG)
    ax.tick_params(colors=config.COLOR_FG)
    for spine in ax.spines.values():
        spine.set_visible(False)


def print_summary(built_up_gdf, retention: dict) -> None:
    """Print the per-epoch correlation and the per-polarisation retention."""
    print("\n" + "=" * 60)
    print("VV/VH coherence correlation (built-up cells)")
    print("=" * 60)
    for epoch in EPOCHS:
        vv, vh = paired_coherence(built_up_gdf, epoch)
        print(f"  {epoch}: mean VV {vv.mean():.3f}  mean VH {vh.mean():.3f}  "
              f"r {pearson_correlation(vv, vh):.3f}  n {len(vv):,}")

    primary, cross = config.COH_POLARISATIONS[0], config.COH_POLARISATIONS[1]
    print("\nPer-polarisation environmental retention R_env (unbuilt cells)")
    for epoch in config.DAMAGE_EPOCHS:
        print(f"  {epoch}: {primary} {retention[epoch][primary]:.3f}  "
              f"{cross} {retention[epoch][cross]:.3f}")


def main() -> None:
    config.configure_gdal_proj_env()
    config.ensure_processing_dirs()
    buildings_gdf = load_buildings()

    cell_size_m = config.GRID_CELL_SIZE_M
    min_pixels = config.grid_min_pixels(cell_size_m)
    grid_gdf = grid_with_counts(buildings_gdf, cell_size_m)
    add_epoch_coherence(grid_gdf)

    retention, _ = environmental_retention(grid_gdf, min_pixels)
    built_up_gdf = grid_gdf[grid_gdf["building_count"] > 0]
    print_summary(built_up_gdf, retention)

    fig, axes = plt.subplots(1, 2, figsize=(14, 6), facecolor=config.COLOR_BG)
    fig.subplots_adjust(left=0.07, right=0.97, top=0.84, bottom=0.12, wspace=0.22)
    for ax in axes:
        style_axes(ax)
    plot_scatter(axes[0], built_up_gdf)
    plot_retention(axes[1], retention)
    fig.text(0.5, 0.965, "Dual-polarisation diagnostic  -  El Geneina 2023",
             ha="center", va="center", color=config.COLOR_FG,
             fontsize=16, fontweight="bold")

    output_path = config.POLARISATION_DIAGNOSTIC_FIGURE
    fig.savefig(output_path, dpi=200, bbox_inches="tight", facecolor=config.COLOR_BG)
    print(f"\nSaved: {output_path}")


if __name__ == "__main__":
    main()
