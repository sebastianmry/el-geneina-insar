"""Thin wrapper around the ESA SNAP Python bridge (esa_snappy / jpy).

Importing SNAP is expensive and only required for the processing pipeline
(preprocess.py, run_insar.py). The analysis and visualization scripts do not
need it. This module centralizes the import and the GDAL/PROJ environment setup
so the pipeline modules stay clean.

SNAP must be installed and the Python bindings configured separately; see
docs/DATA.md and requirements-pipeline.txt.
"""

from __future__ import annotations

import config

# GDAL/PROJ must be configured before SNAP / GDAL are used.
config.configure_gdal_proj_env()

from esa_snappy import (  # noqa: E402  (import after env setup, intentional)
    GPF,
    GeoPos,
    HashMap,
    PixelPos,
    ProductIO,
)
import jpy  # noqa: E402

# Frequently used Java types.
Integer = jpy.get_type("java.lang.Integer")
JavaSystem = jpy.get_type("java.lang.System")
ProductArray = "org.esa.snap.core.datamodel.Product"

__all__ = [
    "GPF",
    "GeoPos",
    "HashMap",
    "PixelPos",
    "ProductIO",
    "jpy",
    "Integer",
    "JavaSystem",
    "ProductArray",
]
