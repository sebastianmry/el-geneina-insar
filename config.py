"""Central configuration for the El Geneina InSAR Coherence Change Detection project.

Single source of truth for paths, the area of interest (AOI), processing
parameters, epoch definitions, coherence pairs and shared visualization styling.
No values are hardcoded in the individual scripts - everything is imported from here.

Data location
-------------
The large raw and intermediate data does not live in this repository (see
docs/DATA.md). Point the environment variable ``SAR_DATA_DIR`` at the local
data root, for example:

    Windows (PowerShell):  $env:SAR_DATA_DIR = "D:\\SAR"
    Linux / macOS:         export SAR_DATA_DIR=/data/sar

If the variable is unset, ``./data`` inside the repository is used as a fallback.
"""

from __future__ import annotations

import json
import os
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np

# -----------------------------------------------------------------------------
# Paths
# -----------------------------------------------------------------------------
REPO_DIR = Path(__file__).resolve().parent

DATA_ROOT = Path(os.environ.get("SAR_DATA_DIR", REPO_DIR / "data")).resolve()

SAFE_DIR = DATA_ROOT / "safe"
BUILDINGS_DIR = DATA_ROOT / "buildings"
PROCESSED_DIR = DATA_ROOT / "processed"

SPLIT_DIR = PROCESSED_DIR / "split"
COREG_DIR = PROCESSED_DIR / "coregistered"
COH_DIR = PROCESSED_DIR / "coherence"
GEOCODED_DIR = PROCESSED_DIR / "geocoded"
RESULTS_DIR = PROCESSED_DIR / "results"

# AOI definition is small and version-controlled inside the repository.
AOI_PATH = REPO_DIR / "data" / "aoi" / "al-geneina_S1_SLC_AOI.geojson"

# Rendered figures and showcase assets.
VISUAL_DIR = DATA_ROOT / "visual"
ASSETS_DIR = REPO_DIR / "assets"

# Key data products.
BUILDINGS_FILE = BUILDINGS_DIR / "hotosm_el_geneina.gpkg"
# Quality-controlled footprints written by clean_buildings.py. The pipeline
# prefers this file when present and falls back to the raw download otherwise.
BUILDINGS_CLEAN_FILE = BUILDINGS_DIR / "hotosm_el_geneina_clean.gpkg"
DAMAGE_BUILDINGS_FILE = RESULTS_DIR / "damage_buildings.gpkg"

# Markdown removal report from the cleaning stage (open-science transparency).
CLEANING_REPORT_PATH = REPO_DIR / "docs" / "CLEANING_REPORT.md"


def ensure_processing_dirs() -> None:
    """Create the intermediate and output directories if they do not exist."""
    for directory in (
        SPLIT_DIR, COREG_DIR, COH_DIR, INTENSITY_DIR, GEOCODED_DIR, RESULTS_DIR
    ):
        directory.mkdir(parents=True, exist_ok=True)


def configure_gdal_proj_env() -> None:
    """Point GDAL/PROJ at the active conda environment's data directories.

    Avoids hardcoded, user-specific paths: the locations are derived from the
    interpreter prefix at runtime. Only sets a variable if it is not already
    set and the corresponding directory exists.
    """
    share = Path(sys.prefix) / "Library" / "share"  # conda layout on Windows
    candidates = {
        "GDAL_DATA": share / "gdal",
        "PROJ_LIB": share / "proj",
        "PROJ_DATA": share / "proj",
    }
    for variable, path in candidates.items():
        if variable not in os.environ and path.exists():
            os.environ[variable] = str(path)


