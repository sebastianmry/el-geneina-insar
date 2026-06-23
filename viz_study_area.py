"""Study-area locator figure (Fig. 1): where El Geneina sits.

A dark locator in the same ICEYE-style palette as the damage maps. The main panel
shows western Sudan and its neighbours with the city, the analysis AOI and a West
Darfur label; a small Africa inset gives the continental context. Country outlines
come from Natural Earth (admin-0, 50 m), downloaded under DATA_ROOT/naturalearth.

    python viz_study_area.py
"""

from __future__ import annotations

import geopandas as gpd
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
from shapely.geometry import box

import config

OUT_PATH = config.ASSETS_DIR / "study_area.png"
NE_DIR = config.DATA_ROOT / "naturalearth"
ADMIN0 = NE_DIR / "ne_50m_admin_0_countries.shp"
RIVERS = NE_DIR / "ne_50m_rivers_lake_centerlines.shp"

WEB_MERCATOR = "EPSG:3857"

# Main panel extent in lon/lat: Sudan and named neighbours, pulled north to the
# Nile delta and the Mediterranean coast. The eastern margin (Red Sea / Arabia)
# plus this northern band leave room for the inset clear of Sudan.
MAIN_EXTENT_LONLAT = (13.0, 46.0, 0.0, 33.0)
# Inset box in lon/lat, flush to the top-right corner. The northern band (lat
# 26-33) sits well above Sudan (max ~22 N), so the locator never overlaps it.
INSET_BOX_LONLAT = (39.0, 46.0, 26.0, 33.0)
# Inset map content: Africa with Europe and the Middle East in view.
INSET_VIEW_LONLAT = (-20.0, 60.0, -38.0, 60.0)
# Neighbours labelled at the representative point of their visible part.
LABEL_COUNTRIES = {
    "Sudan", "Chad", "S. Sudan", "Central African Rep.", "Egypt",
    "Libya", "Eritrea", "Ethiopia",
}
# Spell out abbreviated Natural Earth names for the labels.
DISPLAY_NAMES = {"S. Sudan": "South Sudan", "Central African Rep.": "Central African Rep."}
RIVER_COLOR = "#4a6fa5"


def _to_mercator(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    return gdf.to_crs(WEB_MERCATOR)


def _extent_mercator(lon_min, lon_max, lat_min, lat_max):
    """Return (xmin, xmax, ymin, ymax) of a lon/lat box in Web Mercator."""
    corners = gpd.GeoSeries([box(lon_min, lat_min, lon_max, lat_max)], crs="EPSG:4326")
    xmin, ymin, xmax, ymax = corners.to_crs(WEB_MERCATOR).total_bounds
    return xmin, xmax, ymin, ymax


def _style_panel(ax) -> None:
    """Style the main panel seamlessly: no ticks, no frame border."""
    ax.set_facecolor(config.COLOR_BG)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.margins(0)


def draw_main(ax, countries: gpd.GeoDataFrame) -> None:
    """Draw the Sudan-centred locator panel with neighbours and major rivers."""
    xmin, xmax, ymin, ymax = _extent_mercator(*MAIN_EXTENT_LONLAT)
    extent_box = box(xmin, ymin, xmax, ymax)

    countries.plot(ax=ax, facecolor=config.COLOR_PANEL, edgecolor=config.COLOR_LINE,
                   linewidth=0.6)
    sudan = countries[countries["NAME"] == "Sudan"]
    sudan.plot(ax=ax, facecolor="#241a14", edgecolor=config.COLOR_SUB, linewidth=1.0)

    _draw_rivers(ax, extent_box)

    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)

    # Label each neighbour at the representative point of its visible part, so
    # the text stays inside the frame even when the country centroid is outside.
    for _, row in countries.iterrows():
        if row["NAME"] not in LABEL_COUNTRIES:
            continue
        visible = row.geometry.intersection(extent_box)
        if visible.is_empty:
            continue
        point = visible.representative_point()
        is_sudan = row["NAME"] == "Sudan"
        label = DISPLAY_NAMES.get(row["NAME"], row["NAME"]).upper()
        ax.text(point.x, point.y, label, ha="center", va="center",
                color=config.COLOR_FG if is_sudan else "#c9c9dd", alpha=1.0,
                fontsize=12 if is_sudan else 10,
                fontweight="bold" if is_sudan else "normal", zorder=5)

    # City marker only (no AOI box).
    city = gpd.GeoSeries.from_xy([config.TARGET_LON], [config.TARGET_LAT],
                                 crs="EPSG:4326").to_crs(WEB_MERCATOR)
    ax.scatter(city.x, city.y, s=80, color="#f5c518", edgecolor=config.COLOR_BG,
               linewidth=1.0, zorder=6)
    ax.annotate("El Geneina", (city.x.iloc[0], city.y.iloc[0]),
                textcoords="offset points", xytext=(9, 7),
                color=config.COLOR_FG, fontsize=10, fontweight="bold", zorder=7)


