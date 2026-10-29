"""Names for models and their output directories.

A model's output goes to out/<slug>/<band>/:

    slug = <geometry tag>[_<feed>][_<conductor>]_<ground>
    band = IARU band of the pattern frequency ("40m"), else the frequency ("12.5MHz")

The geometry tag comes from the shape builder (info["tag"]), e.g. invv_29.39m_apex12_ends4.
Its first number is the defining length in metres (total wire, radiator or perimeter);
the others are heights and dimensions in metres, each after a word that names it.
Numbers are rounded to the centimetre, and trailing zeros are dropped.
"""
from __future__ import annotations

from .bands import band_of
from .wire_gauge import AWG

DEFAULT_GAUGE = 14
CONDUCTORS = {5.8e7: "cu", 3.5e7: "al"}
GROUNDS = {(13.0, 0.005): "avg", (5.0, 0.001): "poor", (20.0, 0.03): "good"}


def num(x: float) -> str:
    """29.368 → "29.37", 10.0 → "10"."""
    return f"{round(x, 2):g}"


def wire(radius: float) -> str:
    """"" for the default AWG14, "awg<n>" for another gauge, else "d<diameter>mm"."""
    for n, r in AWG.items():
        if abs(r - radius) < 1e-6:
            return "" if n == DEFAULT_GAUGE else f"awg{n}"
    return f"d{num(2000 * radius)}mm"


def join(*tokens: str) -> str:
    return "_".join(t for t in tokens if t)


def ground(g) -> str:
    if g.kind != "real":
        return g.kind
    return GROUNDS.get((g.eps_r, g.sigma), f"er{g.eps_r:g}s{g.sigma:g}")


def conductor(sigma: float | None) -> str:
    if not sigma:
        return ""
    return CONDUCTORS.get(sigma, f"s{sigma:.2g}")


def band(f_mhz: float) -> str:
    return band_of(f_mhz) or f"{f_mhz:g}MHz"
