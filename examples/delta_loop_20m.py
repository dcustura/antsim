"""20 m full-wave delta loop, apex up, base 6 m above average ground, fed at the base centre.

Feed is ~100+ Ω, so SWR is referred to 112.5 Ω (50 Ω through a λ/4 75 Ω transformer).
"""
from antsim import AWG, Ground, Model
from antsim.shapes import delta_loop

PERIMETER = 22.5     # m
BOTTOM = 6.0         # m

wires, g = delta_loop(PERIMETER, BOTTOM, AWG[14])

model = Model(
    name="delta_loop_20m",
    wires=wires,
    feed=g["feed"],
    ground=Ground.real(),
    sweep=(13.8, 14.6, 33),
    center_freq=14.175,
    z0=112.5,
    description=f"Delta loop, {PERIMETER:g} m AWG14, sides {g['side']:.2f} m, base {BOTTOM:g} m, "
                f"apex {g['top']:.1f} m, average ground, z0 = 112.5 Ω",
)