# -----------------------------------------------------------------------------
# Sentinel-1 SLC scenes
# -----------------------------------------------------------------------------
# Acquisition date (YYYYMMDD) -> .SAFE.zip filename. Files are not committed;
# download them into SAFE_DIR following docs/DATA.md.
SAFE_FILENAMES: dict[str, str] = {
    "20230319": "S1A_IW_SLC__1SDV_20230319T042215_20230319T042245_047708_05BB16_385B.SAFE.zip",
    "20230331": "S1A_IW_SLC__1SDV_20230331T042216_20230331T042246_047883_05C0F0_184D.SAFE.zip",
    "20230412": "S1A_IW_SLC__1SDV_20230412T042216_20230412T042246_048058_05C6E4_3917.SAFE.zip",
    "20230424": "S1A_IW_SLC__1SDV_20230424T042216_20230424T042246_048233_05CCBC_4330.SAFE.zip",
    "20230506": "S1A_IW_SLC__1SDV_20230506T042217_20230506T042247_048408_05D29C_4D60.SAFE.zip",
    "20230611": "S1A_IW_SLC__1SDV_20230611T042219_20230611T042249_048933_05E265_AFCA.SAFE.zip",
    "20230623": "S1A_IW_SLC__1SDV_20230623T042219_20230623T042249_049108_05E7B9_5D20.SAFE.zip",
    "20230705": "S1A_IW_SLC__1SDV_20230705T042220_20230705T042250_049283_05ED1A_9FC7.SAFE.zip",
    "20230717": "S1A_IW_SLC__1SDV_20230717T042221_20230717T042251_049458_05F27B_E795.SAFE.zip",
    "20230729": "S1A_IW_SLC__1SDV_20230729T042222_20230729T042252_049633_05F7E6_2BDD.SAFE.zip",
}


def safe_path(date: str) -> Path:
    """Return the absolute path to the .SAFE.zip for a given acquisition date."""
    return SAFE_DIR / SAFE_FILENAMES[date]


# -----------------------------------------------------------------------------
# Epochs and coherence pairs
# -----------------------------------------------------------------------------
# Epoch 1: pre-conflict reference (city intact)
EPOCH_1_DATES = ["20230319", "20230331", "20230412"]
# Epoch 2a: first strike (first weeks after conflict onset on 15 Apr)
EPOCH_2A_DATES = ["20230424", "20230506"]
# Epoch 2b: peak destruction (around the 14-22 Jun massacre)
EPOCH_2B_DATES = ["20230611", "20230623"]
# Epoch 3: post-conflict (city under RSF control, signal stabilized)
EPOCH_3_DATES = ["20230705", "20230717", "20230729"]

ALL_DATES = EPOCH_1_DATES + EPOCH_2A_DATES + EPOCH_2B_DATES + EPOCH_3_DATES

EPOCH_DESCRIPTIONS: dict[str, str] = {
    "Epoch_1": "Pre-conflict / reference (Mar-Apr 2023)",
    "Epoch_2a": "First strike (Apr-May 2023)",
    "Epoch_2b": "Peak destruction (Jun 2023, around the 14-22 Jun massacre)",
    "Epoch_3": "Post-conflict (Jul 2023, after RSF took control)",
}

# Coherence pairs - format: (reference_date, secondary_date, label)
COH_PAIRS: list[tuple[str, str, str]] = [
    # Epoch 1 internal - reference coherence (stable city)
    ("20230319", "20230331", "E1_coh_0319_0331"),
    ("20230331", "20230412", "E1_coh_0331_0412"),
    # Epoch 2a - first strike
    ("20230424", "20230506", "E2a_coh_0424_0506"),
    # Epoch 2b - peak destruction
    ("20230611", "20230623", "E2b_coh_0611_0623"),
    # Epoch 3 internal - stabilized post-conflict state
    ("20230705", "20230717", "E3_coh_0705_0717"),
    ("20230717", "20230729", "E3_coh_0717_0729"),
]

# GeoTIFF basenames grouped per epoch, used by damage classification / plots.
EPOCH_COH_TIFS: dict[str, list[str]] = {
    "E1": ["E1_coh_0319_0331.tif", "E1_coh_0331_0412.tif"],
    "E2a": ["E2a_coh_0424_0506.tif"],
    "E2b": ["E2b_coh_0611_0623.tif"],
    "E3": ["E3_coh_0705_0717.tif", "E3_coh_0717_0729.tif"],
}

# Epochs evaluated for damage relative to the E1 reference.
DAMAGE_EPOCHS = ["E2a", "E2b", "E3"]

REFERENCE_COH_TIF = COH_DIR / "E1_coh_0319_0331.tif"

