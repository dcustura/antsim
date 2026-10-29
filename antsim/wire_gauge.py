"""Wire radii in metres."""
from __future__ import annotations


def awg(n: int) -> float:
    """Radius (m) of solid AWG wire: d = 0.127 mm × 92^((36 − n) / 39)."""
    return 0.127e-3 * 92 ** ((36 - n) / 39) / 2


AWG = {n: awg(n) for n in range(8, 25)}   # AWG[14] = 0.000814

# Tubing, by outside diameter
TUBE_3_8_INCH = 0.009525
TUBE_HALF_INCH = 0.0127
TUBE_1_INCH = 0.0254
