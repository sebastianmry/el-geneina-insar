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
ADMIN1 = NE_DIR / "ne_10m_admin_1_states_provinces.shp"
RIVERS = NE_DIR / "ne_50m_rivers_lake_centerlines.shp"

WEB_MERCATOR = "EPSG:3857"

# Main panel extent in lon/lat: tightened onto Sudan so the country fills the
# frame, while the eastern margin still keeps the Red Sea (and the Arabian coast
# beyond it) in view on the right.
MAIN_EXTENT_LONLAT = (17.0, 43.0, 6.0, 25.0)
# Inset box in lon/lat, flush to the top-right corner over the Red Sea / Arabia,
# clear of Sudan.
INSET_BOX_LONLAT = (37.4, 42.8, 19.3, 24.4)
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

# West Darfur (Natural Earth admin-1 name) and the capital for spatial context.
WEST_DARFUR_NAME = "Western Darfur"
WD_FILL = "#3a2517"
WD_EDGE = "#e07b39"
KHARTOUM_LON, KHARTOUM_LAT = 32.53, 15.50
# Red Sea label, placed mid-water and rotated along the basin's NW-SE trend.
RED_SEA_LONLAT = (40.0, 18.3)
RED_SEA_COLOR = "#6f8fc0"


def _merc_xy(lon, lat):
    """Project a single lon/lat point to Web Mercator and return (x, y)."""
    p = gpd.GeoSeries.from_xy([lon], [lat], crs="EPSG:4326").to_crs(WEB_MERCATOR)
    return p.x.iloc[0], p.y.iloc[0]


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

    _draw_west_darfur(ax)
    _draw_rivers(ax, extent_box)

    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)

    # Red Sea label, rotated along the basin so it reads as water, not land.
    rs_x, rs_y = _merc_xy(*RED_SEA_LONLAT)
    ax.text(rs_x, rs_y, "RED SEA", ha="center", va="center", rotation=-42,
            rotation_mode="anchor", color=RED_SEA_COLOR, fontsize=9,
            fontstyle="italic", fontweight="bold", zorder=5)

    # Centre each label on its country: the centroid of the visible part, so the
    # text sits in the middle of the area on screen and stays inside the frame.
    for _, row in countries.iterrows():
        if row["NAME"] not in LABEL_COUNTRIES:
            continue
        visible = row.geometry.intersection(extent_box)
        if visible.is_empty:
            continue
        point = visible.centroid
        if not visible.contains(point):       # concave shapes: keep it on land
            point = visible.representative_point()
        is_sudan = row["NAME"] == "Sudan"
        label = DISPLAY_NAMES.get(row["NAME"], row["NAME"]).upper()
        ax.text(point.x, point.y, label, ha="center", va="center",
                color=config.COLOR_FG if is_sudan else "#c9c9dd", alpha=1.0,
                fontsize=12 if is_sudan else 10,
                fontweight="bold" if is_sudan else "normal", zorder=5)

    # Khartoum: a quiet secondary marker so the eye stays on El Geneina.
    kh_x, kh_y = _merc_xy(KHARTOUM_LON, KHARTOUM_LAT)
    ax.scatter(kh_x, kh_y, s=28, color=config.COLOR_SUB, edgecolor=config.COLOR_BG,
               linewidth=0.8, zorder=6)
    ax.annotate("Khartoum", (kh_x, kh_y), textcoords="offset points",
                xytext=(8, 5), color=config.COLOR_SUB, fontsize=9, zorder=7)

    # El Geneina: the focal point, brighter and larger than any other marker.
    city = gpd.GeoSeries.from_xy([config.TARGET_LON], [config.TARGET_LAT],
                                 crs="EPSG:4326").to_crs(WEB_MERCATOR)
    cx, cy = city.x.iloc[0], city.y.iloc[0]
    _draw_aoi_reticle(ax, cx, cy)
    ax.scatter(cx, cy, s=95, color="#f5c518", edgecolor=config.COLOR_BG,
               linewidth=1.2, zorder=7)
    ax.annotate("El Geneina", (cx, cy), textcoords="offset points",
                xytext=(11, 8), color=config.COLOR_FG, fontsize=12,
                fontweight="bold", zorder=8,
                path_effects=[pe.withStroke(linewidth=2.5, foreground=config.COLOR_BG)])