# -----------------------------------------------------------------------------
# SLC / InSAR processing parameters
# -----------------------------------------------------------------------------
SUBSWATH = "IW1"          # El Geneina lies in IW1 (confirmed by find_subswath)
POLARISATIONS = "VV,VH"

# Polarisations carried through to the coherence estimate. VV is the primary
# co-pol channel; VH (cross-pol) is processed as a second channel for dual-pol
# fusion in the damage classification (mean of the per-polarisation relative
# coherence loss). The list is parsed from POLARISATIONS so the split and the
# coherence stages stay consistent, and the first entry is the primary channel.
COH_POLARISATIONS = [pol.strip() for pol in POLARISATIONS.split(",")]


def coh_tif_name(label: str, polarisation: str) -> str:
    """GeoTIFF name for a coherence pair in a given polarisation.

    The primary channel (VV) keeps the bare label for backward compatibility
    with the original VV-only products, so those rasters are not reprocessed.
    The cross-pol channel carries a polarisation suffix.
    """
    if polarisation == COH_POLARISATIONS[0]:
        return f"{label}.tif"
    return f"{label}_{polarisation}.tif"


def epoch_coh_tif_names(epoch: str, polarisation: str) -> list[str]:
    """Coherence GeoTIFF names for an epoch in a given polarisation.

    EPOCH_COH_TIFS holds the primary-channel (VV) names; this maps them to the
    requested polarisation via coh_tif_name so the damage classification can read
    each polarisation separately for the dual-pol fusion.
    """
    return [coh_tif_name(name[:-4], polarisation) for name in EPOCH_COH_TIFS[epoch]]


# Calibrated backscatter (sigma0) is written as a second, incoherent change
# channel (run_intensity.py). Each scene produces one GeoTIFF with the
# polarisations as bands, in COH_POLARISATIONS order (band 1 = VV, band 2 = VH).
INTENSITY_DIR = PROCESSED_DIR / "intensity"


def intensity_tif_name(date: str) -> str:
    """GeoTIFF name for a calibrated, terrain-corrected sigma0 scene."""
    return f"intensity_{date}.tif"


# Scenes averaged per epoch for the intensity log-ratio (mirrors EPOCH_COH_TIFS
# for the coherence channel). E1 is the pre-conflict reference.
EPOCH_INTENSITY_DATES: dict[str, list[str]] = {
    "E1": EPOCH_1_DATES,
    "E2a": EPOCH_2A_DATES,
    "E2b": EPOCH_2B_DATES,
    "E3": EPOCH_3_DATES,
}

# Intensity false-positive filter (classify_intensity.py). A coherence-flagged
# cell is kept only when its backscatter also changed beyond what unbuilt
# reference cells show: the per-epoch threshold is INTENSITY_CHANGE_SIGMA robust
# standard deviations (1.4826 * MAD) of the log-ratio over unbuilt cells. Because
# the noise is calibrated on unbuilt ground, ordinary seasonal backscatter
# variation is absorbed into the threshold; built-up cells exceeding it carry a
# structural change, which the rain-robust intensity channel sees but seasonal
# decorrelation does not. The change is unsigned (collapse can raise or lower
# backscatter), so the filter tests the magnitude of the log-ratio.
INTENSITY_CHANGE_SIGMA = 2.0

# Intensity values at or below this (linear sigma0) are treated as no-data.
INTENSITY_VALID_MIN = 1e-6

INTENSITY_FILTERED_FILE = RESULTS_DIR / "damage_grid_50m_intensity_filtered.gpkg"
INTENSITY_FIGURE = ASSETS_DIR / "intensity_filter.png"

# Cache of the full grid (built-up and unbuilt cells) with the intensity and
# corrected-coherence columns. The zonal extraction over all scenes is the slow
# step, so it is cached here and the figure can be re-rendered from it in seconds
# (python classify_intensity.py figure).
INTENSITY_GRID_CACHE = RESULTS_DIR / "intensity_grid_cache.pkl"


ORBIT_DIRECTION = "DESCENDING"
NUM_BURSTS = 9            # IW always has 9 bursts per subswath
COH_WIN_RANGE = 10        # coherence window, range (pixels)
COH_WIN_AZIMUTH = 3       # coherence window, azimuth (pixels)
PIXEL_SPACING_M = 10.0    # terrain-correction output resolution (meters)
DEM_NAME = "SRTM 3Sec"
OUTPUT_CRS = "EPSG:32634"  # UTM zone 34N - correct for ~22.4 E

