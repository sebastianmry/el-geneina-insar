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
from scipy.stats import gaussian_kde

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
    # Evaluate the KDE ourselves so the curve runs back to zero at both ends
    # (no clipping) and so we know its peak: the y-domain then gets headroom that
    # keeps the curve clear of the threshold labels along the top.
    z = confidence_df["z"].to_numpy(dtype=float)
    z_max = float(np.ceil(z.max()))
    grid = np.linspace(0.0, z_max, 400)
    density_values = gaussian_kde(z)(grid)
    density_df = pd.DataFrame({"z": grid, "density": density_values})
    y_max = float(density_values.max()) * 1.18

    density = (
        alt.Chart(density_df)
        .mark_area(opacity=0.6, interpolate="monotone", color=palette.DAMAGE_CLASSES["stable"])
        .encode(
            x=alt.X("z:Q", title="Damage confidence  z = signal / noise",
                    scale=alt.Scale(domain=[0.0, z_max], nice=False)),
            y=alt.Y("density:Q", title="Density", axis=alt.Axis(labels=False, ticks=False),
                    scale=alt.Scale(domain=[0.0, y_max], nice=False)),
        )
    )

    marks_df = pd.DataFrame({"z": [value for value, _ in Z_MARKS], "label": [label for _, label in Z_MARKS]})
    rules = (
        alt.Chart(marks_df)
        .mark_rule(color=palette.MUTED, strokeDash=[4, 4], size=1)
        .encode(x="z:Q")
    )
    # Anchor "confident" to the left of its rule and "high confidence" to the
    # right of its rule, so neither word is crossed by a line. The font is sized
    # down so "confident" fits left of its rule without overrunning the axis,
    # keeping the x-domain tight at zero (no empty negative margin).
    label_size = 8
    confident_label = (
        alt.Chart(marks_df.iloc[[0]])
        .mark_text(align="right", dx=-4, dy=6, fontSize=label_size, color=palette.INK, baseline="top")
        .encode(x="z:Q", y=alt.value(0), text="label:N")
    )
    high_label = (
        alt.Chart(marks_df.iloc[[1]])
        .mark_text(align="left", dx=4, dy=6, fontSize=label_size, color=palette.INK, baseline="top")
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
