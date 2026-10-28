"""Matplotlib plots for sweep and pattern results."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .nec import Pattern, Sweep


def _z_panel(ax, f, z, ylabel: str, r_label: str = "R"):
    ax.plot(f, z.real, color=ELEV_COLORS[0], lw=2, label=r_label)
    ax.plot(f, z.imag, color=ELEV_COLORS[1], lw=2, label="X")
    ax.axhline(0, color="grey", lw=0.8)
    ax.set_ylabel(ylabel)
    ax.legend()
    ax.grid(alpha=0.3)


def plot_sweep(s: Sweep, title: str, path: Path, ic: int | None = None):
    """SWR, impedance and resistance breakdown; `ic` is the sweep index the efficiency
    is quoted at (default: the middle of the sweep)."""
    blue, aqua, magenta = ELEV_COLORS[0], ELEV_COLORS[2], ELEV_COLORS[4]
    n = 4 if s.feedline else 3
    fig, axes = plt.subplots(n, 1, figsize=(8, 3.3 * n), sharex=True)
    a1, a2, a3 = axes[0], axes[1], axes[-1]
    a1.plot(s.freq, s.swr, "o-", ms=3, color=blue)
    a1.set_ylabel(f"SWR ({s.z0:g} Ω)" + (" at line input" if s.feedline else ""))
    a1.set_ylim(1, min(10, max(3, np.nanmax(s.swr) * 1.05)))
    a1.axhline(2, color="grey", lw=0.8, ls="--")
    a1.grid(alpha=0.3)
    a1.set_title(title)
    if np.nanmin(s.swr) > 10:
        a1.text(0.5, 0.5, f"SWR > 10 across the sweep (min {np.nanmin(s.swr):.0f})\n"
                "see impedance below; needs a tuner/matching network",
                transform=a1.transAxes, ha="center", va="center", color=INK)
    _z_panel(a2, s.freq, s.z, "Impedance at antenna (Ω)", "R (input)")
    if s.feedline:
        _z_panel(axes[2], s.freq, s.z_line, "Impedance at line input (Ω)")
        axes[2].set_title(f"After {s.feedline.describe()}", fontsize=10, color=INK)
    # Resistance breakdown: R_in = R_rad + R_loss (ground, conductor and load losses)
    a3.plot(s.freq, s.z.real, color=blue, lw=2, label="R input")
    a3.plot(s.freq, s.r_rad, color=aqua, lw=2, label="R radiation")
    if not np.allclose(s.rad_fraction, 1, atol=0.02):
        a3.plot(s.freq, s.z.real - s.r_rad, color=magenta, lw=2, label="R loss")
    a3.set_ylim(0, max(s.z.real.max(), s.r_rad.max()) * 1.1)
    a3.set_ylabel("Resistance (Ω)")
    a3.set_xlabel("Frequency (MHz)")
    a3.legend()
    a3.grid(alpha=0.3)
    ic = len(s.freq) // 2 if ic is None else ic
    a3.set_title(f"Radiation efficiency {s.efficiency(ic)} at {s.freq[ic]:g} MHz",
                 fontsize=10, color=INK)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


# Categorical palette, fixed order (dataviz reference palette). Validated adjacent-pair
# CVD ΔE >= 9.1; aqua/yellow/magenta are < 3:1 on white, so curves are also direct-labelled.
ELEV_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300",
               "#6250d6", "#e34948"]
INK, MUTED = "#333333", "#888888"


def _floored(p: Pattern, floor: float) -> Pattern:
    """The pattern with gain clamped at `floor` dBi (nec2c writes -999.99 for no field)."""
    return replace(p, gain=np.maximum(p.gain, floor))


def _azimuth_cut(p: Pattern, elev: float):
    """(phi radians closed loop, gain, actual elevation) for a polar plot."""
    g, el = p.azimuth_cut(elev)
    return np.radians(np.append(p.phi, p.phi[0] + 360)), np.append(g, g[0]), el


def _style_polar(ax, rmin, rmax):
    ax.set_theta_zero_location("N")       # 0° azimuth (+X) at top
    ax.set_theta_direction(-1)            # clockwise, like a compass
    ax.set_rlim(rmin, rmax)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.grid(color="#dddddd", lw=0.6)


def plot_azimuth_grid(p: Pattern, elevations, title: str, path: Path, floor: float = -30.0):
    """Small multiples: one azimuth cut per elevation, shared dBi scale."""
    gmax = max(p.azimuth_cut(e)[0].max() for e in elevations)
    rmin, rmax = max(floor, gmax - 30), gmax + 2
    p = _floored(p, rmin)
    n = len(elevations)
    cols = min(3, n)
    rows = -(-n // cols)
    fig = plt.figure(figsize=(4.2 * cols, 4.4 * rows))
    for k, elev in enumerate(elevations):
        phi, g, el = _azimuth_cut(p, elev)
        ax = fig.add_subplot(rows, cols, k + 1, projection="polar")
        _style_polar(ax, rmin, rmax)
        ax.plot(phi, g, color=ELEV_COLORS[0], lw=2)
        ipk = int(np.argmax(g[:-1]))
        ax.plot(phi[ipk], g[ipk], "o", ms=8, color=ELEV_COLORS[0], mec="white", mew=2)
        ax.set_title(f"{el:.0f}° elevation\nmax {g[ipk]:.1f} dBi @ {np.degrees(phi[ipk]):.0f}° az",
                     color=INK, fontsize=10, pad=14)
    fig.suptitle(f"{title} — azimuth patterns, {p.freq:g} MHz (dBi, 0° = +X)",
                 color=INK)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def plot_pattern(p: Pattern, title: str, path: Path, elevations=(5, 10, 20, 30, 45, 60),
                 floor: float = -30.0, label_az: tuple[float, float] = (100.0, 170.0)):
    gmax, th_pk, ph_pk = p.peak()
    rmin, rmax = max(floor, gmax - 30), gmax + 2
    p = _floored(p, rmin)
    fig = plt.figure(figsize=(11, 5.5))

    # Overlay of azimuth cuts, one categorical colour per elevation (max 8, never cycled)
    elevations = sorted(elevations)[:len(ELEV_COLORS)]
    ax = fig.add_subplot(1, 2, 1, projection="polar")
    _style_polar(ax, rmin, rmax)
    # stagger direct labels along an azimuth arc so bunched curves don't collide
    label_azs = np.linspace(*label_az, len(elevations))
    for elev, color, az in zip(elevations, ELEV_COLORS, label_azs):
        phi, g, el = _azimuth_cut(p, elev)
        ia = p.phi_index(az)
        ax.plot(phi, g, color=color, lw=2, label=f"{el:.0f}°")
        ax.annotate(f"{el:.0f}°", (phi[ia], g[ia]), color=INK, fontsize=7,
                    ha="center", va="center",
                    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec=color, lw=1))
    ax.legend(title="Elevation", loc="upper left", bbox_to_anchor=(1.02, 1.05),
              fontsize=8, title_fontsize=8, frameon=False)
    ax.set_title("Azimuth (0° = +X)", pad=18)

    # Elevation cuts through the peak azimuth and at right angles to it (for a dipole
    # along Y: broadside and end-fire), each with its opposite azimuth on the left.
    # Drawn in ink and grey so they don't borrow the elevation colours of the left panel.
    ax = fig.add_subplot(1, 2, 2, projection="polar")
    # angle from horizon on the near side = 90 - theta, opposite side = 90 + theta
    ang = np.concatenate([90 - p.theta, (90 + p.theta)[::-1]])
    cuts = []
    for az in (ph_pk, ph_pk + 90):
        ia, ib = p.phi_index(az), p.phi_index(az + 180)
        cuts.append((ia, ib, np.concatenate([p.gain[ia, :], p.gain[ib, ::-1]])))
    # one cut is enough when the second adds nothing (verticals, other omni patterns)
    if np.max(np.abs(cuts[0][2] - cuts[1][2])) < 0.5:
        cuts = cuts[:1]
    omni = np.max(np.ptp(p.gain, axis=0)) < 0.5
    for k, ((ia, ib, g), (color, ls)) in enumerate(zip(cuts, ((INK, "-"), (MUTED, "--")))):
        ax.plot(np.radians(ang), g, color=color, ls=ls, lw=2)
        # direction labels on each horizon, stacked one line per cut, in the cut's colour
        dy = 6 - 12 * k if len(cuts) > 1 else 0
        right, left = ("any az", "any az") if omni else (f"az {p.phi[ia]:.0f}°", f"az {p.phi[ib]:.0f}°")
        for th, txt, dx, ha in ((0, f"{right} →", 6, "left"), (np.pi, f"← {left}", -6, "right")):
            ax.annotate(txt, (th, rmax), xytext=(dx, dy), textcoords="offset points",
                        ha=ha, va="center", color=color, fontsize=9, fontweight="bold",
                        annotation_clip=False)
    ax.set_rlim(rmin, rmax)
    # tick labels give elevation from the nearer horizon (negative below it); the
    # horizons themselves carry the direction labels
    if not p.full_sphere:            # over ground: upper hemisphere only
        ax.set_thetamin(0)
        ax.set_thetamax(180)
        ax.set_thetagrids([30, 60, 90, 120, 150], ["30°", "60°", "90°", "60°", "30°"])
    else:
        ax.set_thetagrids([30, 60, 90, 120, 150, 210, 240, 270, 300, 330],
                          ["30°", "60°", "90°", "60°", "30°", "−30°", "−60°", "−90°", "−60°", "−30°"])
    ax.set_title("Elevation", pad=18)

    fig.suptitle(f"{title} — {p.freq:g} MHz, peak {gmax:.2f} dBi")
    fig.tight_layout(rect=(0, 0, 1, 0.94))   # leave room for the suptitle
    fig.savefig(path, dpi=120)
    plt.close(fig)
