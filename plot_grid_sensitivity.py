"""Diagnostic plot: grid resolution sensitivity of the damage extent.

The statistical unit is a grid cell, so the chosen cell size could bias the
headline numbers. This figure reports the affected and severe shares at the peak
epoch E2b across three cell sizes. The affected extent is stable from 30 to
100 m, while the severe class is smeared out at 100 m because total destruction
is a sub-cell phenomenon, which is why 50 m is the chosen resolution. See config
GRID_CELL_SIZES_M.
"""

from __future__ import annotations

import altair as alt
import geopandas as gpd
import pandas as pd

import config
import palette

OUT_PATH = palette.ASSETS_DIR / "diag_grid_sensitivity.png"

EPOCH = config.OPTICAL_VALIDATION_EPOCH  # E2b, the peak
METRIC_LABELS = {"affected": "affected (>= 20 % loss)", "severe": "severe (> 60 % loss)"}


def load_sensitivity_df() -> pd.DataFrame:
    """Returns affected and severe shares per cell size at the peak epoch."""
    records = []
    for cell_size_m in config.GRID_CELL_SIZES_M:
        grid_gdf = gpd.read_file(
            config.grid_damage_file(cell_size_m),
            columns=["building_count", f"damage_{EPOCH}"],
            ignore_geometry=True,
        )
        built_up = grid_gdf[grid_gdf["building_count"] > 0]
        classified = built_up[f"damage_{EPOCH}"][built_up[f"damage_{EPOCH}"] >= 0]
        label = f"{int(cell_size_m)} m"
        records.append((label, METRIC_LABELS["affected"], (classified >= 1).mean() * 100.0))
        records.append((label, METRIC_LABELS["severe"], (classified >= 3).mean() * 100.0))
    return pd.DataFrame(records, columns=["cell_size", "metric", "pct"])


def build_chart(sensitivity_df: pd.DataFrame) -> alt.Chart:
    order = [f"{int(c)} m" for c in config.GRID_CELL_SIZES_M]
    metric_order = list(METRIC_LABELS.values())
    colors = [palette.DAMAGE_CLASSES["stable"], palette.DAMAGE_CLASSES["destroyed"]]
    scale = alt.Scale(domain=metric_order, range=colors)

    base = alt.Chart(sensitivity_df).encode(
        x=alt.X("cell_size:N", title="Grid cell size", sort=order, axis=alt.Axis(labelAngle=0)),
        xOffset=alt.XOffset("metric:N", sort=metric_order),
    )
    bars = base.mark_bar(cornerRadiusEnd=2).encode(
        y=alt.Y(
            "pct:Q",
            title="Built-up cells, raw classification (%)",
            scale=alt.Scale(domain=[0, 70]),
        ),
        color=alt.Color("metric:N", scale=scale, legend=alt.Legend(title=None, orient="top")),
    )
    labels = base.mark_text(dy=-6, fontSize=11, color=palette.INK).encode(
        y="pct:Q",
        text=alt.Text("pct:Q", format=".1f"),
    )
    return (bars + labels).properties(width=480, height=300)


def main() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    chart = palette.apply_light_theme(build_chart(load_sensitivity_df()))
    chart.save(str(OUT_PATH), ppi=200)
    print(f"written: {OUT_PATH}")


if __name__ == "__main__":
    main()
