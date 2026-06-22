"""Stage 3f: damage confidence / uncertainty layer.

The damage classification uses fixed relative-loss thresholds. This stage adds
the missing dimension: how trustworthy each cell's call is. For every built-up
cell `correct_baseline_drift.py` stores a signal-to-noise z-score (z_<epoch>),
the drift-corrected coherence drop divided by its standard error from the
within-cell spatial spread of coherence. A high z means the drop is large
relative to the local variability, so the damage call is confident; a low z means
the cell sits in the noise. Because pixels in a cell are spatially correlated,
the z reads as a relative confidence, not a strict p-value.

This script maps the confidence of the affected cells per epoch and reports what
share of the affected extent is statistically confident.

    python uncertainty.py

Output: a three-panel confidence map (config.UNCERTAINTY_FIGURE).
"""

from __future__ import annotations

import matplotlib.pyplot as plt
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize

import config
import viz_common

EPOCH_TITLES = {
    "E2a": "E2a  Apr - May 2023",
    "E2b": "E2b  Jun 2023  (Peak)",
    "E3": "E3  Jul 2023",
}
Z_MAX = 4.0  # colour-scale ceiling for the z-score


def print_confidence(grid_gdf) -> None:
    """Report the confident share of the affected cells per epoch."""
    print("\n" + "=" * 60)
    print("Confidence of corrected-affected cells (signal-to-noise z)")
    print("=" * 60)
    print("  epoch | affected | confident (z>=1.6) | high (z>=2.3)")
    for epoch in config.DAMAGE_EPOCHS:
        affected = grid_gdf[grid_gdf[f"damagec_{epoch}"] >= 1]
        total = len(affected)
        if total == 0:
            continue
        confident = (affected[f"z_{epoch}"] >= config.Z_CONFIDENT).sum()
        high = (affected[f"z_{epoch}"] >= config.Z_HIGH_CONFIDENCE).sum()
        print(f"  {epoch:5s} | {total:8,} | {confident / total * 100:16.0f} % | "
              f"{high / total * 100:11.0f} %")


def plot_panel(ax, grid_gdf, reference, epoch: str, norm) -> None:
    """Draw one epoch: affected cells coloured by confidence on the backdrop."""
    ax.set_facecolor(config.COLOR_BG)
    viz_common.draw_coherence_backdrop(ax, reference)

    affected = grid_gdf[grid_gdf[f"damagec_{epoch}"] >= 1]
    if len(affected):
        affected.plot(ax=ax, column=f"z_{epoch}", cmap=config.COLORMAP_CONFIDENCE,
                      norm=norm, linewidth=0.0, zorder=2)

    ax.set_xlim(config.PLOT_XLIM)
    ax.set_ylim(config.PLOT_YLIM)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(EPOCH_TITLES[epoch], color=config.COLOR_FG, fontsize=12)
    viz_common.add_scale_bar(ax)
    viz_common.add_north_arrow(ax)


def main() -> None:
    config.configure_gdal_proj_env()
    grid_gdf = viz_common.load_damage_grid_corrected()
    if f"z_{config.DAMAGE_EPOCHS[0]}" not in grid_gdf.columns:
        raise SystemExit("No z_<epoch> columns: run correct_baseline_drift.py first.")
    reference = viz_common.load_reference_raster()
    print_confidence(grid_gdf)

    norm = Normalize(vmin=0.0, vmax=Z_MAX)
    fig, axes = plt.subplots(1, 3, figsize=(21, 9), facecolor=config.COLOR_BG)
    fig.subplots_adjust(left=0.01, right=0.99, top=0.93, bottom=0.12, wspace=0.03)
    fig.text(0.5, 0.965, "Damage confidence (signal-to-noise)  -  El Geneina 2023",
             ha="center", va="center", color=config.COLOR_FG,
             fontsize=16, fontweight="bold")
    for ax, epoch in zip(axes, config.DAMAGE_EPOCHS):
        plot_panel(ax, grid_gdf, reference, epoch, norm)

    mappable = ScalarMappable(norm=norm, cmap=config.COLORMAP_CONFIDENCE)
    cbar = fig.colorbar(mappable, ax=axes, orientation="horizontal",
                        fraction=0.04, pad=0.04, aspect=50)
    cbar.set_label("confidence z  (corrected loss / standard error)",
                   color=config.COLOR_FG)
    cbar.ax.tick_params(colors=config.COLOR_FG)
    for threshold in (config.Z_CONFIDENT, config.Z_HIGH_CONFIDENCE):
        cbar.ax.axvline(threshold, color=config.COLOR_FG, linewidth=1.0, linestyle="--")

    fig.savefig(config.UNCERTAINTY_FIGURE, dpi=200, bbox_inches="tight",
                facecolor=config.COLOR_BG)
    print(f"\nSaved: {config.UNCERTAINTY_FIGURE}")


if __name__ == "__main__":
    main()
