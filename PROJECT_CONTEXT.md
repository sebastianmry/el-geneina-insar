# Project context

Background, design decisions and integrity rules for the El Geneina InSAR
Coherence Change Detection project. Intended for anyone extending the pipeline.

## Goal

Produce a defensible damage classification for El Geneina during the 2023
conflict using only cloud-independent SAR data. The statistical unit is a
resolution-matched 50 m grid, since individual HOT OSM footprints are sub-pixel
(median ~15 m2 against a 100 m2 pixel). The output is a GeoPackage of grid cells
and a building layer that inherits each cell's per-epoch coherence, relative loss
and damage class, plus a small set of figures.

## Why SAR coherence

Optical assessment is unreliable here: persistent cloud cover, smoke from fires
and no ground access. Interferometric coherence measures how stable the radar
backscatter is between two acquisitions. Intact, rigid structures stay coherent;
collapse, rubble and burning decorrelate the signal. Comparing each epoch
against a pre-conflict reference (E1) isolates conflict-driven change from
natural decorrelation.

## Key design decisions

- **Single source of truth (`config.py`):** all paths, AOI bounds, epoch and
  coherence-pair definitions, processing parameters and shared figure styling
  live in `config.py`. Nothing is hardcoded in individual scripts.
- **Data lives outside the repo:** raw scenes (~8 GB each), processing
  intermediates and building footprints are reproducible from public sources and
  are git-ignored. The repository holds code, the small AOI definition, docs and
  rendered showcase figures only. The data root is set via `SAR_DATA_DIR`.
- **Portable environment setup:** GDAL/PROJ data directories are derived from the
  active interpreter at runtime (`config.configure_gdal_proj_env`), not from
  machine-specific absolute paths.
- **Coregistration without ESD:** Enhanced Spectral Diversity is intentionally
  skipped. It is not required for coherence change detection, and a SNAP
  date-format bug ("31Mar2023") breaks it for this stack.
- **Sensor consistency:** a single sensor (Sentinel-1A), subswath (IW1), orbit
  direction (DESCENDING) and polarization set (VV+VH) is used across all epochs,
  so coherence differences reflect ground change rather than acquisition
  geometry.

## Integrity rules

- **No fabricated statistics:** affected/severe percentages shown in figures are
  computed from the classified data at render time, never hardcoded. The headline
  numbers come from the 50 m grid (the statistical unit), reported by
  `classify_grid.py`, while the map draws the building footprints that inherit
  each cell's class. Earlier exploratory code embedded these as literals; that
  has been removed.
- **Documented footprint cleaning:** the HOT OSM footprints pass a conservative
  quality control (`clean_buildings.py`) before any statistics. Only geometries
  that cannot be a standing building are removed (invalid, duplicate, micro
  sliver, under construction, outside the AOI), 15 of 137,560 in total, and every
  removed feature is counted by category in `docs/CLEANING_REPORT.md`.
- **No bridging of invalid data:** cells outside the area of valid coherence are
  excluded, not interpolated. Coherence values outside [0, 1] and nodata are
  masked to NaN before sampling.
- **Reference-relative, not absolute:** damage is defined by relative coherence
  loss against E1, which controls for land-cover-specific baseline coherence.

## Caveats

- Coherence loss is a proxy for physical surface change; it does not by itself
  confirm the cause (conflict vs. construction, flooding, vegetation change).
- The grid is the honest reporting unit, but the underlying resolution still
  cannot characterize an isolated sub-pixel footprint on its own.
- Rainy-season decorrelation (Sahel rains from June) inflates the E2b and E3
  affected figures; those epochs read as an upper bound. The drift correction
  (`correct_baseline_drift.py`) brackets this with a lower bound estimated from
  stable unbuilt reference cells. The pre-conflict reference itself is checked
  for stability in `check_baseline.py`.
- The 12-day revisit means sub-epoch timing of individual events cannot be
  resolved.
- Optical validation has a ceiling here (`validate_optical.py`). A Sentinel-2
  dNBR check on phenology-matched dry-season scenes does not reproduce the SAR
  pattern (correlation 0.03): mud-brick rubble is spectrally close to bare soil,
  so optical change detection at 10-20 m cannot see it. The check rules out the
  raw upper bound as literal destruction but cannot confirm the lower bound; that
  would need sub-metre imagery. SAR-internal checks carry the confidence.

## Possible extensions

- Incorporate VH alongside VV for the coherence estimate.
- Add an ascending-orbit track to reduce layover/shadow ambiguity.
- Uncertainty layer from intra-epoch coherence variance.
- Deep-learning segmentation (e.g. U-Net on Sentinel-1) to suppress
  environmental false positives, planned as a separate project.
