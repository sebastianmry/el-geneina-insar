"""Diagnostic plot: SAR coherence loss vs. Sentinel-2 dNBR (no relationship).

Honest optical cross-check for the peak epoch E2b. Each point is a built-up 50 m
cell: the drift-corrected SAR coherence loss against the optical dNBR. The two
signals are uncorrelated (r near zero), so the optical reference cannot confirm
the SAR extent. This avoids a confusion matrix, which would wrongly treat the
optical signal as ground truth; mud-brick rubble is spectrally close to bare
soil, so optical change detection is blind to the destruction here. See
validate_optical.py and config.OPTICAL_VALIDATION_REPORT.
"""

from __future__ import annotations

import altair as alt
import geopandas as gpd
import numpy as np
import pandas as pd

import config
import palette

OUT_PATH = palette.ASSETS_DIR / "diag_optical_relationship.png"

EPOCH = config.OPTICAL_VALIDATION_EPOCH  # E2b, the peak
AFFECTED_LOSS_PCT = config.DAMAGE_THRESHOLDS[1] * 100.0  # 20 % loss
# Deep navy for the optical threshold, echoing the pre-conflict coherence blues.
OPTICAL_BLUE = "#2a4b7c"


def load_points_df() -> pd.DataFrame:
    """Returns per-cell coherence loss (%) and dNBR over built-up cells."""
    grid_gdf = gpd.read_file(
        config.OPTICAL_DNBR_FILE,
        columns=["building_count", f"relc_{EPOCH}", "dnbr"],
        ignore_geometry=True,
    )
    built_up = grid_gdf[grid_gdf["building_count"] > 0]
    loss = built_up[f"relc_{EPOCH}"].to_numpy(dtype=float) * 100.0
    dnbr = built_up["dnbr"].to_numpy(dtype=float)
    finite = np.isfinite(loss) & np.isfinite(dnbr)
    return pd.DataFrame({"loss": loss[finite], "dnbr": dnbr[finite]})


def build_chart(points_df: pd.DataFrame) -> alt.Chart:
    correlation = points_df["loss"].corr(points_df["dnbr"])

    points = (
        alt.Chart(points_df)
        .mark_circle(size=9, opacity=0.18, color=palette.DAMAGE_CLASSES["stable"], clip=True)
        .encode(
            x=alt.X("loss:Q", title="SAR coherence loss (%)", scale=alt.Scale(domain=[-10, 100])),
            y=alt.Y("dnbr:Q", title="Optical dNBR (pre - post)", scale=alt.Scale(domain=[-0.3, 0.5])),
        )
    )

    # The two decision thresholds: optical destruction (dNBR) and SAR affected.
    dnbr_rule = (
        alt.Chart(pd.DataFrame({"y": [config.DNBR_DESTRUCTION_THRESHOLD]}))
        .mark_rule(color=OPTICAL_BLUE, strokeDash=[4, 4], size=1)
        .encode(y="y:Q")
    )
    loss_rule = (
        alt.Chart(pd.DataFrame({"x": [AFFECTED_LOSS_PCT]}))
        .mark_rule(color=palette.MUTED, strokeDash=[4, 4], size=1)
        .encode(x="x:Q")
    )
    label = (
        alt.Chart(pd.DataFrame({"text": [f"r (loss, dNBR) = {correlation:.2f}"], "x": [98.0], "y": [0.46]}))
        .mark_text(align="right", baseline="top", fontSize=12, color=palette.INK)
        .encode(x="x:Q", y="y:Q", text="text:N")
    )
    # Label the two decision thresholds so they are not mistaken for statistics.
    dnbr_label = (
        alt.Chart(pd.DataFrame({"text": ["optical: dNBR ≥ 0.10"], "x": [-9.0], "y": [config.DNBR_DESTRUCTION_THRESHOLD]}))
        .mark_text(align="left", baseline="bottom", dy=-2, fontSize=10, color=OPTICAL_BLUE)
        .encode(x="x:Q", y="y:Q", text="text:N")
    )
    loss_label = (
        alt.Chart(pd.DataFrame({"text": ["SAR: loss ≥ 20 %"], "x": [AFFECTED_LOSS_PCT], "y": [-0.27]}))
        .mark_text(align="left", baseline="bottom", dx=4, fontSize=10, color=palette.MUTED)
        .encode(x="x:Q", y="y:Q", text="text:N")
    )

    return (
        points + dnbr_rule + loss_rule + label + dnbr_label + loss_label
    ).properties(width=520, height=320)


def main() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    chart = palette.apply_light_theme(build_chart(load_points_df()))
    chart.save(str(OUT_PATH), ppi=200)
    print(f"written: {OUT_PATH}")


if __name__ == "__main__":
    main()