def _draw_aoi_reticle(ax, cx, cy) -> None:
    """Draw a GEOINT-style corner-bracket reticle around the analysis AOI.

    The true AOI is only a few kilometres across, invisible at this scale, so the
    bracket is drawn at a fixed on-screen size as a callout that frames the city.
    """
    bounds = config.load_aoi_bounds()
    aoi_cx = (bounds["west"] + bounds["east"]) / 2
    aoi_cy = (bounds["south"] + bounds["north"]) / 2
    ax_cx, ax_cy = _merc_xy(aoi_cx, aoi_cy)
    half = 115000.0          # bracket half-size in metres (tight frame on the city)
    arm = half * 0.45        # length of each corner arm
    x0, x1 = ax_cx - half, ax_cx + half
    y0, y1 = ax_cy - half, ax_cy + half
    style = dict(color="#f5c518", linewidth=1.3, alpha=0.85, zorder=6,
                 solid_capstyle="round")
    for bx, sx in ((x0, 1), (x1, -1)):
        for by, sy in ((y0, 1), (y1, -1)):
            ax.plot([bx, bx + sx * arm], [by, by], **style)
            ax.plot([bx, bx], [by, by + sy * arm], **style)


def _draw_west_darfur(ax) -> None:
    """Highlight the West Darfur state polygon and label it from the east.

    Space above the state is cramped, so the label sits further east in open
    desert with a leader arrow pointing back to the highlighted region.
    """
    if not ADMIN1.exists():
        return
    states = gpd.read_file(ADMIN1, columns=["adm0_a3", "name", "geometry"])
    wd = states[(states["adm0_a3"] == "SDN") & (states["name"] == WEST_DARFUR_NAME)]
    if wd.empty:
        return
    wd = wd.to_crs(WEB_MERCATOR)
    wd.plot(ax=ax, facecolor=WD_FILL, edgecolor=WD_EDGE, linewidth=1.2,
            alpha=0.95, zorder=3)

    target_x, target_y = _merc_xy(24.3, 14.95)  # north-east edge of the state
    label_x, label_y = _merc_xy(25.6, 15.45)    # open ground just east of Darfur
    # Text and leader are drawn separately so the arrow starts exactly at the
    # vertical centre of the "W" (left edge of the label) instead of docking to
    # the lower corner of the text box.
    ax.text(label_x, label_y, "WEST DARFUR", ha="left", va="center",
            color=WD_EDGE, fontsize=10, fontweight="bold", zorder=7,
            path_effects=[pe.withStroke(linewidth=2.5, foreground=config.COLOR_BG)])
    ax.annotate("", xy=(target_x, target_y), xytext=(label_x, label_y),
                arrowprops=dict(arrowstyle="->", color=WD_EDGE, linewidth=1.2,
                                patchA=None, shrinkA=2, shrinkB=4), zorder=6)


def _draw_rivers(ax, extent_box) -> None:
    """Draw the major rivers (Nile system) clipped to the panel extent."""
    if not RIVERS.exists():
        return
    rivers = gpd.read_file(RIVERS).to_crs(WEB_MERCATOR)
    rivers = rivers[rivers.intersects(extent_box)]
    if rivers.empty:
        return
    clipped = rivers.clip(extent_box)
    clipped.plot(ax=ax, color=RIVER_COLOR, linewidth=1.0, alpha=1.0)
    _label_rivers(ax, clipped)


# Natural Earth river names -> the label to print, and where along the visible
# centreline (0 = start, 1 = end) to place it so labels avoid the confluence.
RIVER_LABELS = {
    "Nile": ("NILE", 0.5),
    "El Bahr el Abyad": ("WHITE NILE", 0.45),
    "El Bahr el Azraq": ("BLUE NILE", 0.55),
    "Atbara": ("ATBARA", 0.5),
}


def _label_rivers(ax, clipped: gpd.GeoDataFrame) -> None:
    """Place a small rotated label along each named major river."""
    import math

    for ne_name, (label, frac) in RIVER_LABELS.items():
        parts = clipped[clipped["name"] == ne_name]
        if parts.empty:
            continue
        line = max(parts.geometry, key=lambda g: g.length)   # longest visible reach
        if line.length == 0:
            continue
        pt = line.interpolate(frac, normalized=True)
        a = line.interpolate(max(frac - 0.04, 0.0), normalized=True)
        b = line.interpolate(min(frac + 0.04, 1.0), normalized=True)
        angle = math.degrees(math.atan2(b.y - a.y, b.x - a.x))
        if angle > 90:
            angle -= 180
        elif angle < -90:
            angle += 180
        ax.text(pt.x, pt.y, label, ha="center", va="center", rotation=angle,
                rotation_mode="anchor", color=RIVER_COLOR, fontsize=7.5,
                fontstyle="italic", fontweight="bold", zorder=5,
                path_effects=[pe.withStroke(linewidth=2.0, foreground=config.COLOR_BG)])


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
    ax.text(0.5, 0.99, "Study area", transform=ax.transAxes, ha="center",
            va="top", color=config.COLOR_FG, fontsize=15, fontweight="bold",
            path_effects=[pe.withStroke(linewidth=2.5, foreground=config.COLOR_BG)],
            zorder=9)

    config.ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
    fig.savefig(OUT_PATH, dpi=200, facecolor=config.COLOR_BG, bbox_inches="tight")
    plt.close(fig)
    print(f"written: {OUT_PATH}")


if __name__ == "__main__":
    main()
