# antsim

antsim is a small harness for modelling HF/VHF wire antennas with [NEC2](https://www.nec2.org/) (via `nec2c`). It is built so that [Claude Code](https://claude.com/claude-code) can drive it. You describe an antenna in plain language, and Claude writes a Python model, runs the simulation, checks it, and reports impedance, SWR, bandwidth, gain, take-off angle and efficiency. You can also use it directly from the command line.

```
> model a 40 m inverted-V, apex 10 m, ends 3 m, over average ground, and make it resonant at 7.1 MHz
```

## Setup

```sh
sudo apt install nec2c xnec2c       # xnec2c is optional (3D viewer)
pip install numpy matplotlib        # or: pip install -e .   (adds an `antsim` command)
python3 -m antsim doctor            # checks tools, runs a dipole sanity check
```

Then run `claude` in this directory. `CLAUDE.md` gives Claude the workflow, the API and the NEC modelling rules. `.claude/settings.json` pre-approves the simulation commands.

## Using it by hand

```sh
python3 -m antsim examples                                   # list reference models
python3 -m antsim new my_dipole --from dipole_20m            # copy one to models/
python3 -m antsim run models/my_dipole.py                    # simulate → out/<slug>/<band>/
python3 -m antsim tune examples/invv_40m_apex10_ends3.py 7.1 19 22  # resonant length
python3 -m antsim multiband examples/dipole_multiband.py --wire 20 30 1 --line 5 20 0.5 --balun 4
python3 -m antsim bands --region 1
```

A model file is plain Python:

```python
from antsim import AWG, Ground, Model
from antsim.shapes import inverted_v

wires, info = inverted_v(total=20.6, apex=10, end_height=3, radius=AWG[14])
model = Model(info["tag"], wires, feed=info["feed"], ground=Ground.real(),
              sweep=(6.9, 7.4, 26), center_freq=7.1)
```

Every run writes these files to `out/<slug>/<band>/` (see [Naming](#naming)), here `out/invv_20.6m_apex10_ends3_avg/40m/`:

- `summary.md`: resonance, Z, SWR, bandwidth, R radiation vs loss, efficiency, peak gain, F/B, and gain per elevation.
- `swr.png`: SWR, R/X at the antenna (and at the line input when there is a feedline), and the resistance breakdown.
- `pattern.png`: an overlay of azimuth cuts plus an elevation cut through the peak.
- `azimuth.png`: one azimuth plot per elevation, on a shared scale.
- `sweep.nec/.out` and `pattern.nec/.out`: the raw NEC decks and nec2c output (`xnec2c -i out/<slug>/<band>/pattern.nec`).

## Naming

Model files describe a design: `<type>_<band>[_<features>].py`. Examples are `invv_80m_apex12_ends4.py`, `trapdipole_40m-20m.py` and `dipole_multiband.py`. The type is the shape's word (`dipole`, `invv`, `trapdipole`, `endfed`, `vertical`, `quad`, `delta`, `yagi3`), and the features are what tell this design apart from others of the same type.

Each model inside a file names its output directory from its own parameters, so the name always matches what was simulated:

```
out/<geometry>[_<wire>][_<feed>][_<conductor>]_<ground>/<band>/
out/invv_29.39m_apex12_ends4_450ohm10.6m_avg/80m/
```

| Part | Tokens |
|---|---|
| geometry | type, then the defining length in m (total wire, radiator, perimeter), then heights and other dimensions: `dipole_10.27m_h10`, `invv_29.39m_apex12_ends4`, `endfed_19.5m_h10_cp2`, `vertical_10.42m_base2.5_rad4x10.5_droop1.5`, `delta_22.5m_base6`, `trapdipole_18.07m_inner10_h10`, `yagi3_boom6.4_h15` |
| wire | omitted for AWG14; `awg18`, or `d12.7mm` for tube |
| feed | each section antenna side first, joined with `+`: `450ohm9m+4to1+50ohm10m` (physical lengths) |
| conductor | omitted when lossless; `cu`, `al` |
| ground | `free`, `perfect`, `avg`, `poor`, `good`, or `er<εr>s<σ>` |
| band | IARU band of the pattern frequency (`40m`), else the frequency (`12.5MHz`) |

Numbers are in metres, rounded to the centimetre. The same antenna on two bands shares one design directory. `run` refuses to start if two models would write to the same directory.

## What it models

| | |
|---|---|
| Geometry | Any straight-wire structure. `antsim.shapes` has dipole, inverted-V, trap dipole, end-fed, vertical with radials, quad and delta loops, and Yagi. |
| Ground | Free space, perfect, or real (Sommerfeld/Norton, with εr and σ). |
| Losses | Ground loss, wire conductivity (`COPPER`, `ALUMINIUM`), and lumped R/L/C loads (traps, loading coils). |
| Feed systems | Lossless or lossy lines, ideal baluns and ununs, and chains of them. SWR is reported at the shack end. |
| Searches | Resonant-length tuning (at the antenna or at the line input), and multiband wire × ladder-line searches over the IARU region 1/2/3 bands. |

## Examples

| File | Shows |
|---|---|
| `dipole_20m.py` | Free space vs real ground; the basic template. |
| `invv_40m_apex10_ends3.py` | A `build(length)` function for `tune`. |
| `vertical_40m.py` | Elevated, drooping radials; tube radiator with wire radials. |
| `endfed_40m.py` | High-Z feed with a transformer-referred `z0`. |
| `delta_20m.py` | Loop builder, λ/4 matching section referred `z0`. |
| `trapdipole_40m-20m.py` | `Load.trap_for`, copper loss, one antenna on two bands. |
| `yagi3_20m.py` | A beam: F/B ratio, aluminium elements. |
| `dipole_multiband.py` | Doublet: ladder line + 4:1 balun + coax `FeedlineChain`, used for `multiband`. |

## Layout

```
antsim/      package: model.py, nec.py, report.py, plots.py, shapes.py, tune.py,
             multiband.py, bands.py, wire_gauge.py, cli.py, naming.py
examples/    reference models (tuned, known good)
models/      your designs
out/         generated results (gitignored)
tests/       python3 -m unittest discover tests
```

## Limits

NEC2 is a thin-wire method-of-moments code. It does not handle buried wires, wires touching real ground, or very close parallel wires of different radii well. It also can't model insulation directly. Results are only as good as the geometry and ground you give it. Treat absolute gain over real ground as an estimate, and use free space to compare designs.
