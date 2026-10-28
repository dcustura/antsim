"""Find the dimension that makes an antenna resonant (X = 0) at a frequency.

CLI: python3 -m antsim tune models/<file>.py FREQ LO HI [--at antenna|line] [--n 13] [--max-r OHMS]

The model file must define `build(length) -> Model`; LO/HI bound the length scan (m).
Resonance can be sought at the antenna terminals or at the input of `model.feedline`.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable

import numpy as np

from .workspace import load_build, out_root
from .model import Model
from .nec import impedance


@dataclass
class Solution:
    length: float
    z_ant: complex
    z_line: complex | None


def _z(build: Callable[[float], Model], length: float, f: float, workdir: Path):
    m = replace(build(length), sweep=(f, f, 1), center_freq=f)
    z = complex(impedance(m, workdir)[0])
    zl = complex(m.feedline.transform(z, f)) if m.feedline else None
    return z, zl


def find_lengths(build: Callable[[float], Model], f: float, lo: float, hi: float,
                 at: str = "antenna", n: int = 13, tol: float = 0.002,
                 max_r: float | None = None, workdir: Path | None = None) -> tuple[list[Solution], list[tuple]]:
    """Scan n lengths in [lo, hi], then bisect every X sign change to `tol` metres.
    Solutions with R > max_r (at the chosen point) are dropped.
    Returns (solutions, scan) where scan rows are (length, z_ant, z_line)."""
    workdir = workdir or out_root() / "_tune"
    side = (lambda za, zl: za) if at == "antenna" else (lambda za, zl: zl)
    pick = lambda za, zl: side(za, zl).imag
    scan = [(L, *_z(build, L, f, workdir)) for L in np.linspace(lo, hi, n)]
    sols = []
    for (l0, za0, zl0), (l1, za1, zl1) in zip(scan, scan[1:]):
        x0, x1 = pick(za0, zl0), pick(za1, zl1)
        if x0 * x1 > 0:
            continue
        # X vs length also jumps sign through a pole (open-circuit-like point); skip those
        if abs(x0) > 5000 or abs(x1) > 5000:
            continue
        while l1 - l0 > tol:
            lm = (l0 + l1) / 2
            zam, zlm = _z(build, lm, f, workdir)
            xm = pick(zam, zlm)
            if x0 * xm <= 0:
                l1, x1 = lm, xm
            else:
                l0, x0 = lm, xm
        L = (l0 + l1) / 2
        sol = Solution(L, *_z(build, L, f, workdir))
        r = side(sol.z_ant, sol.z_line).real
        if max_r is None or r <= max_r:
            sols.append(sol)
    return sols, scan


def main(argv=None, prog=None) -> int:
    ap = argparse.ArgumentParser(prog=prog, description=__doc__.splitlines()[0])
    ap.add_argument("model_file", type=Path)
    ap.add_argument("freq", type=float)
    ap.add_argument("lo", type=float)
    ap.add_argument("hi", type=float)
    ap.add_argument("--at", choices=["antenna", "line"], default="antenna")
    ap.add_argument("--n", type=int, default=13)
    ap.add_argument("--max-r", type=float, help="keep only resonances with R below this (ohms)")
    a = ap.parse_args(argv)
    build = load_build(a.model_file)
    sols, scan = find_lengths(build, a.freq, a.lo, a.hi, a.at, a.n, max_r=a.max_r)
    fl = build(a.lo).feedline
    print(f"Scan at {a.freq:g} MHz (resonance sought at {a.at}"
          + (f"; feedline {fl.describe()}" if fl else "") + ")")
    print(f"{'length m':>9} | {'Z antenna':>20} | {'Z line input':>20}")
    for L, za, zl in scan:
        zls = f"{zl.real:8.1f} {zl.imag:+9.1f}j" if zl is not None else ""
        print(f"{L:9.3f} | {za.real:8.1f} {za.imag:+9.1f}j | {zls}")
    if not sols:
        print("No resonance in range" + (f" with R < {a.max_r:g} Ω." if a.max_r else "."))
    for s in sols:
        zls = f", line input {s.z_line.real:.1f} {s.z_line.imag:+.1f}j Ω" if s.z_line is not None else ""
        print(f"→ resonant length {s.length:.3f} m: antenna {s.z_ant.real:.1f} {s.z_ant.imag:+.1f}j Ω{zls}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
