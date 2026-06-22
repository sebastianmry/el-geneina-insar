# Data acquisition

The large data is not version-controlled. This document explains how to obtain
it and where to put it so the scripts find it.

## Data root

By default the scripts use `./data` inside the repository (see `config.py`).
Because this data is large (the raw scenes alone are ~80 GB), you can place it on
another drive and point `SAR_DATA_DIR` there instead:

```bash
# Windows (PowerShell)
$env:SAR_DATA_DIR = "E:\sar-data"
# Linux / macOS
export SAR_DATA_DIR=/data/sar
```

Expected layout under the data root (`./data` or `$SAR_DATA_DIR`):

```
<data root>/
├── aoi/           area-of-interest GeoJSON (shipped in the repo)
├── safe/          Sentinel-1 SLC scenes (.SAFE.zip)        -- download below
├── buildings/     HOT OSM building footprints (.gpkg)      -- download below
│                   (clean_buildings.py adds hotosm_el_geneina_clean.gpkg)
└── processed/     pipeline output (created automatically)
    ├── split/         BEAM-DIMAP from preprocess.py
    ├── coherence/     coherence GeoTIFFs from run_insar.py
    ├── geocoded/
    └── results/       damage_grid_{30,50,100}m.gpkg, damage_buildings_from_grid.gpkg
```

## 1. Sentinel-1A SLC scenes

Source: [Copernicus Data Space Ecosystem](https://dataspace.copernicus.eu/)
(free account). Product: **Sentinel-1A, IW, SLC, VV+VH, DESCENDING**.

The scenes were selected in the [Copernicus Browser](https://browser.dataspace.copernicus.eu/)
by uploading the project AOI (`data/aoi/al-geneina_S1_SLC_AOI.geojson`) as the
search area and filtering for Sentinel-1 IW SLC on a descending orbit. Download
the following 10 scenes into the data root's `safe/` folder:

| Date | Scene |
| :--- | :--- |
| 2023-03-19 | `S1A_IW_SLC__1SDV_20230319T042215_20230319T042245_047708_05BB16_385B` |
| 2023-03-31 | `S1A_IW_SLC__1SDV_20230331T042216_20230331T042246_047883_05C0F0_184D` |
| 2023-04-12 | `S1A_IW_SLC__1SDV_20230412T042216_20230412T042246_048058_05C6E4_3917` |
| 2023-04-24 | `S1A_IW_SLC__1SDV_20230424T042216_20230424T042246_048233_05CCBC_4330` |
| 2023-05-06 | `S1A_IW_SLC__1SDV_20230506T042217_20230506T042247_048408_05D29C_4D60` |
| 2023-06-11 | `S1A_IW_SLC__1SDV_20230611T042219_20230611T042249_048933_05E265_AFCA` |
| 2023-06-23 | `S1A_IW_SLC__1SDV_20230623T042219_20230623T042249_049108_05E7B9_5D20` |
| 2023-07-05 | `S1A_IW_SLC__1SDV_20230705T042220_20230705T042250_049283_05ED1A_9FC7` |
| 2023-07-17 | `S1A_IW_SLC__1SDV_20230717T042221_20230717T042251_049458_05F27B_E795` |
| 2023-07-29 | `S1A_IW_SLC__1SDV_20230729T042222_20230729T042252_049633_05F7E6_2BDD` |

Keep them as `.SAFE.zip`. SNAP reads the zip archives directly, and the
filenames must match `config.SAFE_FILENAMES`.

Reference geometry: the pipeline reprojects all products to EPSG:32634 (UTM zone
34N) during terrain correction and uses the SRTM 3Sec DEM, which SNAP downloads
automatically on first use.

## 2. Building footprints

Source: [HOT Export Tool](https://export.hotosm.org/) / OpenStreetMap, building
polygons for the El Geneina area, licensed under
[ODbL](https://opendatacommons.org/licenses/odbl/).

Save as a GeoPackage at the path referenced by `config.BUILDINGS_FILE`:

```
$SAR_DATA_DIR/buildings/hotosm_el_geneina.gpkg
```

## 3. ESA SNAP (for the InSAR pipeline)

`preprocess.py` and `run_insar.py` require [ESA SNAP](https://step.esa.int/main/download/snap-download/)
and its Python bridge `esa_snappy`.

1. Install SNAP (includes the Sentinel-1 Toolbox).
2. Configure the Python bindings against your environment, e.g.:
   ```
   <snap-install>/bin/snappy-conf <path-to-python>
   ```
   See the [SNAP-Python documentation](https://senbox.atlassian.net/wiki/spaces/SNAP/pages/19300362/How+to+use+the+SNAP+API+from+Python).
3. Precise orbit files and the SRTM 3Sec DEM are downloaded automatically by
   SNAP on first use (internet connection required).
