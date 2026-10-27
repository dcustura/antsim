"""20 m half-wave dipole: free space and 10 m over average ground."""
from antsim import Ground, Model, Wire

HALF = 5.136         # half-length, m (total 10.27 m, resonant ~14.175 MHz in free space)
RADIUS = 0.000814    # AWG14
HEIGHT = 10.0


def dipole(name, z, ground, desc):
    return Model(
        name=name,
        wires=[Wire((0, -HALF, z), (0, HALF, z), RADIUS, 21)],
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
