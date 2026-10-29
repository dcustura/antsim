"""antsim: NEC2 wire-antenna modelling from Python model files.

Commands:
  run FILE...                   simulate model files; write plots and summary.md under out/<slug>/<band>/
  tune FILE FREQ LO HI [...]    find the length that makes build(length) resonant
  multiband FILE --wire ... [...]  search wire × feedline lengths for multiband SWR
  new NAME [--from EXAMPLE]     start models/NAME.py from an example
  examples                      list the example models
  bands [--region N]            print the band plan
  doctor                        check nec2c and Python dependencies, run a sanity model

`python3 -m antsim FILE.py` is short for `run FILE.py`. Use `<command> -h` for options.
"""
from __future__ import annotations

import argparse
import ast
from concurrent.futures import ProcessPoolExecutor
import shutil
import sys
from pathlib import Path

from .workspace import EXAMPLES, MODELS, load_models, out_root

COMMANDS = ("run", "tune", "multiband", "new", "examples", "bands", "doctor")


def cmd_run(argv) -> int:
    ap = argparse.ArgumentParser(prog="antsim run", description="Simulate model files.")
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--only", help="run only the models with this name, slug or slug/band "
                    "(when a file defines several)")
    a = ap.parse_args(argv)
    from .report import run_model
    models = []
    for path in a.files:
        found = load_models(path)
        if a.only:
            found = [m for m in found if a.only in (m.name, m.slug, m.run_dir)]
            if not found:
                raise SystemExit(f"{path}: no model named {a.only!r}")
        models += found
    runs = [m.run_dir for m in models]
    dups = sorted({r for r in runs if runs.count(r) > 1})
    if dups:
        raise SystemExit("several models would write to the same directory (give them distinct "
                         "names, e.g. a variant suffix): " + ", ".join(dups))
    outdirs = [out_root() / r for r in runs]
    # models are independent (each owns out/<slug>/<band>/), so run them on all cores;
    # map() keeps the summaries in input order
    if len(models) == 1:
        summaries = [run_model(models[0], outdirs[0])]
    else:
        with ProcessPoolExecutor() as ex:
            summaries = ex.map(run_model, models, outdirs)
    for text, outdir in zip(summaries, outdirs):
        print(text)
        print(f"→ {outdir}/ (swr.png, pattern.png, azimuth.png, summary.md, *.nec, *.out)\n")
    return 0


def _example_doc(path: Path) -> str:
    doc = ast.get_docstring(ast.parse(path.read_text())) or ""
    return doc.strip().splitlines()[0] if doc.strip() else ""


def cmd_examples(argv) -> int:
    for p in sorted(EXAMPLES.glob("*.py")):
        print(f"{p.stem:<24} {_example_doc(p)}")
    return 0


def cmd_new(argv) -> int:
    ap = argparse.ArgumentParser(prog="antsim new", description="Copy an example to models/NAME.py.")
    ap.add_argument("name")
    ap.add_argument("--from", dest="src", default="dipole_20m", help="example name (see `antsim examples`)")
    a = ap.parse_args(argv)
    src = EXAMPLES / f"{a.src.removesuffix('.py')}.py"
    if not src.exists():
        raise SystemExit(f"no example {a.src!r}; see `python3 -m antsim examples`")
    dst = MODELS / f"{a.name.removesuffix('.py')}.py"
    if dst.exists():
        raise SystemExit(f"{dst} already exists")
    MODELS.mkdir(exist_ok=True)
    shutil.copy(src, dst)
    print(f"{dst} (from {src.name}); edit it, then: python3 -m antsim run {dst.relative_to(MODELS.parent)}")
    return 0


def cmd_bands(argv) -> int:
    from .bands import REGIONS, default_region
    ap = argparse.ArgumentParser(prog="antsim bands")
    ap.add_argument("--region", type=int, choices=[1, 2, 3], default=default_region())
    a = ap.parse_args(argv)
    print(f"IARU Region {a.region} (check national allocations)")
    for name, (f0, f1) in REGIONS[a.region].items():
        print(f"{name:>5}  {f0:g}–{f1:g} MHz")
    return 0


def cmd_doctor(argv) -> int:
    ok = True
    for exe in ("nec2c", "xnec2c"):
        found = shutil.which(exe)
        need = "required" if exe == "nec2c" else "optional, for the 3D viewer"
        print(f"{'ok ' if found else 'MISSING'} {exe} ({need}){': ' + found if found else ''}")
        ok &= bool(found) or exe != "nec2c"
    for mod in ("numpy", "matplotlib"):
        try:
            v = __import__(mod).__version__
            print(f"ok  {mod} {v}")
        except ImportError:
            print(f"MISSING {mod}")
            ok = False
    if not ok:
        print("Install nec2c (e.g. `apt install nec2c`) and `pip install numpy matplotlib`.")
        return 1
    # Sanity: a free-space half-wave dipole is ~73 Ω and radiates ~100% of its input
    from .model import Model
    from .nec import simulate
    from .shapes import dipole
    from .wire_gauge import AWG
    wires, info = dipole(10.272, 0, AWG[14])
    m = Model("_doctor_dipole", wires, feed=info["feed"], sweep=(14.175, 14.175, 1))
    s, _ = simulate(m, out_root() / "_doctor")
    z, eff = s.z[0], s.rad_fraction[0]
    good = 60 < z.real < 85 and abs(eff - 1) < 0.05
    print(f"{'ok ' if good else 'FAIL'} free-space dipole: Z = {z.real:.1f} {z.imag:+.1f}j Ω, "
          f"radiation efficiency {100 * eff:.0f}%")
    return 0 if good else 1


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0 if argv else 1
    cmd, rest = argv[0], argv[1:]
    if cmd.endswith(".py"):                     # `antsim FILE.py ...` = `antsim run FILE.py ...`
        return cmd_run(argv)
    if cmd == "tune":
        from .tune import main as tune_main
        return tune_main(rest, prog="antsim tune")
    if cmd == "multiband":
        from .multiband import main as mb_main
        return mb_main(rest, prog="antsim multiband")
    handlers = {"run": cmd_run, "new": cmd_new, "examples": cmd_examples,
                "bands": cmd_bands, "doctor": cmd_doctor}
    if cmd not in handlers:
        print(f"unknown command {cmd!r}\n\n{__doc__}")
        return 1
    return handlers[cmd](rest)
