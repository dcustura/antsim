"""Simulate a model, write plots and a Markdown summary."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from .model import Model, wavelength
from .nec import Pattern, Sweep, simulate
from .plots import plot_azimuth_grid, plot_pattern, plot_sweep


def run_model(m: Model, outdir: Path) -> str:
    """Run nec2c for one model; write swr.png, pattern.png, azimuth.png and summary.md.
    Returns the summary text."""
    sweep, pattern = simulate(m, outdir)
    plot_sweep(sweep, m.name, outdir / "swr.png", sweep.index(m.center_freq))
    plot_pattern(pattern, m.name, outdir / "pattern.png", m.azimuth_elevations)
    plot_azimuth_grid(pattern, m.azimuth_elevations, m.name, outdir / "azimuth.png")
    text = summarize(m, sweep, pattern)
    (outdir / "summary.md").write_text(text)
    return text


def summarize(m: Model, sweep: Sweep, pattern: Pattern) -> str:
    i = int(np.argmin(sweep.swr))
    ic = sweep.index(m.center_freq)
    gmax, th, ph = pattern.peak()
    res = sweep.resonances()
    losses = [name for name, on in (("ground", m.ground.kind == "real"),
                                    ("conductor", m.conductivity), ("loads", m.loads)) if on]
    lines = [
        f"# {m.name}",
        "",
        m.description.strip(),
        "",
        f"- Ground: {m.ground.kind}"
        + (f" (εr={m.ground.eps_r}, σ={m.ground.sigma} S/m)" if m.ground.kind == "real" else ""),
        f"- Wires: {len(m.wires)}, total length {sum(w.length for w in m.wires):.3f} m, "
        f"feed tag {m.feed[0]} seg {m.feed[1]}"
        + (f", conductivity {m.conductivity:.3g} S/m" if m.conductivity else ", lossless wire"),
    ]
    for ld in m.loads:
        lines.append(f"- Load on tag {ld.tag} seg {ld.seg}: {'parallel' if ld.parallel else 'series'} "
                     f"R={ld.r:g} Ω, L={ld.l * 1e6:g} µH, C={ld.c * 1e12:g} pF")
    lines += [
        f"- λ at {m.center_freq:g} MHz: {wavelength(m.center_freq):.3f} m",
        "",
        "| Quantity | Value |",
        "|---|---|",
        f"| Resonance at antenna (X=0) | {_fmt_res(res)} |",
        f"| Z antenna @ {sweep.freq[ic]:.3f} MHz | {sweep.z[ic].real:.1f} {sweep.z[ic].imag:+.1f}j Ω |",
    ]
    if m.feedline:
        zl = sweep.z_line
        lines += [
            f"| Feedline | {m.feedline.describe()} |",
            f"| Resonance at line input | {_fmt_res(sweep.resonances('line'))} |",
            f"| Z line input @ {sweep.freq[ic]:.3f} MHz | {zl[ic].real:.1f} {zl[ic].imag:+.1f}j Ω |",
        ]
    where = "line input" if m.feedline else "feed"
    lines += [
        f"| SWR ({m.z0:g} Ω, at {where}) @ {sweep.freq[ic]:.3f} MHz | {sweep.swr[ic]:.2f} |",
        f"| Min SWR | {sweep.swr[i]:.2f} @ {sweep.freq[i]:.3f} MHz |",
        f"| SWR < 2 bandwidth | {_bw(sweep)} |",
        f"| R radiation @ {sweep.freq[ic]:.3f} MHz | {sweep.r_rad[ic]:.2f} Ω "
        f"(loss {sweep.z.real[ic] - sweep.r_rad[ic]:.2f} Ω"
        + (f": {', '.join(losses)}" if losses else "") + ") |",
        f"| Radiation efficiency | {sweep.efficiency(ic)}, already included in gain figures |",
        f"| Peak gain @ {pattern.freq:g} MHz | {gmax:.2f} dBi at elevation {90 - th:.0f}°, azimuth {ph:.0f}° |",
    ]
    fb = pattern.front_to_back()
    if fb is not None:
        lines.append(f"| Front/back at peak elevation | {fb:.1f} dB |")
    lines += ["", "| Elevation | Max gain | at azimuth | Az 0° (+X) | Az 90° (+Y) | Az 180° (−X) |",
              "|---|---|---|---|---|---|"]
    for elev in m.azimuth_elevations:
        g, el = pattern.azimuth_cut(elev)
        ip = int(np.argmax(g))
        g0, g90, g180 = (g[pattern.phi_index(a)] for a in (0, 90, 180))
        lines.append(f"| {el:.0f}° | {g[ip]:.2f} dBi | {pattern.phi[ip]:.0f}° "
                     f"| {g0:.2f} dBi | {g90:.2f} dBi | {g180:.2f} dBi |")
    warns = m.check()
    if warns:
        lines += ["", "**Model warnings:**"] + [f"- {w}" for w in warns]
    return "\n".join(lines) + "\n"


def _fmt_res(res) -> str:
    return ", ".join(f"{f:.3f} MHz" for f in res) or "none in sweep"


def _bw(s) -> str:
    ok = s.freq[s.swr < 2]
    if len(ok) == 0:
        return "none"
    edge = " (hits sweep edge)" if ok[0] == s.freq[0] or ok[-1] == s.freq[-1] else ""
    return f"{ok[0]:.3f}–{ok[-1]:.3f} MHz ({(ok[-1] - ok[0]) * 1000:.0f} kHz){edge}"
