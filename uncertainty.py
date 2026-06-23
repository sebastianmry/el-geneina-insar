"""Stage 3f: damage confidence / uncertainty layer.

The damage classification uses fixed relative-loss thresholds. This stage adds
the missing dimension: how trustworthy each cell's call is. For every built-up
cell `correct_baseline_drift.py` stores a signal-to-noise z-score (z_<epoch>),
the drift-corrected coherence drop divided by its standard error from the
within-cell spatial spread of coherence. A high z means the drop is large
relative to the local variability, so the damage call is confident; a low z means
the cell sits in the noise. Because pixels in a cell are spatially correlated,
the z reads as a relative confidence, not a strict p-value.

This script reports what share of the affected extent per epoch is statistically
confident.

    python uncertainty.py
"""

from __future__ import annotations

import config
import viz_common


def print_confidence(grid_gdf) -> None:
    """Report the confident share of the affected cells per epoch."""
    print("\n" + "=" * 60)
    print("Confidence of corrected-affected cells (signal-to-noise z)")
    print("=" * 60)
    print("  epoch | affected | confident (z>=1.6) | high (z>=2.3)")
    for epoch in config.DAMAGE_EPOCHS:
        affected = grid_gdf[grid_gdf[f"damagec_{epoch}"] >= 1]
        total = len(affected)
        if total == 0:
            continue
        confident = (affected[f"z_{epoch}"] >= config.Z_CONFIDENT).sum()
        high = (affected[f"z_{epoch}"] >= config.Z_HIGH_CONFIDENCE).sum()
        print(f"  {epoch:5s} | {total:8,} | {confident / total * 100:16.0f} % | "
              f"{high / total * 100:11.0f} %")


def main() -> None:
    config.configure_gdal_proj_env()
    grid_gdf = viz_common.load_damage_grid_corrected()
    if f"z_{config.DAMAGE_EPOCHS[0]}" not in grid_gdf.columns:
        raise SystemExit("No z_<epoch> columns: run correct_baseline_drift.py first.")
    print_confidence(grid_gdf)


if __name__ == "__main__":
    main()
