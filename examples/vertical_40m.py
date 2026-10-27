"""40 m quarter-wave vertical with four elevated, drooping radials over average ground.

`build(height)` tunes the radiator:  python3 -m antsim tune examples/vertical_40m.py 7.1 9 11.5
"""
from antsim import Ground, Model
from antsim.shapes import vertical
from antsim.wire_gauge import TUBE_1_INCH, awg

BASE = 2.5           # feed point / radial hub height, m
RADIALS = 4
RADIAL_LENGTH = 10.5  # m
DROOP = 1.5          # radial ends this much lower than the hub, m


def build(height: float, name: str | None = None) -> Model:
    wires, g = vertical(height, TUBE_1_INCH / 2, base=BASE, radials=RADIALS,
                        radial_length=RADIAL_LENGTH, radial_droop=DROOP)
    for w in wires[1:]:
        w.radius = awg(14)
    return Model(
        name=name or f"vertical_40m_{height:.2f}m",
        wires=wires,
        feed=g["feed"],
        ground=Ground.real(),
        sweep=(6.9, 7.4, 26),
        center_freq=7.1,
        azimuth_elevations=(5, 10, 15, 20, 30, 45),
        description=f"Quarter-wave vertical {height:.2f} m (1/2\" tube), base at {BASE:g} m, "
                    f"{RADIALS} × {RADIAL_LENGTH:g} m AWG14 radials drooping {DROOP:g} m, average ground",
    )


models = [build(10.42, "vertical_40m")]
