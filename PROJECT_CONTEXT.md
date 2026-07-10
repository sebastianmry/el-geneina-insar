# Project context

Background, design decisions and integrity rules for the El Geneina InSAR
Coherence Change Detection project. Intended for anyone extending the pipeline.

## Goal

Produce a defensible damage classification for El Geneina during the 2023
conflict using only open SAR data. The statistical unit is a
resolution-matched 50 m grid, since individual HOT OSM footprints are sub-pixel
(median ~15 m2 against a 100 m2 pixel). The output is a GeoPackage of grid cells
and a building layer that inherits each cell's per-epoch coherence, relative loss
and damage class, plus a small set of figures.

## Why SAR coherence

With no independent ground access, the damage can only be assessed from orbit,
and optical imagery struggles here for a specific reason: collapsed mud-brick is
spectrally almost indistinguishable from the surrounding bare soil, so even
cloud-free scenes miss it (confirmed by the null dNBR cross-validation). SAR
responds to the physical change instead. Interferometric coherence measures how
stable the radar backscatter is between two acquisitions. Intact, rigid structures stay coherent;
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
- **Dual-polarisation fusion:** coherence is estimated on both VV and VH. Because
  VH coherence sits systematically below VV, the channels are not averaged
  directly; each is normalised against its own E1 baseline into a relative loss
  and the two losses are averaged. VV and VH correlate only moderately (r about
  0.4 to 0.6), so the fusion reduces noise, and VH is markedly more robust to the
  rainy-season decorrelation (`compare_polarisations.py`).

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
- **Per-epoch active change, not cumulative:** coherence is computed on
  within-epoch image pairs, so each epoch records active change during that
  window, not a running total. E3 reflects continued July change, not June damage
  carried forward; the dry-season E2a figure is the single most robust value.
- **Confidence reported, not just a class:** each cell carries a signal-to-noise
  z-score (`uncertainty.py`) so calls are not presented as more certain than they
  are. The thresholded affected extent coincides with statistical significance
  (z >= 1.6), confirming the thresholds are not arbitrary. The z is a relative
  confidence (pixels within a cell are spatially correlated), not a strict p-value.

## Caveats

- Coherence loss is a proxy for physical surface change; it does not by itself
  confirm the cause (conflict vs. construction, flooding, vegetation change).
- The grid is the honest reporting unit, but the underlying resolution still
  cannot characterize an isolated sub-pixel footprint on its own.
- Rainy-season decorrelation (Sahel rains from June) inflates the E2b and E3
  affected figures; those epochs read as an upper bound. The drift correction
  (`correct_baseline_drift.py`) brackets this with a lower bound estimated from
  stable unbuilt reference cells, per polarisation. The cross-pol VH channel is
  far less affected by the rain (R_env about 0.9 vs 0.66 for VV at the June peak),
  so the fused result keeps damage signal where VV alone is swamped. The
  pre-conflict reference itself is checked for stability in `check_baseline.py`.
- The 12-day revisit means sub-epoch timing of individual events cannot be
  resolved.
- A single descending track has no ascending counterpart, so layover and
  shadow in El Geneina's dense, low-rise fabric are not averaged out. Pairing an
  ascending track is the standard fix, but it was not available: Sentinel-1B
  failed in December 2021 and left no ascending coverage of El Geneina for the
  2023 study period. Affected buildings on the sensor-facing or far side of a
  block can be over- or under-represented in the coherence signal independently
  of actual damage.
- Optical validation has a ceiling here (`validate_optical.py`). A Sentinel-2
  dNBR check on phenology-matched dry-season scenes does not reproduce the SAR
  pattern (correlation 0.03): mud-brick rubble is spectrally close to bare soil,
  so optical change detection at 10-20 m cannot see it. The check rules out the
  raw upper bound as literal destruction but cannot confirm the lower bound; that
  would need sub-metre imagery. SAR-internal checks carry the confidence.
- The backscatter intensity cross-check has the same ceiling
  (`classify_intensity.py`). The dual-pol intensity log-ratio does not reproduce
  the coherence pattern (correlation -0.11) and confirms only 1-9 % of the
  coherence-affected cells, because mud-brick rubble scatters radar much like bare
  soil. Used as a false-positive filter it collapses the extent to under 1 %,
  which is the channel's sensitivity floor on this fabric, not a damage estimate.
  The drift-corrected dual-pol headline stands; the intensity is a second,
  radar-internal line of evidence that incoherent change detection fails on mud
  brick at this resolution, which is the case for coherence change detection here.

## Possible extensions

The main direction is a supervised deep-learning segmentation step that learns
the destruction signature from labelled examples and separates it from the
environmental decorrelation the coherence proxy cannot filter. It would train on
consistent damage ground truth across several affected areas and multiple time
windows so it generalises rather than fitting one site or season. Newer free
radar data would help: NISAR L-band decorrelates more slowly, and Sentinel-1C
restores the revisit and ascending coverage missing during the 2023 study
period. Planned as a separate project.
