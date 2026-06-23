"""Diagnostic plot: affected extent per epoch, raw vs. drift-corrected.

The rainy-season epochs (E2b, E3) decorrelate from seasonal moisture as well as
from destruction. The drift correction, estimated from bare ground, removes the
environmental component and turns the raw single-number extent into an honest
upper/lower bracket. This figure shows how far the correction pulls the affected
share down, especially at the peak epoch E2b. See correct_baseline_drift.py.
"""

from __future__ import annotations

import altair as alt
import geopandas as gpd
import pandas as pd

import config
import palette

OUT_PATH = palette.ASSETS_DIR / "diag_damage_bracket.png"

METHOD_LABELS = {"raw": "raw", "corrected": "drift-corrected"}


def load_bracket_df() -> pd.DataFrame:
    """Returns the affected share per epoch for the raw and corrected classes.

    Reads the drift-corrected 50 m grid, keeps built-up cells and computes the
    share of classified cells reaching the affected class (>= 1) for both the
    raw damage column and the drift-corrected one.
    """
    columns = ["building_count"] + [
        f"{prefix}_{epoch}"
        for epoch in config.DAMAGE_EPOCHS
        for prefix in ("damage", "damagec")
    ]
    grid_gdf = gpd.read_file(
        config.grid_drift_file(config.GRID_CELL_SIZE_M),
        columns=columns,
        ignore_geometry=True,
    )
    built_up = grid_gdf[grid_gdf["building_count"] > 0]

    records = []
    for epoch in config.DAMAGE_EPOCHS:
        for method, prefix in (("raw", "damage"), ("corrected", "damagec")):
            damage = built_up[f"{prefix}_{epoch}"]
            classified = damage[damage >= 0]
            affected_pct = (classified >= 1).mean() * 100.0
            records.append((epoch, METHOD_LABELS[method], affected_pct))
    return pd.DataFrame(records, columns=["epoch", "method", "affected_pct"])


def build_chart(bracket_df: pd.DataFrame) -> alt.Chart:
    order = list(METHOD_LABELS.values())
    # Raw is the inflated upper bound (warm sand), corrected is the result (teal).
    # Deliberately not the terracotta "destroyed" red: raw is not destruction.
    colors = [palette.DAMAGE_CLASSES["partial"], palette.DAMAGE_CLASSES["stable"]]
    scale = alt.Scale(domain=order, range=colors)

    base = alt.Chart(bracket_df).encode(
        x=alt.X("epoch:N", title=None, sort=config.DAMAGE_EPOCHS, axis=alt.Axis(labelAngle=0)),
        xOffset=alt.XOffset("method:N", sort=order),
    )
    bars = base.mark_bar(cornerRadiusEnd=2).encode(
        y=alt.Y("affected_pct:Q", title="Affected built-up cells (%)", scale=alt.Scale(domain=[0, 70])),
        color=alt.Color("method:N", scale=scale, legend=alt.Legend(title=None, orient="top-left")),
    )
    labels = base.mark_text(dy=-6, fontSize=11, color=palette.INK).encode(
        y="affected_pct:Q",
        text=alt.Text("affected_pct:Q", format=".0f"),
    )
    return (bars + labels).properties(width=480, height=300)


def main() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    chart = palette.apply_light_theme(build_chart(load_bracket_df()))
    chart.save(str(OUT_PATH), ppi=200)
    print(f"written: {OUT_PATH}")


if __name__ == "__main__":
    main()
