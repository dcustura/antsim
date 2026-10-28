"""Sanity tests. Run: python3 -m unittest discover tests"""
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np

from antsim import AWG, Feedline, FeedlineChain, Ground, Load, Model, Transformer, Wire, awg
from antsim import shapes
from antsim.bands import band_of, bands
from antsim.model import wavelength
from antsim.nec import impedance, simulate

HAVE_NEC = shutil.which("nec2c") is not None


class TestPure(unittest.TestCase):
    def test_awg(self):
        self.assertAlmostEqual(AWG[14], 0.000814, places=6)
        self.assertAlmostEqual(awg(12), 0.001026, places=6)

    def test_feedline_half_wave_repeats_load(self):
        f = 10.0
        line = Feedline(450, wavelength(f) / 2)
        self.assertAlmostEqual(complex(line.transform(73 + 20j, f)), 73 + 20j, places=6)

    def test_chain_transformer(self):
        chain = FeedlineChain((Feedline(450, 0.0), Transformer(4)))
        self.assertAlmostEqual(complex(chain.transform(200 + 0j, 7.0)), 50 + 0j)

    def test_trap_for_resonates(self):
        t = Load.trap_for(2, 1, 14.15, 33)
        f = 1 / (2 * np.pi * np.sqrt(t.l * t.c)) / 1e6
        self.assertAlmostEqual(f, 14.15, places=3)
        self.assertTrue(t.card().startswith("LD 1 2 1 1"))

    def test_shapes_have_no_warnings(self):
        builds = [
            shapes.dipole(10.0, 10, AWG[14]),
            shapes.inverted_v(20.6, 10, 3, AWG[14]),
            shapes.trap_dipole(10, 3.5, 10, AWG[14]),
            shapes.end_fed(19.5, 10, AWG[14]),
            shapes.vertical(10.4, 0.006, base=2.5, radials=4, radial_droop=1.5),
            shapes.quad_loop(21.5, 6, AWG[14]),
            shapes.delta_loop(22.5, 6, AWG[14]),
            shapes.yagi([(0, 10.5), (3.2, 10.2), (6.4, 9.42)], 15, 0.00635),
        ]
        for wires, info in builds:
            m = Model("t", wires, feed=info["feed"], ground=Ground.real(), sweep=(7.0, 14.35, 3))
            self.assertEqual(m.check(), [], msg=str(info))

    def test_check_catches_near_miss_and_bad_feed(self):
        wires = [Wire((0, 0, 10), (0, 5, 10), AWG[14], 11), Wire((0, 5.002, 10), (0, 10, 10), AWG[14], 11)]
        warns = Model("t", wires, feed=(3, 1)).check()
        self.assertTrue(any("not joined" in w for w in warns))
        self.assertTrue(any("does not exist" in w for w in warns))

    def test_bands(self):
        self.assertEqual(bands(1, ["40m"])["40m"], (7.0, 7.2))
        self.assertEqual(band_of(14.2, 2), "20m")


@unittest.skipUnless(HAVE_NEC, "nec2c not installed")
class TestNec(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="antsim"))

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_free_space_dipole(self):
        wires, info = shapes.dipole(10.272, 0, AWG[14])
        m = Model("d", wires, feed=info["feed"], sweep=(14.175, 14.175, 1))
        s, p = simulate(m, self.tmp)
        self.assertAlmostEqual(s.z[0].real, 72, delta=3)
        self.assertLess(abs(s.z[0].imag), 5)
        self.assertAlmostEqual(s.rad_fraction[0], 1.0, delta=0.03)
        self.assertAlmostEqual(p.peak()[0], 2.14, delta=0.1)

    def test_conductor_loss_lowers_efficiency(self):
        wires, info = shapes.dipole(10.272, 0, AWG[24])
        lossy = Model("d", wires, feed=info["feed"], sweep=(14.175, 14.175, 1), conductivity=1e5)
        s, _ = simulate(lossy, self.tmp)
        self.assertLess(s.rad_fraction[0], 0.95)

    def test_series_load_adds_resistance(self):
        wires, info = shapes.dipole(10.272, 0, AWG[14])
        base = Model("d", wires, feed=info["feed"], sweep=(14.175, 14.175, 1))
        loaded = Model("d", wires, feed=info["feed"], sweep=(14.175, 14.175, 1),
                       loads=[Load(1, info["feed"][1], r=50)])
        dz = impedance(loaded, self.tmp)[0] - impedance(base, self.tmp)[0]
        self.assertAlmostEqual(dz.real, 50, delta=1)


if __name__ == "__main__":
    unittest.main()