# City center of El Geneina, used to locate the covering subswath.
TARGET_LON = 22.4473
TARGET_LAT = 13.4527

# -----------------------------------------------------------------------------
# Damage classification thresholds (relative coherence loss vs. E1)
# -----------------------------------------------------------------------------
DAMAGE_THRESHOLDS = {
    1: 0.20,  # light
    2: 0.40,  # moderate
    3: 0.60,  # severe
}

# Zonal sampling: coherence is averaged over all raster pixels touching a
# building footprint (not read at the centroid). A building needs at least this
# many valid pixels in both the reference and the compared epoch to be
# classified; below that it is flagged as insufficient coverage and excluded
# from the damage statistics.
MIN_BUILDING_PIXELS = 4

# Damage class assigned to buildings with insufficient coherence coverage. It is
# kept out of the affected / severe percentages (see viz_common.damage_percentages).
DAMAGE_NODATA = -1

# Coherence values at or below this are treated as no-data (rasters store 0, not NaN).
COH_VALID_MIN = 0.001

# -----------------------------------------------------------------------------
# Footprint quality control (clean_buildings.py)
# -----------------------------------------------------------------------------
# The HOT OSM download is screened before any statistics are computed. The
# thresholds below are deliberately conservative: only geometries that cannot
# represent a real standing building are removed, so the cleaning does not bias
# the damage percentages. Every removed feature is counted by category in the
# cleaning report (config.CLEANING_REPORT_PATH).

# Footprints below this area are smaller than any habitable structure and are
# treated as digitizing artefacts (square meters, measured in OUTPUT_CRS).
MIN_BUILDING_AREA_M2 = 1.0

# Polsby-Popper compactness (4*pi*area / perimeter^2; 1.0 = circle). Footprints
# below this are line-like slivers, typically a traced wall rather than a
# building outline.
MIN_BUILDING_COMPACTNESS = 0.05

# OSM building tag values excluded from the damage analysis. "construction"
# marks a site that was not yet a standing building during the study window, so
# it cannot show conflict-driven coherence loss.
EXCLUDED_BUILDING_TAGS = {"construction"}

# -----------------------------------------------------------------------------
# Resolution-matched analysis grid
# -----------------------------------------------------------------------------
# HOT OSM footprints in El Geneina have a median area of ~15 m2, far below the
# 100 m2 of a single 10 m Sentinel-1 pixel, so per-building coherence is
# effectively a sub-pixel sample. The defensible statistical unit is a grid
# whose cells each contain several independent coherence estimates.
#
# The coherence is itself estimated over a 10 x 3 pixel window (COH_WIN_RANGE,
# COH_WIN_AZIMUTH), so neighbouring 10 m pixels are spatially correlated; a cell
# must span several window footprints to average independent looks.
#
# The cell size is chosen from the sensitivity analysis (GRID_CELL_SIZES_M): the
# affected extent is stable across 30-100 m, but the severe class is smeared out
# at 100 m because total destruction is a sub-cell phenomenon. A 50 m cell
# (5 x 5 = 25 pixels) keeps a stable mean while preserving the severity gradient,
# and stays comparable to Sentinel-1 coherence damage-density products (UNOSAT).
GRID_CELL_SIZE_M = 50.0

# Cell sizes for the sensitivity analysis (report how stable the headline
# percentages are against the chosen resolution).
GRID_CELL_SIZES_M = [30.0, 50.0, 100.0]

# A grid cell is classified only if at least this fraction of its pixels carry
# valid coherence (in both the reference and the compared epoch).
GRID_MIN_VALID_FRACTION = 0.25


def grid_min_pixels(cell_size_m: float) -> float:
    """Minimum valid pixel count for a grid cell of the given size."""
    pixels_per_cell = (cell_size_m / PIXEL_SPACING_M) ** 2
    return GRID_MIN_VALID_FRACTION * pixels_per_cell