def _draw_rivers(ax, extent_box) -> None:
    """Draw the major rivers (Nile system) clipped to the panel extent."""
    if not RIVERS.exists():
        return
    rivers = gpd.read_file(RIVERS).to_crs(WEB_MERCATOR)
    rivers = rivers[rivers.intersects(extent_box)]
    if rivers.empty:
        return
    rivers.clip(extent_box).plot(ax=ax, color=RIVER_COLOR, linewidth=1.0, alpha=1.0)


def draw_inset(parent_ax, countries: gpd.GeoDataFrame) -> None:
    """Locator inset (Africa with Europe and the Middle East), Sudan highlighted.

    Positioned in data coordinates flush to the top-right map corner and east of
    Sudan, so it never overlaps the country regardless of the axes aspect.
    """
    bx0, bx1, by0, by1 = _extent_mercator(*INSET_BOX_LONLAT)
    inset = parent_ax.inset_axes(
        [bx0, by0, bx1 - bx0, by1 - by0], transform=parent_ax.transData, zorder=8
    )
    inset.set_facecolor(config.COLOR_BG)
    inset.set_xticks([])
    inset.set_yticks([])
    for spine in inset.spines.values():
        spine.set_edgecolor(config.COLOR_SUB)

    countries.plot(ax=inset, facecolor=config.COLOR_PANEL,
                   edgecolor=config.COLOR_LINE, linewidth=0.2)
    countries[countries["NAME"] == "Sudan"].plot(
        ax=inset, facecolor="#f5c518", edgecolor="#f5c518", linewidth=0.2)

    vxmin, vxmax, vymin, vymax = _extent_mercator(*INSET_VIEW_LONLAT)
    inset.set_xlim(vxmin, vxmax)
    inset.set_ylim(vymin, vymax)


def main() -> None:
    if not ADMIN0.exists():
        raise SystemExit(
            f"Natural Earth admin-0 not found at {ADMIN0}.\n"
            "Download and unzip the 50 m countries shapefile into that folder:\n"
            "  https://naciscdn.org/naturalearth/50m/cultural/ne_50m_admin_0_countries.zip"
        )

    countries = _to_mercator(gpd.read_file(ADMIN0, columns=["NAME"]))

    # Size the figure to the data aspect so the map fills the frame with no
    # vertical letterboxing below the content.
    xmin, xmax, ymin, ymax = _extent_mercator(*MAIN_EXTENT_LONLAT)
    fig_w = 11.0
    fig_h = fig_w * (ymax - ymin) / (xmax - xmin)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), facecolor=config.COLOR_BG)
    _style_panel(ax)
    draw_main(ax, countries)
    draw_inset(ax, countries)
    # Title set inside the frame, centred over the Mediterranean between the top
    # edge and the Egyptian coast (rather than in a margin above the map).
    ax.text(0.5, 0.972, "Study area", transform=ax.transAxes, ha="center",
            va="center", color=config.COLOR_FG, fontsize=14, fontweight="bold",
            path_effects=[pe.withStroke(linewidth=2.5, foreground=config.COLOR_BG)],
            zorder=9)

    config.ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
    fig.savefig(OUT_PATH, dpi=200, facecolor=config.COLOR_BG, bbox_inches="tight")
    plt.close(fig)
    print(f"written: {OUT_PATH}")


if __name__ == "__main__":
    main()
