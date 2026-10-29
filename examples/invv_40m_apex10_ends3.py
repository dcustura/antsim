"""40 m inverted-V with build(length) for `antsim tune`; apex 10 m, ends 3 m, average ground.

Find the resonant length:  python3 -m antsim tune examples/invv_40m_apex10_ends3.py 7.1 18 23
"""
from antsim import AWG, Ground, Model
from antsim.shapes import inverted_v

APEX = 10.0          # m
END_HEIGHT = 3.0     # m
RADIUS = AWG[14]


def build(total: float) -> Model:
    """Inverted-V with `total` metres of wire (incl. the 0.25 m feed gap)."""
    wires, g = inverted_v(total, APEX, END_HEIGHT, RADIUS, segments=41)
    return Model(
        name=g["tag"],
        wires=wires,
        feed=g["feed"],
        ground=Ground.real(),
        sweep=(6.9, 7.4, 26),
        center_freq=7.1,
        description=f"Inverted-V, {total:.2f} m total AWG14, apex {APEX:g} m, ends {END_HEIGHT:g} m, "
                    f"legs {g['leg']:.2f} m, {g['angle']:.0f}° included, span {g['span']:.1f} m, "
                    f"average ground",
    )


models = [build(20.6)]
