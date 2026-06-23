"""Supplementary figure: pre-conflict reference (E1 coherence per building).

    python viz_supplementary.py
"""

from __future__ import annotations

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt

import config
import viz_common

# E1 coherence bins: (min, max, fill, edge, label). Sequential blue ramp on the
# dark backdrop: low coherence stays deep navy, high coherence glows light blue.
COH_BINS = [
    (0.00, 0.20, "#0d1b3e", "#1a2a50", "Very low  (0.0-0.2)"),
    (0.20, 0.35, "#1a4a72", "#1a5c8a", "Low  (0.2-0.35)"),
    (0.35, 0.50, "#2471a3", "#2980b9", "Medium  (0.35-0.5)"),
    (0.50, 0.65, "#5dade2", "#76b7e8", "High  (0.5-0.65)"),
    (0.65, 1.01, "#aed6f1", "#c5e3f5", "Very high  (0.65+)"),
]


def _style_axes(ax):
    ax.set_xlim(*config.PLOT_XLIM)
    ax.set_ylim(*config.PLOT_YLIM)
    ax.set_aspect("equal")
    ax.axis("off")
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_edgecolor(config.COLOR_LINE)
        spine.set_linewidth(0.8)


def plot_pre_conflict_reference(buildings_gdf, reference) -> None:
    """E1 coherence binned per building footprint."""
    print("\nPre-conflict reference panel...")
    fig, ax = plt.subplots(1, 1, figsize=(12, 13), facecolor=config.COLOR_BG)
    fig.subplots_adjust(left=0.03, right=0.97, top=0.92, bottom=0.04)

    ax.set_facecolor(config.COLOR_BG)
    # Match the damage overview's quieter backdrop so the figure set is consistent
    # and the coherence-binned footprints carry the panel, not the speckle.
    viz_common.draw_coherence_backdrop(ax, reference, alpha=0.20)

    no_data = buildings_gdf[buildings_gdf["coh_E1"].isna()]
    if not no_data.empty:
        no_data.plot(ax=ax, facecolor=config.COLOR_PANEL, edgecolor=config.COLOR_LINE,
                     linewidth=0.10, alpha=0.5, zorder=1)

    legend_patches = []
    for bin_min, bin_max, fill, edge, label in COH_BINS:
        subset = buildings_gdf[
            (buildings_gdf["coh_E1"] >= bin_min) & (buildings_gdf["coh_E1"] < bin_max)
        ]
        if subset.empty:
            continue
        subset.plot(ax=ax, facecolor=fill, edgecolor=edge,
                    linewidth=0.30, alpha=0.92, zorder=2)
        legend_patches.append(mpatches.Patch(facecolor=fill, edgecolor=edge,
                                             linewidth=0.8, label=f"{label}  (n={len(subset):,})"))

    _style_axes(ax)
    viz_common.add_scale_bar(ax)
    viz_common.add_north_arrow(ax)

    legend = ax.legend(handles=legend_patches, loc="lower right", frameon=True,
                       framealpha=0.9, facecolor=config.COLOR_PANEL, edgecolor=config.COLOR_LINE,
                       labelcolor=config.COLOR_FG, fontsize=8,
                       title=f"E1 coherence ({int(config.GRID_CELL_SIZE_M)} m grid cell)",
                       title_fontsize=8.5)
    legend.get_title().set_color(config.COLOR_FG)

    fig.text(0.5, 0.96, "Pre-Conflict Reference  -  El Geneina 2023", ha="center",
             color=config.COLOR_FG, fontsize=15, fontweight="bold")
    viz_common.add_attribution(fig, "© OpenStreetMap contributors")

    output_path = config.ASSETS_DIR / "pre_conflict_reference.png"
    fig.savefig(output_path, dpi=200, facecolor=config.COLOR_BG)
    plt.close(fig)
    print(f"  Saved: {output_path}")


def main() -> None:
    config.ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    buildings_gdf = viz_common.load_damage_buildings(clip_to_valid=True)
    reference = viz_common.load_reference_raster()

    plot_pre_conflict_reference(buildings_gdf, reference)


if __name__ == "__main__":
    main()
