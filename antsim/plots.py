"""Matplotlib plots for sweep and pattern results."""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .nec import Pattern, Sweep


def plot_sweep(s: Sweep, title: str, path: Path, center_freq: float | None = None):
    blue, orange, aqua, magenta = ELEV_COLORS[0], ELEV_COLORS[1], ELEV_COLORS[2], ELEV_COLORS[4]
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
    a2.plot(s.freq, s.z.real, color=blue, lw=2, label="R (input)")
    a2.plot(s.freq, s.z.imag, color=orange, lw=2, label="X")
    a2.axhline(0, color="grey", lw=0.8)
    a2.set_ylabel("Impedance at antenna (Ω)")
    a2.legend()
    a2.grid(alpha=0.3)
    if s.feedline:
        al = axes[2]
        al.plot(s.freq, s.z_line.real, color=blue, lw=2, label="R")
        al.plot(s.freq, s.z_line.imag, color=orange, lw=2, label="X")
        al.axhline(0, color="grey", lw=0.8)
        al.set_ylabel("Impedance at line input (Ω)")
        al.set_title(f"After {s.feedline.describe()}",
                     fontsize=10, color=INK)
        al.legend()
        al.grid(alpha=0.3)
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
    ic = int(np.argmin(np.abs(s.freq - center_freq))) if center_freq else len(s.freq) // 2
    a3.set_title(f"Radiation efficiency {100 * s.rad_fraction[ic]:.0f}% "
                 f"({10 * np.log10(s.rad_fraction[ic]):.1f} dB) at {s.freq[ic]:g} MHz",
                 fontsize=10, color=INK)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


# Categorical palette, fixed order (dataviz reference palette). Validated adjacent-pair
# CVD ΔE >= 9.1; aqua/yellow/magenta are < 3:1 on white, so curves are also direct-labelled.
ELEV_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300",
               "#6250d6", "#e34948"]
INK, MUTED = "#333333", "#888888"


def _floor(g, floor):
    return np.maximum(g, floor)


def _azimuth_cut(p: Pattern, elev: float):
    """(phi radians closed loop, gain) at the theta nearest to the given elevation."""
    it = int(np.argmin(np.abs(p.theta - (90 - elev))))
    phi = np.radians(np.append(p.phi, p.phi[0] + 360))
    return phi, np.append(p.gain[:, it], p.gain[0, it]), 90 - p.theta[it]


def _style_polar(ax, rmin, rmax):
    ax.set_theta_zero_location("N")       # 0° azimuth (broadside, +X) at top
    ax.set_theta_direction(-1)            # clockwise, like a compass
    ax.set_rlim(rmin, rmax)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.grid(color="#dddddd", lw=0.6)


def plot_azimuth_grid(p: Pattern, elevations, title: str, path: Path, floor: float = -30.0):
    """Small multiples: one azimuth cut per elevation, shared dBi scale."""
    gmax = max(_azimuth_cut(p, e)[1].max() for e in elevations)
    rmin, rmax = max(floor, gmax - 30), gmax + 2
    n = len(elevations)
    cols = min(3, n)
    rows = -(-n // cols)
    fig = plt.figure(figsize=(4.2 * cols, 4.4 * rows))
    for k, elev in enumerate(elevations):
        phi, g, el = _azimuth_cut(p, elev)
        ax = fig.add_subplot(rows, cols, k + 1, projection="polar")
        _style_polar(ax, rmin, rmax)
        ax.plot(phi, _floor(g, rmin), color="#2a78d6", lw=2)
        ipk = int(np.argmax(g[:-1]))
        ax.plot(phi[ipk], g[ipk], "o", ms=8, color="#2a78d6", mec="white", mew=2)
        ax.set_title(f"{el:.0f}° elevation\nmax {g[ipk]:.1f} dBi @ {np.degrees(phi[ipk]):.0f}° az",
                     color=INK, fontsize=10, pad=14)
    fig.suptitle(f"{title} — azimuth patterns, {p.freq:g} MHz (dBi, 0° = broadside +X)",
                 color=INK)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def plot_pattern(p: Pattern, title: str, path: Path, elevations=(5, 10, 20, 30, 45, 60),
                 floor: float = -30.0, label_az: tuple[float, float] = (100.0, 170.0)):
    gmax, th_pk, ph_pk = p.peak()
    rmin = max(floor, gmax - 30)
    fig = plt.figure(figsize=(11, 5.5))

    # Overlay of azimuth cuts, one categorical colour per elevation (max 8, never cycled)
    elevations = sorted(elevations)[:len(ELEV_COLORS)]
    ax = fig.add_subplot(1, 2, 1, projection="polar")
    _style_polar(ax, rmin, gmax + 2)
    # stagger direct labels along an azimuth arc so bunched curves don't collide
    label_azs = np.linspace(*label_az, len(elevations))
    for elev, color, az in zip(elevations, ELEV_COLORS, label_azs):
        phi, g, el = _azimuth_cut(p, elev)
        ia = int(np.argmin(np.abs(p.phi - az)))
        ax.plot(phi, _floor(g, rmin), color=color, lw=2, label=f"{el:.0f}°")
        ax.annotate(f"{el:.0f}°", (phi[ia], max(g[ia], rmin)), color=INK, fontsize=7,
                    ha="center", va="center",
                    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec=color, lw=1))
    ax.legend(title="Elevation", loc="upper left", bbox_to_anchor=(1.02, 1.05),
              fontsize=8, title_fontsize=8, frameon=False)
    ax.set_title("Azimuth (0° = broadside)", pad=18)

    # Elevation cut through the peak azimuth (and its opposite)
    ax = fig.add_subplot(1, 2, 2, projection="polar")
    ip = np.searchsorted(p.phi, ph_pk)
    ip_opp = np.argmin(np.abs(((p.phi - ph_pk - 180) + 180) % 360 - 180))
    # angle from horizon on the peak side = 90 - theta, other side = 90 + theta
    ang = np.concatenate([90 - p.theta, (90 + p.theta)[::-1]])
    g = np.concatenate([p.gain[ip, :], p.gain[ip_opp, ::-1]])
    ax.plot(np.radians(ang), _floor(g, rmin))
    ax.set_rlim(rmin, gmax + 2)
    if p.theta.max() <= 90:
        ax.set_thetamin(0)
        ax.set_thetamax(180)
    ax.set_title(f"Elevation, azimuth {ph_pk:.0f}°/{(ph_pk + 180) % 360:.0f}°", pad=18)

    fig.suptitle(f"{title} — {p.freq:g} MHz, peak {gmax:.2f} dBi")
    fig.tight_layout(rect=(0, 0, 1, 0.94))   # leave room for the suptitle
    fig.savefig(path, dpi=120)
    plt.close(fig)
