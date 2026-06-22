"""Damage overview figure: three-panel map of building damage per epoch.

Renders E2a / E2b / E3 side by side, colored by damage class, over the faded
reference coherence raster. The affected and severe percentages shown in the
bars are computed from the classification, not hardcoded.

    python viz_damage_overview.py
"""

from __future__ import annotations

import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt

import config
import viz_common

# Short period labels for the panel titles.
PERIOD_LABELS = {
    "E2a": "Apr - May 2023",
    "E2b": "Jun 2023  (Peak)",
    "E3": "Jul 2023",
}


def main() -> None:
    config.ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    # Both the headline percentages and the map use the drift-corrected class, a
    # single consistent scale with the rainy-season signal removed everywhere, so
    # the figure is neither rain-inflated nor internally inconsistent. The grid is
    # the statistical unit for the numbers; the footprints inherit their cell's
    # corrected class for the map.
    reference = viz_common.load_reference_raster()
    grid_gdf = viz_common.load_damage_grid_corrected()
    buildings_gdf = viz_common.load_damage_buildings_corrected(clip_to_valid=False)
    plot_gdf = viz_common.clip_to_valid_footprint(buildings_gdf, reference)

    fig, axes = plt.subplots(1, 3, figsize=(21, 9), facecolor=config.COLOR_BG)
    fig.subplots_adjust(left=0.01, right=0.99, top=0.93, bottom=0.12, wspace=0.03)

    fig.text(0.5, 0.965, "SAR Coherence Change Detection  -  El Geneina 2023",
             ha="center", va="center", color=config.COLOR_FG,
             fontsize=16, fontweight="bold")

    for ax, epoch in zip(axes, config.DAMAGE_EPOCHS):
        affected_pct, severe_pct = viz_common.damage_percentages(
            grid_gdf, epoch, column_prefix="damagec")
        _draw_panel(fig, ax, plot_gdf, reference, epoch, affected_pct, severe_pct)

    _add_legend(fig)

    output_path = config.ASSETS_DIR / "damage_overview.png"
    fig.savefig(output_path, dpi=200, bbox_inches="tight", facecolor=config.COLOR_BG)
    plt.close(fig)
    print(f"Saved: {output_path}")


def _draw_panel(fig, ax, buildings_gdf, reference, epoch, affected_pct, severe_pct):
    """Render a single epoch panel with its damage classes and stat bars.

    The percentages are the drift-corrected affected and severe shares.
    """
    ax.set_facecolor(config.COLOR_BG)
    viz_common.draw_coherence_backdrop(ax, reference, alpha=0.30)

    damage_column = f"damagec_{epoch}"
    for damage_class in (0, 1, 2, 3):
        subset = buildings_gdf[buildings_gdf[damage_column] == damage_class]
        if subset.empty:
            continue
        subset.plot(ax=ax, facecolor=config.DAMAGE_FILL[damage_class],
                    edgecolor=config.DAMAGE_EDGE[damage_class],
                    linewidth=config.DAMAGE_LINEWIDTH[damage_class],
                    alpha=config.DAMAGE_ALPHA[damage_class], zorder=2 + damage_class)

    ax.set_xlim(*config.PLOT_XLIM)
    ax.set_ylim(*config.PLOT_YLIM)
    ax.set_aspect("equal")
    ax.axis("off")
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_edgecolor(config.COLOR_LINE)
        spine.set_linewidth(0.8)

    viz_common.add_scale_bar(ax)
    viz_common.add_north_arrow(ax)

    ax.set_title(f"{epoch}  {PERIOD_LABELS[epoch]}", color=config.COLOR_FG,
                 fontsize=11, fontweight="bold", pad=8)

    _add_stat_bars(fig, ax, affected_pct, severe_pct)


def _add_stat_bars(fig, ax, affected_pct, severe_pct):
    """Draw the drift-corrected affected and severe percentage bars beneath a panel."""
    position = ax.get_position()
    bar_height = 0.013
    gap = 0.004
    y_top = position.y0 - 0.005

    bars = [
        (affected_pct, "#e07b39", "Affected", 0),
        (severe_pct, "#d62728", "Severe", 1),
    ]
    for index, (value_pct, color, name, decimals) in enumerate(bars):
        y = y_top - index * (bar_height + gap) - bar_height
        fig.add_artist(plt.Rectangle((position.x0, y), position.width, bar_height,
                                     transform=fig.transFigure, facecolor=config.COLOR_PANEL,
                                     clip_on=False, zorder=5))
        fig.add_artist(plt.Rectangle((position.x0, y), position.width * value_pct / 100,
                                     bar_height, transform=fig.transFigure,
                                     facecolor=color, clip_on=False, zorder=6))
        label = f"{name}  {value_pct:.{decimals}f}%"
        fig.text(position.x0 + 0.005, y + bar_height + 0.002, label,
                 transform=fig.transFigure, color=config.COLOR_FG, fontsize=7.5,
                 fontweight="bold", va="bottom",
                 path_effects=[pe.withStroke(linewidth=1.5, foreground=config.COLOR_BG)],
                 zorder=8)


def _add_legend(fig):
    """Add the shared damage-class legend at the bottom of the figure."""
    handles = [
        mpatches.Patch(facecolor=config.DAMAGE_FILL[c], edgecolor=config.DAMAGE_EDGE[c],
                       linewidth=0.8, label=config.DAMAGE_CLASS_LABELS[c])
        for c in (0, 1, 2, 3)
    ]
    legend = fig.legend(handles=handles,
                        title="Damage class  (relative coherence loss)",
                        title_fontsize=9, fontsize=9, loc="lower center", ncol=4,
                        frameon=True, framealpha=0.9, facecolor=config.COLOR_PANEL,
                        edgecolor=config.COLOR_LINE, labelcolor=config.COLOR_FG,
                        bbox_to_anchor=(0.5, 0.02))
    legend.get_title().set_color(config.COLOR_FG)


if __name__ == "__main__":
    main()
