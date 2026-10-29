"""3-element 20 m Yagi, 1/2" aluminium tube elements, beam towards +X (azimuth 0°).

Free space for comparison with published designs, and at 15 m over average ground.
Feed impedance is about 37 Ω; a real build would add a hairpin or gamma match.
"""
from antsim import ALUMINIUM, Ground, Model
from antsim.shapes import yagi
from antsim.wire_gauge import TUBE_HALF_INCH

RADIUS = TUBE_HALF_INCH / 2
ELEMENTS = [(0.0, 10.50), (3.2, 10.20), (6.4, 9.42)]   # (x position, length) m: reflector, driven, director
HEIGHT = 15.0


def beam(z, ground):
    wires, g = yagi(ELEMENTS, z, RADIUS, driven=1)
    return Model(
        name=g["tag"],
        wires=wires,
        feed=g["feed"],
        ground=ground,
        sweep=(13.9, 14.5, 25),
        center_freq=14.15,
        conductivity=ALUMINIUM,
        description=f"3-el Yagi, boom {g['boom']:g} m, elements "
                    + ", ".join(f"{L:g}" for _, L in ELEMENTS) + " m, 1/2\" aluminium",
    )


models = [
    beam(0.0, Ground.free()),
    beam(HEIGHT, Ground.real()),
]
