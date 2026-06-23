"""Damage overview figure: three-panel map of building damage per epoch.

Renders E2a / E2b / E3 side by side, colored by damage class, over the faded
reference coherence raster. The affected percentage shown in the bar is computed
from the classification, not hardcoded. The severe share is near zero after the
drift correction, so it is reported in the README rather than as an empty bar.

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

# Stat-bar styling. The gauge fill picks up the light-class gold, the colour that
# carries the whole figure, so the bar echoes the dominant damage signal. A faint
# dark track shows the 100 % reference.
BAR_TRACK = config.COLOR_PANEL
BAR_AFFECTED = config.DAMAGE_FILL[1]


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

    n_panels = len(config.DAMAGE_EPOCHS)
    for idx, (ax, epoch) in enumerate(zip(axes, config.DAMAGE_EPOCHS)):
        affected_pct, _ = viz_common.damage_percentages(
            grid_gdf, epoch, column_prefix="damagec")
        _draw_panel(fig, ax, plot_gdf, reference, epoch, affected_pct,
                    is_first=idx == 0, is_last=idx == n_panels - 1)

    _add_legend(fig)
    viz_common.add_attribution(fig, "© OpenStreetMap contributors")

    output_path = config.ASSETS_DIR / "damage_overview.png"
    fig.savefig(output_path, dpi=200, bbox_inches="tight", facecolor=config.COLOR_BG)
    plt.close(fig)
    print(f"Saved: {output_path}")


def _draw_panel(fig, ax, buildings_gdf, reference, epoch, affected_pct,
                is_first, is_last):
    """Render a single epoch panel with its damage classes and the affected bar.

    The percentage is the drift-corrected affected share. Map furniture is shown
    once across the row (scale bar on the first panel, north arrow on the last)
    since all panels share one extent.
    """
    ax.set_facecolor(config.COLOR_BG)
    # Quieter backdrop so the damage classes carry the figure, not the speckle.
    viz_common.draw_coherence_backdrop(ax, reference, alpha=0.20)

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

    if is_first:
        viz_common.add_scale_bar(ax)
    if is_last:
        viz_common.add_north_arrow(ax)

    ax.set_title(f"{epoch}  {PERIOD_LABELS[epoch]}", color=config.COLOR_FG,
                 fontsize=11, fontweight="bold", pad=8)

    _add_stat_bar(fig, ax, affected_pct)


def _add_stat_bar(fig, ax, affected_pct):
    """Draw the drift-corrected affected gauge beneath a panel.

    A faint full-width track carries the affected fill in the light-class gold,
    the dominant colour of the figure.
    """
    position = ax.get_position()
    bar_height = 0.013
    y = position.y0 - 0.005 - bar_height

    fig.add_artist(plt.Rectangle((position.x0, y), position.width, bar_height,
                                 transform=fig.transFigure, facecolor=BAR_TRACK,
                                 clip_on=False, zorder=5))
    fig.add_artist(plt.Rectangle((position.x0, y), position.width * affected_pct / 100,
                                 bar_height, transform=fig.transFigure,
                                 facecolor=BAR_AFFECTED, clip_on=False, zorder=6))

    label = f"Affected  {affected_pct:.0f}%"
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
                        frameon=False, labelcolor=config.COLOR_FG,
                        bbox_to_anchor=(0.5, 0.02))
    legend.get_title().set_color(config.COLOR_FG)


if __name__ == "__main__":
    main()