# Grid output GeoPackages (per cell size).
def grid_damage_file(cell_size_m: float) -> Path:
    """Path to the classified grid GeoPackage for a given cell size."""
    return RESULTS_DIR / f"damage_grid_{int(cell_size_m)}m.gpkg"


# Building footprints with the damage class inherited from their grid cell.
DAMAGE_BUILDINGS_GRID_FILE = RESULTS_DIR / "damage_buildings_from_grid.gpkg"


def grid_drift_file(cell_size_m: float) -> Path:
    """Path to the rainy-season drift-corrected grid GeoPackage for a cell size."""
    return RESULTS_DIR / f"damage_grid_{int(cell_size_m)}m_driftcorrected.gpkg"

# -----------------------------------------------------------------------------
# Optical (Sentinel-2) cross-validation
# -----------------------------------------------------------------------------
# The SAR damage bracket is wide for the rainy-season epochs (E2b, E3) because
# the drift correction, estimated from bare ground, over-corrects the hard
# targets of a built environment. An independent optical destruction map
# constrains where the truth sits inside that bracket.
#
# Structural destruction (burn scars, collapsed roofs, rubble) persists for
# months, so the validation uses cloud-free dry-season scenes: one before the
# conflict and one after the peak. This sidesteps the rainy-season cloud cover
# that motivated the SAR approach in the first place.
#
# The two scenes are matched to the same season (both December). A dry-season
# pre scene against a post-rain post scene would confound the burn signal with
# vegetation phenology: late-October ground is greener than dry-season ground,
# which drives dNBR negative everywhere and masks the destruction. Comparing two
# December scenes a year apart, bracketing the conflict, removes that confound.
STAC_ENDPOINT = "https://earth-search.aws.element84.com/v1"
STAC_COLLECTION = "sentinel-2-l2a"
S2_MAX_CLOUD_COVER = 10.0  # percent, scene-level pre-filter

# Cloud-free, phenology-matched dry-season windows bracketing the conflict.
S2_PRE_WINDOW = ("2022-11-15", "2022-12-31")   # dry season, before the conflict
S2_POST_WINDOW = ("2023-11-15", "2023-12-31")  # dry season, after the peak

# dNBR = NBR_pre - NBR_post. Positive values mark loss of vegetation and intact
# structure (burning, rubble). Cells at or above this are counted as optically
# destroyed in the agreement statistics.
DNBR_DESTRUCTION_THRESHOLD = 0.10

# The SAR epoch validated against the optical reference. E2b is the peak and
# carries the disputed 18-67 % bracket.
OPTICAL_VALIDATION_EPOCH = "E2b"

# Sentinel-2 Scene Classification (SCL) values kept as valid land surface.
# Excluded: 0 nodata, 1 saturated, 3 cloud shadow, 6 water, 8/9 cloud, 10
# cirrus, 11 snow.
S2_SCL_VALID = (4, 5, 7)  # vegetation, bare soil, unclassified

OPTICAL_DNBR_FILE = RESULTS_DIR / "optical_dnbr_50m.gpkg"
OPTICAL_VALIDATION_REPORT = REPO_DIR / "docs" / "OPTICAL_VALIDATION.md"
OPTICAL_VALIDATION_FIGURE = ASSETS_DIR / "optical_validation.png"

# -----------------------------------------------------------------------------
# Dual-polarisation (VV/VH) diagnostic
# -----------------------------------------------------------------------------
# compare_polarisations.py characterises the cross-pol channel against the
# co-pol channel: how correlated VV and VH coherence are (whether VH adds
# independent information) and how differently each decorrelates in the rainy
# season (the per-polarisation environmental retention R_env).
POLARISATION_DIAGNOSTIC_FIGURE = ASSETS_DIR / "polarisation_diagnostic.png"

# -----------------------------------------------------------------------------
# Damage confidence / uncertainty layer (uncertainty.py)
# -----------------------------------------------------------------------------
# Each cell's drift-corrected coherence drop is divided by its standard error,
# estimated from the within-cell spatial spread of coherence, to give a per-cell
# signal-to-noise z-score: how strong the damage signal is relative to the local
# coherence variability. Pixels within a cell are spatially correlated, so this
# reads as a relative confidence, not a strict p-value. The fixed-threshold
# classification is unchanged; this layer flags how trustworthy each call is.
Z_CONFIDENT = 1.645        # one-sided ~p < 0.05, "confident"
Z_HIGH_CONFIDENCE = 2.33   # one-sided ~p < 0.01, "high confidence"
COLORMAP_CONFIDENCE = "viridis"
UNCERTAINTY_FIGURE = ASSETS_DIR / "damage_confidence.png"

