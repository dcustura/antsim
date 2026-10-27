"""40/20 m trap dipole at 10 m over average ground: 20 m traps (parallel LC), copper wire.

Shows Load.trap_for(); `build(outer)` tunes the outer sections for 40 m:
    python3 -m antsim tune examples/trap_dipole_40_20.py 7.1 2 5
"""
from antsim import AWG, COPPER, Ground, Load, Model
from antsim.shapes import trap_dipole

INNER = 10.0         # m, 20 m section between the traps
HEIGHT = 10.0        # m
TRAP_F, TRAP_C = 14.15, 33.0   # trap resonance (MHz) and capacitance (pF)


def build(outer: float, name: str | None = None, sweep=(6.9, 7.4, 26), center_freq=7.1) -> Model:
    wires, g = trap_dipole(INNER, outer, HEIGHT, AWG[14])
    traps = [Load.trap_for(tag, seg, TRAP_F, TRAP_C) for tag, seg in g["traps"]]
    return Model(
        name=name or f"trap_dipole_{outer:.2f}m",
        wires=wires,
        feed=g["feed"],
        ground=Ground.real(),
        sweep=sweep,
        center_freq=center_freq,
        loads=traps,
        conductivity=COPPER,
        description=f"Trap dipole, inner {INNER:g} m, outer {outer:.2f} m each side "
                    f"({g['total']:.2f} m total), traps {TRAP_C:g} pF @ {TRAP_F:g} MHz, "
                    f"AWG14 copper at {HEIGHT:g} m, average ground",
    )


models = [
    build(3.56, "trap_dipole_40m"),
    build(3.56, "trap_dipole_20m", sweep=(13.8, 14.6, 33), center_freq=14.175),
]
