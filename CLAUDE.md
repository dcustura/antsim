# antsim: antenna modelling with NEC2 (nec2c)

The user describes an HF/VHF wire antenna in plain language (a dipole, inverted-V, vertical, end-fed, loop, Yagi, trap or loaded antenna, a feedline system). Turn the description into a Python model file, simulate it with nec2c, check the result, and report it. The harness is the `antsim` package. Plots and summaries go to `out/<slug>/<band>/` (see Naming).

## Workflow
1. **Pin down the design.** Collect the band or design frequency, the dimensions, the heights, the ground, the wire or tube size, the feed and feedline, and what the user wants to learn. When the user doesn't give a value, choose a sensible default and say which one you chose: AWG14 wire, average ground, 50 Ω, and a sweep covering the band.
2. **Write `models/<type>_<band>[_<features>].py`** (see Naming). Start from the closest example (`python3 -m antsim examples`). `python3 -m antsim new <name> --from <example>` copies it. Use `antsim.shapes` builders when one fits; otherwise build `Wire`s directly. Pass `name=info["tag"]` to `Model`. Define `model = Model(...)`, or `models = [...]` for variants. Also define `build(length) -> Model` whenever a dimension needs tuning.
3. **Run it:** `python3 -m antsim run models/<name>.py`. Add `--only <slug>` (or `<slug>/<band>`) to run one variant. A 5° pattern over real ground takes a few seconds.
4. **Check before reporting.** Fix every **Model warning** in the summary. Make sure the sweep brackets the resonance; "hits sweep edge" or "none in sweep" means you should widen it. Results should be plausible: a free-space dipole is about 73 Ω, and efficiency over real ground is usually 30–90%. When the shape of the result matters, look at `out/<slug>/<band>/swr.png`, `pattern.png` and `azimuth.png`.
5. **Tune** when the user wants a resonant or matched design: `python3 -m antsim tune …` (see below). Then put the solved dimension into `models` and rerun. Resonant frequency scales roughly as 1/length.
6. **Report:** resonance, impedance and SWR at the design frequency, SWR<2 bandwidth, peak gain and take-off angle, F/B for beams, radiation efficiency, and any warnings. Give the model file path and the `out/<slug>/<band>/` directory.

## Commands (`python3 -m antsim <command>`, or `antsim` after `pip install -e .`)
| Command | Purpose |
|---|---|
| `run FILE... [--only NAME]` | Simulate. Writes `sweep.nec/.out`, `pattern.nec/.out`, `swr.png`, `pattern.png`, `azimuth.png` and `summary.md`. `python3 -m antsim FILE.py` is short for this. |
| `tune FILE FREQ LO HI [--at antenna\|line] [--n N] [--max-r OHMS]` | The file defines `build(length)`. Scans the length, then bisects each X=0 crossing. `--at line` finds resonance at the feedline input. `--max-r` drops high-impedance resonances. Near poles, X at the line input changes fast, so use a fine scan (about 1 m steps). |
| `multiband FILE --wire LO HI STEP [--line LO HI STEP] [--line-z0 450] [--balun N] [--coax-length/-vf/-z0/-loss] [--region 1\|2\|3] [--bands 80m,40m,…] [--max-swr 3] [--rank coverage\|minimax]` | The file defines `build(total_length)`. Finds the wire and ladder-line lengths with the lowest SWR across several bands. Leave out `--line` for coax only. Antenna impedances are cached in `out/_multiband/<file>.npz`, so trying another balun, loss or line range takes seconds. |
| `new NAME [--from EXAMPLE]` / `examples` | Start a model from an example, or list the examples. |
| `bands [--region N]` | IARU band edges. `$ANTSIM_REGION` sets the default region (3). |
| `doctor` | Checks nec2c and the Python dependencies, and runs a dipole sanity check. |

`$ANTSIM_OUT` overrides the output root (`out/`). Tests: `python3 -m unittest discover tests`.

## Naming
- **Model files** describe a design: `<type>_<band>[_<features>].py`, e.g. `invv_80m_apex12_ends4.py`, `trapdipole_40m-20m.py`, `dipole_multiband.py`. The type is the shape word (`dipole`, `invv`, `trapdipole`, `endfed`, `vertical`, `quad`, `delta`, `yagi<n>`). The features are what tell this design apart from others of the same type, such as the heights (`apex12_ends4`) or the mast.
- **Output** goes to `out/<slug>/<band>/`, built from the model's parameters (`antsim/naming.py`), so don't hand-write names.
  - The slug is `<geometry>[_<wire>][_<feed>][_<conductor>]_<ground>`, e.g. `invv_29.39m_apex12_ends4_450ohm10.6m_avg`.
  - The geometry is the shape's `info["tag"]`: type, then the defining length in metres (total wire, radiator, perimeter), then the heights and dimensions, each after its word (`h10`, `apex12_ends4`, `base2.5`, `rad4x10.5_droop1.5`, `cp2`, `inner10`, `boom6.4`).
  - The wire part is omitted for AWG14; otherwise `awg18`, or `d12.7mm` for tube. The feed part has one token per section, antenna side first, joined with `+`: `450ohm9m+4to1+50ohm10m` (physical lengths). The conductor is `cu` or `al`, and is omitted when the wire is lossless. The ground is `free`, `perfect`, `avg`, `poor`, `good`, or `er<εr>s<σ>`.
  - The band is the IARU band of `center_freq` (`80m`), else the frequency (`12.5MHz`). The same antenna on two bands shares one slug directory.
- Numbers are in metres, rounded to the centimetre. `run` stops if two models map to the same directory. For a difference the slug doesn't capture, such as loads or element lengths, add a suffix: `name=info["tag"] + "_<variant>"`.

