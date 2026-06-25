"""Zentrale Farbpalette für die El-Geneina-InSAR-Figuren.

Single Source of Truth für alle Farben in Karten und Diagnose-Plots. Die
wissenschaftlichen Rampen stammen aus den Crameri Scientific Colour Maps
(perzeptuell uniform, CVD-sicher, graustufentauglich; Crameri et al., 2020).
Die kategorialen Akzente sind thematische Erdtöne und harmonieren mit dem
dunklen SAR-GeoTIFF-Look der Karten.

Verwendung:
    from palette import CRAMERI_MAPS, DAMAGE_CLASSES, damage_color_scale

    ax.imshow(coherence_array, cmap=CRAMERI_MAPS["coherence"], vmin=0, vmax=1)
    color = alt.Color("klasse:N", scale=damage_color_scale())
"""

from __future__ import annotations

# --- Wissenschaftliche Rampen (Crameri) -----------------------------------
# Namen der cmcrameri-Colormaps je nach Datenstruktur. Import erst zur
# Laufzeit, damit das Modul auch ohne cmcrameri (reine Hex-Nutzung) lädt.
CRAMERI_MAP_NAMES: dict[str, str] = {
    "coherence": "batlow",   # 0..1, sequenziell (Kohärenz, Kohärenzverlust)
    "deformation": "vik",    # +/-, divergierend mit neutraler Mitte
    "phase": "romaO",        # -pi..+pi, zyklisch (wrapped Interferogramm)
}

# --- Kategoriale Schadensklassen (thematische Erdtöne) --------------------
# Reihenfolge entspricht der Klassenlogik stable -> destroyed plus Maske.
# Schlüssel englisch, da Plot-Beschriftungen englisch sind.
DAMAGE_CLASSES: dict[str, str] = {
    "stable": "#0f6e56",      # Teal, hohe Kohärenz, intakt
    "partial": "#c9a14c",     # Sand, Übergangsbereich
    "destroyed": "#b5472f",   # Terracotta, Kohärenzverlust (Lehmziegel-Bezug)
    "nodata": "#5b6168",      # Neutralgrau, Maske / Regenzeit-NoData
}

# Zielordner für die gerenderten Figuren (Repo-Assets).
from pathlib import Path as _Path

ASSETS_DIR = _Path(r"D:\projects\el-geneina-insar\assets")

# Neutrale Stützfarben für Gitter, Achsen und Text auf dunklem Grund.
NEUTRAL_GRID = "#3a4047"
NEUTRAL_TEXT = "#8b949e"

# --- Helles Plot-Theme (Diagnose-Plots, technischer Look) ------------------
# Kühles Off-White plus Monospace-Typografie für einen ruhigen, technischen
# Eindruck, bewusster Kontrast zu den dunklen Karten.
LIGHT_BG = "#f4f5f6"
INK = "#000000"        # Schwarz für sämtliche Schrift
GRID = "#e2e4e7"       # dezentes kühles Gitter
MUTED = "#6b7177"      # gestrichelte Schwellenlinien (keine Schrift)

FONT = "Consolas, JetBrains Mono, SF Mono, Menlo, monospace"


def apply_light_theme(chart):
    """Legt das helle Diagnose-Theme über ein Altair-Chart.

    Setzt Hintergrund, Typografie, Gitter und großzügige Abstände. Bewusst
    textarm gehalten; die fachliche Erklärung steht im Repo, nicht im Plot.

    Args:
        chart: Ein Altair-Chart (alt.Chart oder Layer/Concat).

    Returns:
        Das konfigurierte Chart.
    """
    return (
        chart.configure(background=LIGHT_BG, font=FONT, padding=18)
        .configure_view(strokeWidth=0, continuousWidth=520, continuousHeight=300)
        .configure_axis(
            labelColor=INK,
            titleColor=INK,
            titleFontSize=11,
            titleFontWeight="normal",
            labelFontSize=11,
            gridColor=GRID,
            gridWidth=0.6,
            domainColor="#c4c8cd",
            domainWidth=1,
            tickColor="#c4c8cd",
            tickSize=4,
            labelPadding=6,
            titlePadding=12,
        )
        .configure_legend(
            labelColor=INK,
            titleColor=INK,
            labelFontSize=11,
            titleFontSize=11,
            symbolType="circle",
            symbolSize=130,
            labelBaseline="middle",
            padding=8,
        )
        .configure_title(color=INK, fontSize=14, fontWeight=500, anchor="start", dy=-6)
    )


def crameri_colormap(role: str):
    """Liefert die cmcrameri-Colormap für eine gegebene Datenrolle.

    Args:
        role: Schlüssel aus CRAMERI_MAP_NAMES ("coherence", "deformation",
            "phase").

    Returns:
        Die passende matplotlib-Colormap aus cmcrameri.

    Raises:
        KeyError: Wenn die Rolle nicht definiert ist.
    """
    if role not in CRAMERI_MAP_NAMES:
        raise KeyError(f"Unbekannte Rolle '{role}', erlaubt: {list(CRAMERI_MAP_NAMES)}")

    from cmcrameri import cm

    return getattr(cm, CRAMERI_MAP_NAMES[role])


def damage_color_scale():
    """Liefert eine Altair-Color-Scale für die kategorialen Schadensklassen.

    Returns:
        Eine alt.Scale mit fester Domain-Range-Bindung, damit die
        Klassenfarben über alle Figuren stabil bleiben.
    """
    import altair as alt

    return alt.Scale(
        domain=list(DAMAGE_CLASSES.keys()),
        range=list(DAMAGE_CLASSES.values()),
    )
