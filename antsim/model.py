"""Antenna geometry and NEC2 deck generation."""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import textwrap

import numpy as np

C = 299.792458  # speed of light, m * MHz


def wavelength(f_mhz: float) -> float:
    return C / f_mhz


@dataclass
class Wire:
    p1: tuple[float, float, float]
    p2: tuple[float, float, float]
    radius: float          # metres
    segments: int
    tag: int = 0           # assigned by Model

    @property
    def length(self) -> float:
        return math.dist(self.p1, self.p2)

    @property
    def center_segment(self) -> int:
        if self.segments % 2 == 0:
            raise ValueError(f"wire tag {self.tag}: center feed needs an odd segment count")
        return self.segments // 2 + 1


@dataclass
class Ground:
    kind: str = "free"     # "free" | "perfect" | "real"
    eps_r: float = 13.0    # average ground
    sigma: float = 0.005   # S/m

    @classmethod
    def free(cls): return cls("free")

    @classmethod
    def perfect(cls): return cls("perfect")

    @classmethod
    def real(cls, eps_r=13.0, sigma=0.005): return cls("real", eps_r, sigma)


@dataclass
class Feedline:
    """Transmission line between the antenna feed and the shack. Lossless by default,
    the same as NEC's TL card. Length is electrical (physical / velocity factor)."""
    z0: float                      # characteristic impedance, ohms
    electrical_length: float       # metres
    vf: float = 1.0                # velocity factor (only used to get physical length for loss)
    loss_db_100m_10mhz: float = 0.0  # matched loss per 100 m physical at 10 MHz, scaled ∝ √f

    @classmethod
    def physical(cls, z0: float, length: float, vf: float, loss_db_100m_10mhz: float = 0.0):
        return cls(z0, length / vf, vf, loss_db_100m_10mhz)

    def describe(self) -> str:
        loss = f", {self.loss_db_100m_10mhz:g} dB/100 m @10 MHz" if self.loss_db_100m_10mhz else ", lossless"
        phys = f" ({self.electrical_length * self.vf:.2f} m physical, VF {self.vf:g})" if self.vf != 1 else ""
        return f"{self.z0:g} Ω line {self.electrical_length:.2f} m electrical{phys}{loss}"

    def transform(self, z_load, f_mhz):
        """Impedance seen at the line input when terminated by z_load."""
        f = np.asarray(f_mhz, dtype=float)
        beta_l = 2 * np.pi * self.electrical_length / wavelength(f)
        alpha_l = (self.loss_db_100m_10mhz * np.sqrt(f / 10) / 100
                   * self.electrical_length * self.vf / 8.686)       # nepers
        t = np.tanh(alpha_l + 1j * beta_l)
        return self.z0 * (z_load + self.z0 * t) / (self.z0 + z_load * t)


@dataclass
class Transformer:
    """Ideal impedance transformer (balun/unun), ratio N:1 from antenna side to shack side."""
    ratio: float

    def describe(self) -> str:
        return f"{self.ratio:g}:1 transformer"

    def transform(self, z_load, f_mhz):
        return np.asarray(z_load) / self.ratio


@dataclass
class FeedlineChain:
    """Several line sections in series, antenna side first."""
    sections: tuple[Feedline | Transformer, ...]

    def describe(self) -> str:
        return " → ".join(s.describe() for s in self.sections)

    def transform(self, z_load, f_mhz):
        for sec in self.sections:
            z_load = sec.transform(z_load, f_mhz)
        return z_load


@dataclass
class Load:
    """Lumped RLC load on one segment (NEC LD card): traps, loading coils, resistors.
    `parallel=False` puts R, L and C in series; a zero L or C means that element is absent."""
    tag: int
    seg: int
    r: float = 0.0          # ohms
    l: float = 0.0          # henries
    c: float = 0.0          # farads
    parallel: bool = False

    @classmethod
    def coil(cls, tag, seg, l_uh: float, q: float | None = None, f_mhz: float | None = None):
        """Series inductor in µH. Give q and f_mhz to add its loss resistance (X_L / Q)."""
        r = 2 * math.pi * f_mhz * l_uh / q if q and f_mhz else 0.0
        return cls(tag, seg, r=r, l=l_uh * 1e-6)

    @classmethod
    def trap(cls, tag, seg, l_uh: float, c_pf: float):
        """Parallel LC trap, resonant at 1 / (2π√(LC))."""
        return cls(tag, seg, l=l_uh * 1e-6, c=c_pf * 1e-12, parallel=True)

    @classmethod
    def trap_for(cls, tag, seg, f_mhz: float, c_pf: float):
        """Parallel LC trap resonant at f_mhz with the given capacitance."""
        l_uh = 1 / ((2 * math.pi * f_mhz * 1e6) ** 2 * c_pf * 1e-12) * 1e6
        return cls.trap(tag, seg, l_uh, c_pf)

    def card(self) -> str:
        return (f"LD {1 if self.parallel else 0} {self.tag} {self.seg} {self.seg} "
                f"{self.r:.6g} {self.l:.6g} {self.c:.6g}")


COPPER = 5.8e7      # S/m
ALUMINIUM = 3.5e7   # S/m


