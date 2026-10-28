"""Run nec2c and parse its output."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import subprocess

import numpy as np

from .model import Feedline, FeedlineChain, Model

_FREQ = re.compile(r"FREQUENCY\s*:\s*([-\d.E+]+)\s*MHz")


def swr(z, z0: float = 50.0):
    g = np.abs((z - z0) / (z + z0))
    return (1 + g) / (1 - g)


@dataclass
class Sweep:
    freq: np.ndarray   # MHz
    z: np.ndarray      # complex ohms
    z0: float
    rad_fraction: np.ndarray | None = None  # radiated / input power, from pattern averaging
    feedline: Feedline | FeedlineChain | None = None

    @property
    def z_line(self):
        """Impedance at the shack end of the feedline (= z if there is none)."""
        return self.z if self.feedline is None else self.feedline.transform(self.z, self.freq)

    @property
    def r_rad(self):
        """Radiation resistance at the feed: R_in × P_rad/P_in. Over real ground the
        remainder R_in − R_rad is lost in the ground, wire conductivity and loads."""
        return self.z.real * self.rad_fraction

    @property
    def swr(self):
        return swr(self.z_line, self.z0)

    def efficiency(self, i: int) -> str:
        """Radiation efficiency at sweep point i, e.g. "36% (-4.4 dB)"."""
        e = self.rad_fraction[i]
        return f"{100 * e:.0f}% ({10 * np.log10(e):.1f} dB)"

    def index(self, f: float) -> int:
        """Index of the sweep frequency nearest to f (MHz)."""
        return int(np.argmin(np.abs(self.freq - f)))

    def resonances(self, at: str = "antenna") -> list[float]:
        """Frequencies where X crosses zero (linear interpolation), at the antenna or line input."""
        x, out = (self.z if at == "antenna" else self.z_line).imag, []
        for i in range(len(x) - 1):
            if x[i] == 0 or x[i] * x[i + 1] < 0:
                out.append(self.freq[i] - x[i] * (self.freq[i + 1] - self.freq[i]) / (x[i + 1] - x[i]))
        return out


@dataclass
class Pattern:
    freq: float
    theta: np.ndarray  # unique theta values, degrees
    phi: np.ndarray    # unique phi values, degrees
    gain: np.ndarray   # total gain dBi, shape (len(phi), len(theta))

    @property
    def full_sphere(self) -> bool:
        """Free-space decks run theta to 180°, decks over ground to about 90°."""
        return self.theta.max() > 135

    def _peak_index(self) -> tuple[int, int]:
        # in free space search the horizontal plane only, so cuts stay meaningful
        # for symmetric patterns
        if self.full_sphere and 90 in self.theta:
            it = int(np.searchsorted(self.theta, 90))
            return int(np.argmax(self.gain[:, it])), it
        ip, it = np.unravel_index(np.argmax(self.gain), self.gain.shape)
        return int(ip), int(it)

    def peak(self):
        """(gain, theta, phi) of max gain."""
        ip, it = self._peak_index()
        return self.gain[ip, it], self.theta[it], self.phi[ip]

    def phi_index(self, az: float) -> int:
        """Index of the pattern azimuth nearest to `az` degrees (wrapping at 360°)."""
        return int(np.argmin(np.abs((self.phi - az + 180) % 360 - 180)))

    def theta_index(self, elev: float) -> int:
        """Index of the pattern theta nearest to elevation `elev` degrees."""
        return int(np.argmin(np.abs(self.theta - (90 - elev))))

    def azimuth_cut(self, elev: float) -> tuple[np.ndarray, float]:
        """(gain over phi, actual elevation) at the theta nearest to `elev`."""
        it = self.theta_index(elev)
        return self.gain[:, it], 90 - self.theta[it]

    def front_to_back(self) -> float | None:
        """Peak gain minus gain 180° away in azimuth, at the peak's elevation.
        None for patterns that are symmetric front-to-back (under 0.5 dB)."""
        ip, it = self._peak_index()
        fb = float(self.gain[ip, it] - self.gain[self.phi_index(self.phi[ip] + 180), it])
        return fb if fb >= 0.5 else None


def run_nec(deck: str, path: Path) -> str:
    nec, out = path.with_suffix(".nec"), path.with_suffix(".out")
    nec.write_text(deck)
    # relative names: nec2c rejects long paths ("Input file name too long")
    r = subprocess.run(["nec2c", "-i", nec.name, "-o", out.name], cwd=nec.parent,
                       capture_output=True, text=True)
    if r.returncode != 0 or not out.exists():
        raise RuntimeError(f"nec2c failed ({r.returncode}): {r.stderr or r.stdout}")
    return out.read_text()


def parse_sweep(text: str, feed: tuple[int, int], z0: float,
                feedline: Feedline | FeedlineChain | None = None) -> Sweep:
    freqs, zs = parse_freq_z(text, feed)
    frac = [radiated_fraction(p) for p in parse_patterns(text)]
    if len(frac) != len(freqs):
        raise RuntimeError(f"expected {len(freqs)} RADIATION PATTERNS blocks, got {len(frac)}")
    return Sweep(np.array(freqs), np.array(zs), z0, np.array(frac), feedline)


def parse_freq_z(text: str, feed: tuple[int, int]) -> tuple[list[float], list[complex]]:
    freqs, zs = [], []
    lines = text.splitlines()
    current_f = None
    for i, line in enumerate(lines):
        m = _FREQ.search(line)
        if m:
            current_f = float(m.group(1))
        elif "ANTENNA INPUT PARAMETERS" in line:
            # header is 2 lines, then one row per source
            for row in lines[i + 3:]:
                p = row.split()
                if len(p) < 11 or not p[0].isdigit():
                    break
                if (int(p[0]), int(p[1])) == tuple(feed):
                    freqs.append(current_f)
                    zs.append(complex(float(p[6]), float(p[7])))
    if not freqs:
        raise RuntimeError("no ANTENNA INPUT PARAMETERS found in nec2c output")
    return freqs, zs


def parse_patterns(text: str) -> list[Pattern]:
    """All RADIATION PATTERNS blocks, one per frequency, in output order."""
    # one scan for block and FREQUENCY offsets; each block then reads only its own slice
    starts = [m.start() for m in re.finditer("RADIATION PATTERNS", text)]
    freqs = [(m.start(), float(m.group(1))) for m in _FREQ.finditer(text)]
    out, k = [], 0
    for i, j in zip(starts, starts[1:] + [len(text)]):
        while k + 1 < len(freqs) and freqs[k + 1][0] < i:
            k += 1
        out.append(_parse_rp_block(text[i:j], freqs[k][1]))
    return out


def radiated_fraction(p: Pattern) -> float:
    """P_rad / P_in = (1/4π) ∬ G sinθ dθ dφ over the computed sphere/hemisphere.
    Trapezoid in θ (sinθ weighting); φ grid is periodic, so a plain sum is exact-order."""
    g = 10 ** (np.maximum(p.gain, -300) / 10)          # linear gain, shape (phi, theta)
    th = np.radians(p.theta)
    over_phi = g.sum(axis=0) * np.radians(360 / len(p.phi))
    return float(np.trapz(over_phi * np.sin(th), th) / (4 * np.pi))


def _parse_rp_block(block: str, f: float) -> Pattern:
    """One RADIATION PATTERNS block (starting at its header) computed at f MHz."""
    rows = []
    for line in block.splitlines()[5:]:
        p = line.split()
        if len(p) < 5:
            break
        try:
            rows.append([float(v) for v in p[:5]])
        except ValueError:
            break
    a = np.array(rows)
    theta, phi = np.unique(a[:, 0]), np.unique(a[:, 1])
    gain = np.full((len(phi), len(theta)), -999.99)
    ti = np.searchsorted(theta, a[:, 0])
    pi = np.searchsorted(phi, a[:, 1])
    gain[pi, ti] = a[:, 4]
    return Pattern(f, theta, phi, gain)


def simulate(model: Model, outdir: Path) -> tuple[Sweep, Pattern]:
    outdir.mkdir(parents=True, exist_ok=True)
    sweep = parse_sweep(run_nec(model.sweep_deck(), outdir / "sweep"), model.nec_feed,
                        model.z0, model.feedline)
    pattern = parse_patterns(run_nec(model.pattern_deck(), outdir / "pattern"))[0]
    return sweep, pattern


def impedance(model: Model, outdir: Path) -> np.ndarray:
    """Feed-point impedance over the model's sweep, without patterns (fast)."""
    outdir.mkdir(parents=True, exist_ok=True)
    text = run_nec(model.sweep_deck(pattern=False), outdir / "z")
    return np.array(parse_freq_z(text, model.nec_feed)[1])
