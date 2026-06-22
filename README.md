# El Geneina InSAR Coherence Change Detection

Building-level damage mapping for El Geneina (al-Junaynah), West Darfur, during
the 2023 conflict, derived from Sentinel-1 InSAR coherence loss.

Between April and July 2023, El Geneina was the site of large-scale violence and
destruction during the Rapid Support Forces (RSF) offensive in West Darfur.
Persistent cloud cover and the absence of ground access make optical assessment
unreliable. Synthetic Aperture Radar (SAR) works regardless of cloud cover or
daylight, and interferometric **coherence** is highly sensitive to physical change on the
ground: when a building is destroyed, the radar surface decorrelates and
coherence drops. This project turns that signal into a damage map of the city.

The statistical unit is a **resolution-matched grid** rather than the individual
building. HOT OSM footprints in El Geneina have a median area near 15 m2, well
below a single 10 m Sentinel-1 pixel (100 m2), so a per-building coherence value
is a sub-pixel sample shared with its neighbours. Aggregating onto a 50 m grid
restores several independent coherence estimates per cell, which is the
defensible unit for reporting. Each building then inherits the class of the cell
it falls in, so the map keeps the familiar footprint view while the numbers rest
on the grid. This mirrors the damage-density approach used in UNOSAT Sentinel-1
coherence products.

