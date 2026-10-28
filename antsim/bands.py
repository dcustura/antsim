"""Amateur band edges (MHz) per IARU region. Check national allocations, which are often narrower."""
from __future__ import annotations

import os

_COMMON = {
    "60m": (5.3515, 5.3665), "30m": (10.1, 10.15), "20m": (14.0, 14.35),
    "17m": (18.068, 18.168), "15m": (21.0, 21.45), "12m": (24.89, 24.99), "10m": (28.0, 29.7),
}

REGIONS = {
    1: {"160m": (1.81, 2.0), "80m": (3.5, 3.8), "40m": (7.0, 7.2), **_COMMON,
        "6m": (50.0, 52.0), "2m": (144.0, 146.0)},
    2: {"160m": (1.8, 2.0), "80m": (3.5, 4.0), "40m": (7.0, 7.3), **_COMMON,
        "6m": (50.0, 54.0), "2m": (144.0, 148.0)},
    3: {"160m": (1.8, 2.0), "80m": (3.5, 3.9), "40m": (7.0, 7.3), **_COMMON,
        "6m": (50.0, 54.0), "2m": (144.0, 148.0)},
}

# HF + 6 m, the default set for multiband searches
DEFAULT_BANDS = ("80m", "60m", "40m", "30m", "20m", "17m", "15m", "12m", "10m", "6m")


def default_region() -> int:
    return int(os.environ.get("ANTSIM_REGION", 3))


def bands(region: int | None = None, names=DEFAULT_BANDS) -> dict[str, tuple[float, float]]:
    """Band edges for the named bands, in order of increasing frequency."""
    plan = REGIONS[region or default_region()]
    unknown = [n for n in names if n not in plan]
    if unknown:
        raise ValueError(f"unknown band(s) {unknown}; known: {', '.join(plan)}")
    return dict(sorted(((n, plan[n]) for n in names), key=lambda kv: kv[1][0]))


def band_of(f_mhz: float, region: int | None = None) -> str | None:
    for name, (f0, f1) in REGIONS[region or default_region()].items():
        if f0 <= f_mhz <= f1:
            return name
    return None