## API (`from antsim import …`)
- `Wire(p1, p2, radius_m, segments)`: points are (x, y, z) in metres, and Z is height above ground. Tags are 1..n in list order.
- `Model(name, wires, feed=(tag, seg), ground=Ground.free()|.perfect()|.real(eps_r, sigma), sweep=(f0, f1, n), center_freq, z0=50, pattern_step=5, azimuth_elevations=(5, 10, 20, 30, 45, 60), feedline=None, loads=[], conductivity=None, description="")`.
  - `name` is normally the shape's `info["tag"]`. `m.slug`, `m.band` and `m.run_dir` give the output names.
  - `feed` defaults to the centre segment of wire 1. The pattern is computed at `center_freq`, which defaults to the sweep midpoint.
  - `conductivity=COPPER|ALUMINIUM` (S/m) adds wire loss. By default wires are lossless.
  - `loads=[Load(tag, seg, r, l, c, parallel=False)]`, using NEC LD cards. Helpers: `Load.coil(tag, seg, l_uh, q=, f_mhz=)`, `Load.trap(tag, seg, l_uh, c_pf)`, `Load.trap_for(tag, seg, f_mhz, c_pf)`. For a series load, a zero L or C means that element is absent.
- Feed systems: `Feedline(z0, electrical_length)` is a lossless line, equivalent to a NEC TL card and checked against nec2c TL to within 0.1 Ω. `Feedline.physical(z0, length, vf, loss_db_100m_10mhz)` describes real coax; loss scales as √f. `Transformer(N)` is an ideal N:1 balun or unun, from the antenna side to the shack side. N < 1 steps the impedance up: `Transformer(0.25)` is a 1:4 (labelled `1:4`, tag `1to4`). `Component.shunted(l_uh=|c_pf=)` and `Component.series(l_uh=|c_pf=)` are ideal matching-network parts (shunt across the line, or in series with it); an L-network is two of them. `FeedlineChain((…))` is listed antenna side first. With a feedline, SWR and `sweep.z_line` refer to the shack end, and `swr.png` gains a line-input impedance panel. On a lossless line, SWR does not depend on the coax length.
- `antsim.shapes`: each builder returns `(wires, info)`, and you pass `name=info["tag"], feed=info["feed"]` to `Model`.
  - `dipole(length, height, radius, segments)`: along Y.
  - `inverted_v(total, apex, end_height, radius)`: `info` has the leg, the included angle and the span.
  - `trap_dipole(inner, outer, height, radius)`: `info["traps"]` gives the (tag, seg) pairs for `Load.trap_for`.
  - `end_fed(length, height, radius, counterpoise=2.0)`: gives kΩ at the feed, so set `z0=2450` for a 49:1 transformer.
  - `vertical(height, radius, base, radials, radial_length, radial_droop)`: fed at the base.
  - `quad_loop(perimeter, bottom, radius)` and `delta_loop(perimeter, bottom, radius)`: vertical loops in the YZ plane, fed at the bottom centre.
  - `yagi([(x, length), …], height, radius, driven=1)`: the beam points to +X, azimuth 0°.
  - `segments_for(length, f_max)` returns an odd segment count of about 20 per half-wave.
- Wire sizes: `AWG[14]` (or `awg(n)`) is a radius in metres, and `antsim.wire_gauge.TUBE_*` give tube diameters (halve them for the radius).
- `antsim.bands.bands(region, names)` and `band_of(f)` give IARU band edges.

## NEC2 modelling rules
- Keep segments shorter than λ/10 at the highest frequency, and use about 20 or more segments per half-wave. Use an odd segment count so the wire has a centre segment for the feed. The segment-to-radius ratio must be above 4 (thin-wire limit).
- Wires that join must share exact endpoint coordinates; `check()` warns about near misses under 1 cm. Avoid jumps of more than 5× in segment length at a junction.
- To feed between two wires, as at an inverted-V apex, use a short 1-segment feed wire.
- Ground: compare antennas in `free` space. Use `real()` for take-off angle and realistic gain: average is εr=13, σ=0.005; poor is 5/0.001; very good is 20/0.03. Over ground, every wire must stay above z=0. Verticals need elevated radials, or `perfect()` with the base at z=0. NEC2 does not handle buried or ground-touching wires well.
- Directions: theta is measured from the zenith, so elevation = 90 − theta. Phi is measured from +X. A dipole along Y radiates broadside along X (phi 0°/180°). The summary table lists gain at azimuth 0°, 90° and 180°.
- Radiation resistance: the sweep deck computes a 5° pattern at every frequency. Integrating it gives P_rad/P_in (radiation efficiency), and R_rad = R_in × P_rad/P_in. The rest of R_in is ground, conductor and load loss. NEC gains already include this loss. A free-space lossless dipole should give about 100%, which is a sanity check.
- A feed at a high-impedance point (EFHW, a loop at a voltage point) gives thousands of ohms at `z0=50`. Set `z0` to the transformer-referred value, or report the raw Z.
- nec2c limits: card lines must be short (the code wraps CM comments at 70 characters), and file paths must be short (nec2c runs from the output directory with relative names).

## Layout
- `antsim/`: the package. `model.py` holds the geometry and deck generation, `nec.py` runs nec2c and parses its output, `report.py` writes the summary and plots, and `cli.py` holds the commands. The `naming.py`, `tune.py`, `multiband.py`, `shapes.py`, `bands.py`, `wire_gauge.py` and `plots.py` modules hold the rest.
- `examples/`: reference models that are known to work and are tuned to resonance. Don't edit them for user designs.
- `models/`: the user's designs.
- `out/`: generated results (gitignored).
- `tests/`: unittest sanity checks.

## Visual check
`xnec2c -i out/<slug>/<band>/pattern.nec` opens the GUI viewer, which shows the structure, currents and a 3D pattern.
