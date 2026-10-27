"""Multiband search: wire length × line-section length for SWR below a limit on many bands.

CLI: python3 -m antsim multiband models/<file>.py --wire LO HI STEP [--line LO HI STEP]
        [--line-z0 450] [--balun N] [--coax-length M --coax-vf VF --coax-z0 50 --coax-loss DB]
        [--region 1|2|3] [--bands 80m,40m,20m] [--max-swr 3] [--rank coverage|minimax]

The model file must define `build(total_length) -> Model` (geometry, ground, feed).
For each wire length, nec2c computes the antenna impedance at points across every band
(one deck, an FR/XQ pair per band, run in parallel). The optional ladder-line section
(--line; omit for coax only), balun and coax are then applied analytically for every line
length, so the search is cheap.

With lossless lines the coax length does not change SWR (SWR is constant along a lossless
line); only line loss does. Results are therefore worst-case (no loss masking).
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .bands import BANDS_R3, DEFAULT_BANDS, bands as band_plan, default_region
from .model import Feedline, FeedlineChain, Transformer
from .nec import _parse_freq_z, run_nec
from .workspace import load_build, out_root


def band_freqs(f0: float, f1: float) -> np.ndarray:
    step = 0.025 if f1 < 10 else 0.05 if f1 < 30 else 0.2
    n = int(np.clip(round((f1 - f0) / step) + 1, 3, 21))
    return np.linspace(f0, f1, n)


def antenna_z(model, bands: dict, workdir: Path) -> tuple[np.ndarray, np.ndarray]:
    """Antenna impedance at band_freqs() of every band: one deck, FR/XQ per band."""
    lines = [l for l in model.sweep_deck(pattern=False).splitlines() if not l.startswith(("FR", "XQ", "EN"))]
    freqs = []
    for f0, f1 in bands.values():
        fs = band_freqs(f0, f1)
        step = fs[1] - fs[0]
        lines += [f"FR 0 {len(fs)} 0 0 {f0:.6f} {step:.6f}", "XQ"]
        freqs.append(fs)
    lines.append("EN")
    tag, seg = model.feed
    workdir.mkdir(parents=True, exist_ok=True)
    text = run_nec("\n".join(lines) + "\n", workdir / "mb")
    f, z = _parse_freq_z(text, (tag, model.absolute_segment(tag, seg)))
    return np.array(f), np.array(z)


def _job(args):
    model_file, length, bands = args
    m = load_build(Path(model_file))(length)
    return antenna_z(m, bands, out_root() / "_multiband" / f"L{length:.3f}")


def swr(z, z0=50.0):
    g = np.abs((z - z0) / (z + z0))
    return (1 + g) / (1 - g)


@dataclass
class Result:
    wire: float
    line: float
    band_max_swr: dict          # band -> worst SWR in band
    band_coverage: dict         # band -> fraction of points with SWR < limit

    @property
    def n_ok(self): return sum(c == 1.0 for c in self.band_coverage.values())

    @property
    def score(self):
        # bands fully covered first, then total coverage, then how far over the limit the rest are
        over = sum(np.log(max(v / LIMIT[0], 1)) for v in self.band_max_swr.values())
        return (self.n_ok, sum(self.band_coverage.values()), -over)


LIMIT = [3.0]


def _antenna_zs(model_file, wires, bands):
    """Antenna Z for every wire length, cached per model file (invalidated on change)."""
    model_file = Path(model_file)
    cache = out_root() / "_multiband" / f"{model_file.stem}.npz"
    key = np.array([model_file.stat().st_mtime, *[f for b in bands.values() for f in b]])
    have = {}
    if cache.exists():
        d = np.load(cache)
        if d["key"].shape == key.shape and np.allclose(d["key"], key):
            have = {round(float(L), 4): z for L, z in zip(d["wires"], d["z"])}
            freqs = d["freqs"]
    todo = [float(L) for L in wires if round(float(L), 4) not in have]
    if todo:
        with ProcessPoolExecutor() as ex:
            for L, (freqs, z) in zip(todo, ex.map(_job, [(str(model_file), L, bands) for L in todo])):
                have[round(L, 4)] = z
        ws = sorted(have)
        cache.parent.mkdir(parents=True, exist_ok=True)
        np.savez(cache, key=key, wires=ws, freqs=freqs, z=np.array([have[w] for w in ws]))
    return freqs, [have[round(float(L), 4)] for L in wires]


def search(model_file, wires, lines_e, bands, coax: Feedline, line_z0=450.0, max_swr=3.0,
           line_loss=0.0, balun: float = 1.0, rank: str = "coverage"):
    LIMIT[0] = max_swr
    freqs, zs = _antenna_zs(model_file, wires, bands)
    band_of = np.concatenate([[b] * len(band_freqs(*bands[b])) for b in bands])
    results = []
    for L, z_ant in zip(wires, zs):
        for le in lines_e:
            secs = [Feedline(line_z0, le, loss_db_100m_10mhz=line_loss)] if le > 0 else []
            if balun != 1:
                secs.append(Transformer(balun))
            chain = FeedlineChain((*secs, coax))
            s = swr(chain.transform(z_ant, freqs))
            mx = {b: float(s[band_of == b].max()) for b in bands}
            cov = {b: float((s[band_of == b] < max_swr).mean()) for b in bands}
            results.append(Result(float(L), float(le), mx, cov))
    if rank == "minimax":   # smallest worst-band SWR (what a tuner has to cope with)
        results.sort(key=lambda r: max(r.band_max_swr.values()))
    else:
        results.sort(key=lambda r: r.score, reverse=True)
    return results, freqs, dict(zip(map(float, wires), zs))


def main(argv=None, prog=None) -> int:
    ap = argparse.ArgumentParser(prog=prog, description=__doc__.splitlines()[0])
    ap.add_argument("model_file", type=Path)
    ap.add_argument("--wire", type=float, nargs=3, required=True, metavar=("LO", "HI", "STEP"))
    ap.add_argument("--line", type=float, nargs=3, default=(0, 0, 1), metavar=("LO", "HI", "STEP"),
                    help="electrical length range of the ladder-line section (default: none)")
    ap.add_argument("--line-z0", type=float, default=450.0)
    ap.add_argument("--coax-length", type=float, default=10.0, help="physical, m")
    ap.add_argument("--coax-vf", type=float, default=0.66)
    ap.add_argument("--coax-z0", type=float, default=50.0)
    ap.add_argument("--coax-loss", type=float, default=0.0, help="dB/100 m at 10 MHz")
    ap.add_argument("--balun", type=float, default=1.0, help="ideal N:1 transformer at line/coax junction")
    ap.add_argument("--max-swr", type=float, default=3.0)
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--rank", choices=["coverage", "minimax"], default="coverage",
                    help="coverage: most bands under the limit; minimax: lowest worst-band SWR")
    ap.add_argument("--region", type=int, choices=[1, 2, 3], default=default_region(),
                    help="IARU region for band edges (default $ANTSIM_REGION or 3)")
    ap.add_argument("--bands", default=",".join(DEFAULT_BANDS), help="comma-separated, e.g. 80m,40m,20m")
    a = ap.parse_args(argv)
    bands = band_plan(a.region, [b.strip() for b in a.bands.split(",") if b.strip()])
    wires = np.arange(a.wire[0], a.wire[1] + 1e-9, a.wire[2])
    lines_e = np.arange(a.line[0], a.line[1] + 1e-9, a.line[2])
    coax = Feedline.physical(a.coax_z0, a.coax_length, a.coax_vf, a.coax_loss)
    results, _, _ = search(a.model_file, wires, lines_e, bands, coax, a.line_z0, a.max_swr,
                           balun=a.balun, rank=a.rank)
    print(f"IARU Region {a.region}; {len(wires)} wire × {len(lines_e)} line lengths; "
          + (f"{a.balun:g}:1 balun; " if a.balun != 1 else "") + f"coax: {coax.describe()}; "
          f"SWR limit {a.max_swr:g} (worst SWR per band shown)")
    hdr = f"{'wire':>6} {'line':>6} {'ok':>3} | " + " ".join(f"{b:>5}" for b in bands)
    print(hdr)
    for r in results[:a.top]:
        cells = " ".join(f"{min(r.band_max_swr[b], 99):5.1f}" for b in bands)
        print(f"{r.wire:6.2f} {r.line:6.2f} {r.n_ok:3d} | {cells}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