# -----------------------------------------------------------------------------
# Area of interest
# -----------------------------------------------------------------------------
@lru_cache(maxsize=1)
def load_aoi_bounds() -> dict[str, float]:
    """Return the AOI bounding box as {west, east, south, north} in EPSG:4326."""
    with open(AOI_PATH, "r", encoding="utf-8") as aoi_file:
        aoi_geojson = json.load(aoi_file)

    ring = aoi_geojson["features"][0]["geometry"]["coordinates"][0]
    lons = [point[0] for point in ring]
    lats = [point[1] for point in ring]
    return {
        "west": min(lons),
        "east": max(lons),
        "south": min(lats),
        "north": max(lats),
    }


def aoi_wkt() -> str:
    """Return the AOI as a closed POLYGON WKT string (for SNAP Subset)."""
    bounds = load_aoi_bounds()
    west, east = bounds["west"], bounds["east"]
    south, north = bounds["south"], bounds["north"]
    return (
        "POLYGON(("
        f"{west} {south}, {east} {south}, {east} {north}, "
        f"{west} {north}, {west} {south}))"
    )


def aoi_size_km() -> tuple[float, float]:
    """Return the approximate AOI size as (width_km, height_km)."""
    bounds = load_aoi_bounds()
    mid_lat = (bounds["north"] + bounds["south"]) / 2.0
    width_km = (bounds["east"] - bounds["west"]) * 111.0 * np.cos(np.radians(mid_lat))
    height_km = (bounds["north"] - bounds["south"]) * 111.0
    return width_km, height_km


# -----------------------------------------------------------------------------
# Shared visualization styling
# -----------------------------------------------------------------------------
# Dark theme: near-black background with luminous footprints, echoing the
# multitemporal SAR look of ICEYE / Sentinel-1 city composites. Every figure
# references these names so the palette stays a single source of truth.
COLOR_BG = "#0d0d1a"       # figure and axes background
COLOR_FG = "#e8e8f0"       # primary text and map furniture
COLOR_SUB = "#b0b0cc"      # subtitles, captions, metadata
COLOR_PANEL = "#1a1a30"    # legend and inset box fill
COLOR_LINE = "#3a3a5c"     # axes spines and dividers

# Polarisation channels in the dual-pol diagnostic figure. Teal and lavender
# both read on the dark backdrop and stay clear of the warm damage ramp.
COLOR_VV = "#2d4ea8"       # primary co-pol channel (dark blue, matched to magenta)
COLOR_VH = "#b04a9e"       # cross-pol channel (magenta-violet)

# Damage class styling: 0 = none, 1 = light, 2 = moderate, 3 = severe.
# The no-damage class is a muted grey so it recedes on the dark backdrop, while
# the affected classes glow in a warm sequential ramp (yellow to red). Footprint
# outlines are drawn thick enough to read the building shapes on the map.
DAMAGE_FILL = {0: "#8a8a9a", 1: "#f5c518", 2: "#e07b39", 3: "#d62728"}
DAMAGE_EDGE = {0: "#6a6a7a", 1: "#c8a000", 2: "#b05a10", 3: "#a00000"}
DAMAGE_LINEWIDTH = {0: 0.15, 1: 0.50, 2: 0.60, 3: 0.75}
DAMAGE_ALPHA = {0: 0.70, 1: 0.97, 2: 0.97, 3: 1.00}

DAMAGE_CLASS_LABELS = {
    0: "No damage",
    1: "Light  (20-40 %)",
    2: "Moderate  (40-60 %)",
    3: "Severe  (>60 %)",
}

# Plot extent for the El Geneina city overview (EPSG:32634, meters).
PLOT_XLIM = (652107, 660248)
PLOT_YLIM = (1483467, 1491810)