@dataclass
class Model:
    name: str
    wires: list[Wire]
    feed: tuple[int, int] | None = None   # (tag, segment); default: center of wire 1
    ground: Ground = field(default_factory=Ground.free)
    sweep: tuple[float, float, int] = (14.0, 14.35, 15)  # f_start, f_stop, points (MHz)
    center_freq: float | None = None
    z0: float = 50.0
    pattern_step: float = 5.0             # degrees
    azimuth_elevations: tuple[float, ...] = (5, 10, 20, 30, 45, 60)  # azimuth cuts, degrees
    description: str = ""
    feedline: Feedline | FeedlineChain | None = None  # SWR/z_line then refer to the line input
    loads: list[Load] = field(default_factory=list)
    conductivity: float | None = None     # S/m for all wires (COPPER, ALUMINIUM); None = lossless

    def __post_init__(self):
        for i, w in enumerate(self.wires, start=1):
            w.tag = i
        if self.feed is None:
            self.feed = (1, self.wires[0].center_segment)
        if self.center_freq is None:
            self.center_freq = (self.sweep[0] + self.sweep[1]) / 2

    def absolute_segment(self, tag: int, seg: int) -> int:
        """nec2c reports segments by absolute index across all wires."""
        return sum(w.segments for w in self.wires[:tag - 1]) + seg

    def check(self) -> list[str]:
        """Return a list of modelling-guideline warnings."""
        warn = []
        lam_min = wavelength(self.sweep[1])
        tag, seg = self.feed
        if not 1 <= tag <= len(self.wires) or not 1 <= seg <= self.wires[tag - 1].segments:
            warn.append(f"feed (tag {tag}, seg {seg}) does not exist")
        for ld in self.loads:
            if not 1 <= ld.tag <= len(self.wires) or not 1 <= ld.seg <= self.wires[ld.tag - 1].segments:
                warn.append(f"load (tag {ld.tag}, seg {ld.seg}) does not exist")
        # Wires meant to join must share endpoints exactly; a near miss leaves them unconnected.
        ends = [(w, p) for w in self.wires for p in (w.p1, w.p2)]
        for i, (wa, pa) in enumerate(ends):
            for wb, pb in ends[i + 1:]:
                if wa is wb:
                    continue
                d = math.dist(pa, pb)
                if 0 < d < 0.01:
                    warn.append(f"wires {wa.tag} and {wb.tag}: endpoints {d * 1000:.1f} mm apart (not joined)")
                elif d == 0:
                    sa, sb = wa.length / wa.segments, wb.length / wb.segments
                    if max(sa, sb) / min(sa, sb) > 5:
                        warn.append(f"wires {wa.tag}/{wb.tag}: segment lengths {sa:.3f}/{sb:.3f} m "
                                    "change by >5× at the junction")
        for w in self.wires:
            seg = w.length / w.segments
            if seg > lam_min / 10:
                warn.append(f"wire {w.tag}: segment {seg:.3f} m > λ/10 ({lam_min/10:.3f} m)")
            if seg / w.radius < 4:
                warn.append(f"wire {w.tag}: segment/radius {seg/w.radius:.1f} < 4 (thin-wire limit)")
            if self.ground.kind != "free" and min(w.p1[2], w.p2[2]) < 0:
                warn.append(f"wire {w.tag}: below ground (z < 0)")
        return warn

    def _geometry(self) -> list[str]:
        # nec2c reads fixed-width cards: long comment lines crash it, so wrap them
        lines = [f"CM {self.name}"]
        for d in self.description.strip().splitlines():
            lines += [f"CM {chunk}" for chunk in textwrap.wrap(d, 70)]
        lines.append("CE")
        for w in self.wires:
            (x1, y1, z1), (x2, y2, z2) = w.p1, w.p2
            lines.append(f"GW {w.tag} {w.segments} {x1:.5f} {y1:.5f} {z1:.5f} "
                         f"{x2:.5f} {y2:.5f} {z2:.5f} {w.radius:.6f}")
        lines.append("GE 0" if self.ground.kind == "free" else "GE 1")
        if self.ground.kind == "perfect":
            lines.append("GN 1")
        elif self.ground.kind == "real":
            # Sommerfeld/Norton ground
            lines.append(f"GN 2 0 0 0 {self.ground.eps_r} {self.ground.sigma}")
        lines += [ld.card() for ld in self.loads]
        if self.conductivity:
            lines.append(f"LD 5 0 0 0 {self.conductivity:.6g}")
        tag, seg = self.feed
        lines.append(f"EX 0 {tag} {seg} 0 1.0 0.0")
        return lines

    def sweep_deck(self, pattern: bool = True) -> str:
        f0, f1, n = self.sweep
        step = (f1 - f0) / (n - 1) if n > 1 else 0.0
        # 5° pattern per frequency; integrating it gives radiated/input power and hence
        # radiation resistance (nec2c's own XNDA averaging misses the polar caps).
        nth = 37 if self.ground.kind == "free" else 19
        lines = self._geometry()
        lines += [f"FR 0 {n} 0 0 {f0:.6f} {step:.6f}",
                  f"RP 0 {nth} 72 0000 0 0 5 5" if pattern else "XQ", "EN"]
        return "\n".join(lines) + "\n"

    def pattern_deck(self) -> str:
        s = self.pattern_step
        theta_max = 90.0 if self.ground.kind != "free" else 180.0
        nth = int(round(theta_max / s)) + 1
        nph = int(round(360.0 / s))
        lines = self._geometry()
        lines += [f"FR 0 1 0 0 {self.center_freq:.6f} 0",
                  f"RP 0 {nth} {nph} 0000 0 0 {s} {s}",
                  "EN"]
        return "\n".join(lines) + "\n"
