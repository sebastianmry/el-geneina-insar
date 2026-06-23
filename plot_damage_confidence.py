"""Diagnostic plot: per-cell damage confidence (z-score) at the peak epoch.

Instead of trusting a single fixed threshold, each cell's drift-corrected
coherence drop is divided by its within-cell spatial standard error to give a
signal-to-noise z-score. This figure shows the distribution of that confidence
over the affected cells at the peak epoch E2b, with the confident (z = 1.645)
and high-confidence (z = 2.33) markers. See uncertainty.py.
"""

from __future__ import annotations

import altair as alt
import geopandas as gpd
import numpy as np
import pandas as pd

import config
import palette

OUT_PATH = palette.ASSETS_DIR / "diag_damage_confidence.png"

EPOCH = config.OPTICAL_VALIDATION_EPOCH  # E2b, the peak
Z_MARKS = [
    (config.Z_CONFIDENT, "confident"),
    (config.Z_HIGH_CONFIDENCE, "high confidence"),
]


def load_confidence_df() -> pd.DataFrame:
    """Returns the per-cell z-score over affected built-up cells at the peak epoch."""
    columns = ["building_count", f"damagec_{EPOCH}", f"z_{EPOCH}"]
    grid_gdf = gpd.read_file(
        config.grid_drift_file(config.GRID_CELL_SIZE_M),
        columns=columns,
        ignore_geometry=True,
    )
    affected = grid_gdf[
        (grid_gdf["building_count"] > 0) & (grid_gdf[f"damagec_{EPOCH}"] >= 1)
    ]
    z = affected[f"z_{EPOCH}"].to_numpy(dtype=float)
    return pd.DataFrame({"z": z[np.isfinite(z)]})


def build_chart(confidence_df: pd.DataFrame) -> alt.Chart:
    density = (
        alt.Chart(confidence_df)
        .transform_density("z", as_=["z", "density"], extent=[-1, 6])
        .mark_area(opacity=0.6, interpolate="monotone", color=palette.DAMAGE_CLASSES["stable"])
        .encode(
            x=alt.X("z:Q", title="Damage confidence  z = signal / noise"),
            y=alt.Y("density:Q", title="Density", axis=alt.Axis(labels=False, ticks=False)),
        )
    )

    marks_df = pd.DataFrame({"z": [value for value, _ in Z_MARKS], "label": [label for _, label in Z_MARKS]})
    rules = (
        alt.Chart(marks_df)
        .mark_rule(color=palette.MUTED, strokeDash=[4, 4], size=1)
        .encode(x="z:Q")
    )
    # Anchor the lower marker to the left of its line and the upper one to the
    # right, so the two labels do not collide between the close thresholds.
    confident_label = (
        alt.Chart(marks_df.iloc[[0]])
        .mark_text(align="right", dx=-5, dy=6, fontSize=11, color=palette.MUTED, baseline="top")
        .encode(x="z:Q", y=alt.value(0), text="label:N")
    )
    high_label = (
        alt.Chart(marks_df.iloc[[1]])
        .mark_text(align="left", dx=5, dy=6, fontSize=11, color=palette.MUTED, baseline="top")
        .encode(x="z:Q", y=alt.value(0), text="label:N")
    )

    return (density + rules + confident_label + high_label).properties(width=520, height=300)


def main() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    chart = palette.apply_light_theme(build_chart(load_confidence_df()))
    chart.save(str(OUT_PATH), ppi=200)
    print(f"written: {OUT_PATH}")


if __name__ == "__main__":
    main()
