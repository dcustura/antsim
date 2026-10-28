"""20 m half-wave dipole: free space and 10 m over average ground."""
from antsim import Ground, Model
from antsim.shapes import dipole as dipole_wires

HALF = 5.136         # half-length, m (total 10.27 m, resonant ~14.175 MHz in free space)
RADIUS = 0.000814    # AWG14
HEIGHT = 10.0


def dipole(name, z, ground, desc):
    wires, info = dipole_wires(2 * HALF, z, RADIUS, segments=21)
    return Model(
        name=name,
        wires=wires,
        feed=info["feed"],
        ground=ground,
        sweep=(13.5, 14.8, 27),
        center_freq=14.175,
        description=desc,
    )


models = [
    dipole("dipole_20m_free", 0.0, Ground.free(),
           f"Half-wave dipole, {2*HALF:.2f} m AWG14, free space"),
    dipole("dipole_20m_10m_real", HEIGHT, Ground.real(),
           f"Half-wave dipole, {2*HALF:.2f} m AWG14, {HEIGHT:g} m over average ground"),
]
