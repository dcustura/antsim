"""Multiband doublet at 12 m, fed by 450 Ω ladder line, 4:1 balun and 10 m of coax.

`build(total)` is for `antsim multiband`, which searches wire and ladder-line lengths
(it applies its own line/balun/coax from the command-line options, not COAX below):
    python3 -m antsim multiband examples/doublet_multiband.py --wire 20 30 1 --line 5 20 0.5 --balun 4
"""
from antsim import AWG, Feedline, FeedlineChain, Ground, Model, Transformer
from antsim.shapes import dipole, segments_for

HEIGHT = 12.0        # m
COAX = Feedline.physical(z0=50, length=10.0, vf=0.66, loss_db_100m_10mhz=2.0)


def build(total: float, name: str | None = None, line_e: float = 12.0,
          sweep=(7.0, 7.3, 13), center_freq: float = 7.1) -> Model:
    wires, g = dipole(total, HEIGHT, AWG[14], segments_for(total, 54.0))
    feed = FeedlineChain((Feedline(450, line_e), Transformer(4), COAX))
    return Model(
        name=name or f"doublet_{total:.2f}m",
        wires=wires,
        feed=g["feed"],
        ground=Ground.real(),
        sweep=sweep,
        center_freq=center_freq,
        feedline=feed,
        description=f"Doublet {total:.2f} m AWG14 at {HEIGHT:g} m, average ground, feed: {feed.describe()}",
    )


models = [build(26.0, "doublet_multiband")]
