"""40 m end-fed half-wave at 10 m over average ground, through a 49:1 transformer.

The feed is ~2–4 kΩ, so SWR is referred to 50 Ω × 49 (z0 = 2450).
"""
from antsim import AWG, Ground, Model
from antsim.shapes import end_fed

LENGTH = 19.5        # m
HEIGHT = 10.0        # m

wires, g = end_fed(LENGTH, HEIGHT, AWG[14], counterpoise=2.0)

model = Model(
    name=g["tag"],
    wires=wires,
    feed=g["feed"],
    ground=Ground.real(),
    sweep=(6.9, 7.4, 26),
    center_freq=7.1,
    z0=2450,
    description=f"End-fed half-wave {LENGTH:g} m AWG14 at {HEIGHT:g} m, 2 m counterpoise, "
                "49:1 transformer (z0 = 2450 Ω), average ground",
)