> Background and discussion: [LinkedIn post](https://www.linkedin.com/posts/sebastian-macherey-1b140b316_remotesensing-insar-sar-ugcPost-7451764362064809984-_lhB/)

![Damage overview](assets/damage_overview.png)

---

## Background

Since April 2023 a power struggle between the Sudanese Armed Forces (SAF) and the
paramilitary Rapid Support Forces (RSF) has driven one of the world's most severe
humanitarian crises. In West Darfur the violence took on a targeted ethnic
dimension. The RSF, which evolved from the Janjaweed militias, used tactics seen
in the genocide twenty years earlier: deliberate arson, snipers targeting
civilians at water sources, and total sieges. Human Rights Watch has documented a
systematic campaign of ethnic cleansing against the Masalit, Fur and Zaghawa
communities.

The destruction in El Geneina followed a calculated strategy of displacement. As
this analysis shows, the western districts, predominantly inhabited by the
Masalit, were systematically burned and the ruins leveled to erase their physical
footprint and prevent return. In June 2023 the RSF seized full control of the
city. Up to 15,000 people were killed in El Geneina alone, most of them targeted
because of their Masalit identity, and hundreds of thousands fled toward Chad,
South Sudan and Egypt.

Remote sensing cannot stop atrocities, but public satellite data provides an
objective, independent record of destruction when ground access is barred.

Conflict chronology, measured as the share of built-up grid cells per epoch
(50 m grid). All classes are drift-corrected for rainy-season decorrelation, a
single consistent scale; the higher raw values are reported as an upper bound
under Baseline robustness:

| Epoch | Period | Affected built-up area | Severe |
| :--- | :--- | ---: | ---: |
| E1 | Mar-Apr 2023 | pre-conflict baseline | - |
| E2a | Apr-May 2023 | 16 % (initial offensive and arson) | 0.2 % |
| E2b | Jun 2023 | 18 % (peak destruction) | 0.1 % |
| E3 | Jul 2023 | 16 % (post-peak, RSF control) | 0.0 % |

Across the 137,545 quality-controlled HOT OSM building footprints
([cleaning report](docs/CLEANING_REPORT.md)), the corrected affected signal is
stable near 16 to 18 % of built-up cells across all three epochs, with June (E2b)
the peak. The dry-season first offensive (E2a) is the most robust figure because
the seasonal correction barely moves it. The corrected severe class is small once
the seasonal signal is removed: destruction past 60 % excess coherence loss is
rare and spatially clustered rather than pervasive. The raw uncorrected extent
runs to about two thirds, but that is dominated by rainy-season decorrelation
rather than destruction, and high-resolution optical imagery shows nothing near
that extent (see Optical cross-validation).

**Interpretation.** InSAR is weather-independent but needs careful reading.
Environmental factors such as sand drift or heavy rain can cause decorrelation
and false positives. SAR gives a forensic overview but cannot separate arson from
shelling, so cross-validation with high-resolution optical imagery remains
essential for final attribution.

---

## Method

**Coherence Change Detection (CCD).** Interferometric coherence is computed for
12-day Sentinel-1A pairs grouped into four epochs. Each epoch is compared
against the pre-conflict reference (E1). A grid cell whose coherence collapses
relative to E1 is flagged as damaged, binned into four classes by the relative
coherence loss.

| Epoch | Period | Role |
| :--- | :--- | :--- |
| **E1** | Mar-Apr 2023 | Pre-conflict reference (city intact) |
| **E2a** | Apr-May 2023 | First strike (after conflict onset 15 Apr) |
| **E2b** | Jun 2023 | Peak destruction (around the 14-22 Jun massacre) |
| **E3** | Jul 2023 | Post-conflict (city under RSF control) |

**Damage classes** (relative coherence loss vs. E1):

| Class | Loss | Meaning |
| :--- | :--- | :--- |
| 0 | < 20 % | No damage |
| 1 | >= 20 % | Light |
| 2 | >= 40 % | Moderate |
| 3 | >= 60 % | Severe |

**Footprint quality control.** The HOT OSM download is screened once before any
coherence is sampled (`clean_buildings.py`). The screening repairs or drops
invalid and empty geometries, removes exact duplicates, micro polygons below
1 m2, line-like slivers, sites tagged as still under construction, and footprints
outside the study area. The filters are deliberately conservative, so the damage
percentages stay unbiased: only 15 of 137,560 footprints are removed (99.99 %
retained). Every removed feature is counted by category in the
[cleaning report](docs/CLEANING_REPORT.md).

**Resolution-matched grid.** The [HOT OSM](https://www.hotosm.org/) footprints
in El Geneina have a median area near 15 m2, far below a 10 m Sentinel-1 pixel
(100 m2). Only about 190 of the 137,545 buildings cover four or more pixels, so
true per-building zonal statistics are not supported by the data, and adjacent
buildings share pixels. Coherence is therefore aggregated onto a grid aligned to
the reference raster, computed over built-up cells only (cells containing at
least one footprint) with area-weighted zonal statistics (`exactextract`). Each
building inherits the class of its cell for the map.

**Cell size: 50 m, chosen by sensitivity analysis.** The classification was run
at 30 m, 50 m and 100 m. The affected extent is stable across scales, but the
severe class is scale-dependent: at 100 m, total destruction is smaller than one
cell and gets averaged out, while at 30 m a single decorrelated pixel can flip a
cell. A 50 m cell holds 25 pixels, which keeps a stable mean and still resolves
the severity gradient.

| Epoch | 30 m | 50 m | 100 m |
| :--- | ---: | ---: | ---: |
| E2a | 20.5 / 0.7 | 17.0 / 0.2 | 8.8 / 0.1 |
| E2b | 63.7 / 8.1 | 67.1 / 4.1 | 74.8 / 0.4 |
| E3 | 63.9 / 3.0 | 67.6 / 1.2 | 72.8 / 0.0 |

*Affected % / severe % of built-up cells per epoch. Built-up cells: 30,005 (30 m),
13,152 (50 m), 3,925 (100 m).*

Cells outside the area of valid coherence are excluded rather than bridged.

---

## Pipeline

```
Sentinel-1 SLC (.SAFE.zip)
        |
        v
  preprocess.py        TOPSAR-Split (IW1, VV+VH) + Apply-Orbit-File  ->  BEAM-DIMAP
        |
        v
  run_insar.py         Back-Geocoding -> Interferogram + Coherence ->
                       TOPSAR-Deburst -> Goldstein filter -> Subset (AOI) ->
                       Terrain-Correction  ->  coherence GeoTIFF per pair
        |
        v
  check_quality.py     validate projection, bands and valid-pixel counts
        |
        v
  clean_buildings.py   quality-control the HOT OSM footprints (validity,
                       duplicates, micro slivers, tags, AOI) -> removal report
        |
        v
  classify_damage.py   shared coherence sampling + relative loss vs. E1 +
                       damage-class logic (imported by classify_grid)
        |
        v
  classify_grid.py     aggregate coherence onto the 50 m grid, classify cells,
                       run the cell-size sensitivity table, attribute the cell
                       class back to each building  ->  GeoPackage
        |
        v
  check_baseline.py            E1 reference stability + false-positive floor
  correct_baseline_drift.py    rainy-season correction from unbuilt reference
  validate_optical.py          Sentinel-2 dNBR cross-check (validation ceiling)
        |
        v
  viz_*.py             figures (damage overview, pre-conflict reference)
```

The InSAR stages (`preprocess.py`, `run_insar.py`) drive [ESA SNAP](https://step.esa.int/)
through its Python bridge (`esa_snappy`). The analysis and visualization stages
use the standard geospatial Python stack.

---

## Results

![Pre-conflict reference](assets/pre_conflict_reference.png)

*Pre-conflict reference (E1): InSAR coherence per building before the conflict.*

---

## Baseline robustness

Two checks separate genuine conflict damage from baseline and seasonal noise.

**Pre-conflict reference (E1) stability** (`check_baseline.py`). The damage signal
is the coherence drop relative to E1, so the reference itself has to be stable.
E1 spans two consecutive pre-conflict 12-day pairs; comparing them shows the
apparent loss of the intact city with no conflict at all. The two pairs
correlate at 0.76 with a 10.7 % median relative difference. The false-positive
floor that follows is informative:

| Threshold | Intact city flagged |
| :--- | ---: |
| >= 20 % loss (light) | 9.2 % of cells |
| >= 40 % loss (moderate) | 0.9 % of cells |
| >= 60 % loss (severe) | 0.0 % of cells |

The severe class is essentially free of baseline noise. The light class carries a
real floor near 9 %, so a single light cell means less than a clustered severe
one.

**Rainy-season drift correction** (`correct_baseline_drift.py`). The Sahel rains
begin in June and lower coherence over bare ground regardless of the conflict.
Estimated from stable unbuilt reference cells, the seasonal retention R_env is
0.99 in May (E2a), 0.66 in June (E2b) and 0.70 in July (E3), so roughly a third
of the June scene-wide coherence drop is seasonal rather than damage. Removing
that expectation from the built-up cells changes the picture sharply:

| Epoch | Raw affected | Drift-corrected |
| :--- | ---: | ---: |
| E2a | 17.0 % | 15.7 % |
| E2b | 67.1 % | 18.3 % |
| E3 | 67.6 % | 15.6 % |

Bare soil decorrelates more readily than the hard targets of a built environment,
so R_env is a strong, conservative estimate of the seasonal effect. Read the raw
figures as an upper bound and the corrected figures as a lower bound: the true
damage extent lies between them. Once the season is removed, the affected extent
is stable near 16 % of built-up cells across all three epochs, with June (E2b)
still the peak.

---

## Optical cross-validation

An independent check tests whether optical imagery confirms the SAR extent
(`validate_optical.py`). The reference is the change in the Normalised Burn Ratio
(dNBR) between two cloud-free, phenology-matched dry-season Sentinel-2 scenes a
year apart (Dec 2022 vs Nov 2023), streamed from the Earth Search STAC and
averaged onto the same 50 m grid.

The optical map does not reproduce the SAR damage pattern: the correlation
between coherence loss and dNBR is 0.03, and only about 3 % of built-up cells
cross the dNBR threshold, within the noise of the index.

![Optical cross-validation](assets/optical_validation.png)

This is a property of the fabric, not a refutation of the SAR. El Geneina is
built from mud brick, so a destroyed building collapses into rubble that is
spectrally almost identical to the surrounding bare soil; at 10 to 20 m
resolution, optical change detection has too little contrast to see it. SAR
coherence responds to the geometric disturbance regardless of spectral
signature, which is why it carries the signal where optical does not. The check
rules out the raw two-thirds figure as literal building destruction, consistent
with the corrected lower bound, but it cannot positively confirm that bound: a
definitive optical validation would need sub-metre imagery (UNOSAT or Maxar
damage points), not Sentinel-2. Confidence therefore rests on the internal
checks above. Full numbers: [docs/OPTICAL_VALIDATION.md](docs/OPTICAL_VALIDATION.md).

---

## Caveats

- **Coherence loss is a proxy.** It records physical surface change, not its
  cause. Conflict damage, construction, flooding and vegetation change all
  decorrelate the signal, so attribution to shelling or arson needs
  high-resolution optical cross-validation. A Sentinel-2 dNBR check could not
  confirm the extent (see Optical cross-validation): mud-brick rubble is
  spectrally close to bare soil, so this needs sub-metre imagery.
- **Rainy-season decorrelation.** The Sahel rains begin in June, which lowers
  coherence over bare and vegetated ground independently of the conflict. This
  inflates the E2b and E3 affected figures, so those epochs read as an upper
  bound. The drift correction above brackets the effect with a lower bound from
  stable unbuilt reference areas.
- **12-day revisit.** Sub-epoch timing of individual events cannot be resolved.
- **Sub-pixel footprints.** The grid is the honest reporting unit, but the
  underlying resolution still cannot characterise an isolated 15 m2 structure on
  its own.

**Future work.** Beyond the rainy-season correction, the natural extensions are
an ascending-orbit track to reduce layover ambiguity, an uncertainty layer from
intra-epoch coherence variance, and a deep-learning segmentation step (for
example a U-Net on Sentinel-1) to suppress environmental false positives. The
deep-learning direction is planned as a separate project rather than part of this
pipeline.

---

## Repository layout

```
config.py               Single source of truth: paths, AOI, epochs, pairs, parameters, styling
snap.py                 ESA SNAP / esa_snappy bridge wrapper

preprocess.py           Stage 1: TOPSAR-Split + Apply-Orbit-File (+ subswath/burst helpers)
run_insar.py            Stage 2: coherence GeoTIFF per pair
check_quality.py        GeoTIFF quality check
clean_buildings.py      Stage 0: HOT OSM footprint quality control + removal report
classify_damage.py      Stage 3: shared coherence-sampling + damage-class logic
classify_grid.py        Stage 3b: 50 m grid classification + sensitivity table
check_baseline.py       Stage 3c: E1 reference stability + false-positive floor
correct_baseline_drift.py  Stage 3c: rainy-season drift correction (unbuilt ref)
validate_optical.py     Stage 3d: Sentinel-2 dNBR cross-validation (streamed COGs)

viz_common.py           Shared loading/clipping helpers for figures
viz_damage_overview.py  Three-panel damage overview
viz_supplementary.py    Pre-conflict reference figure

data/aoi/               Area-of-interest definition (GeoJSON, version-controlled)
docs/DATA.md            How to obtain the Sentinel-1 scenes and building footprints
assets/                 Rendered showcase figures
tests/                  Pytest smoke tests (config, scene catalog, damage logic)
.github/workflows/      Continuous integration (runs the tests on every push)
```

The large raw and intermediate data (Sentinel-1 scenes, processing
intermediates, building footprints) is **not** version-controlled. It is
reproducible from public sources, documented in [docs/DATA.md](docs/DATA.md).

---

## Setup & workflow

The analysis/visualization stages and the SNAP-based InSAR stages have different
requirements. A conda environment is recommended, since GDAL and the SNAP/Java
bridge are awkward to install from PyPI.

```bash
# Recommended: conda environment for analysis and visualization
conda env create -f environment.yml
conda activate insar
```

```bash
# Alternative: plain pip for the analysis/visualization stages
pip install -r requirements.txt
```

The SNAP-based InSAR pipeline (`preprocess.py`, `run_insar.py`) needs ESA SNAP
and its `esa_snappy` bridge installed separately. See
[docs/DATA.md](docs/DATA.md) and `requirements-pipeline.txt`.

By default the scripts read and write data under `./data` (git-ignored). To use
a different location, point `SAR_DATA_DIR` at it:

```bash
# Windows (PowerShell)
$env:SAR_DATA_DIR = "E:\sar-data"
# Linux / macOS
export SAR_DATA_DIR=/data/sar
```

Then run the stages in order:

```bash
python preprocess.py        # TOPSAR-Split + orbit (needs SNAP + the .SAFE scenes)
python run_insar.py         # coherence GeoTIFFs (slow: ~20-40 min per pair)
python check_quality.py     # validate outputs
python clean_buildings.py   # footprint quality control + removal report
python classify_grid.py     # 50 m grid classification + sensitivity table
python validate_optical.py  # Sentinel-2 dNBR cross-check (needs internet)
python check_baseline.py        # E1 reference stability + false-positive floor
python correct_baseline_drift.py  # rainy-season drift correction

python viz_damage_overview.py
python viz_supplementary.py
```

## Tests

A small `pytest` suite covers the configuration, scene catalog and damage
classification logic. It runs without the large data and is executed on every
push by GitHub Actions (see `.github/workflows/ci.yml`).

```bash
pip install -r requirements-dev.txt
pytest -q
```

---

## Tech Stack

Python 3.11, ESA SNAP (esa_snappy), GDAL, rasterio, geopandas, shapely, pyproj, numpy, pandas, matplotlib, tqdm, pytest

---

## Data sources & attribution

- **Sentinel-1A SLC:** Copernicus / ESA, retrieved from the
  [Copernicus Data Space Ecosystem](https://dataspace.copernicus.eu/).
  Contains modified Copernicus Sentinel data (2023). Output CRS EPSG:32634 (UTM zone 34N).
- **Building footprints:** [Humanitarian OpenStreetMap Team (HOT)](https://www.hotosm.org/)
  and OpenStreetMap contributors, licensed under
  [ODbL](https://opendatacommons.org/licenses/odbl/).

## References

1. Human Rights Watch (2024). *"The Massalit Will Not Come Home."*
2. Yale Humanitarian Research Lab (2023). *Monitoring of Conflict-Related Damage in Sudan.*
3. UN OCHA (2024). *Sudan Humanitarian Update.*

## License

Code is under the [MIT License](LICENSE); data products follow their source licenses (above).

## Disclaimer

This is a remote-sensing analysis. Coherence loss is a proxy for physical
surface change and does not by itself confirm the cause or extent of damage to
any individual structure. Results are intended for research and situational
awareness, not as legal or forensic evidence.
