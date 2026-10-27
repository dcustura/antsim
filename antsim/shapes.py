"""Reusable antenna geometries.

Every builder returns `(wires, info)`. `info["feed"]` is the (tag, segment) to pass as
`Model(feed=...)`, assuming the wires are used as given (tags 1..n in list order). Tags
for other features (loads, traps) are listed in `info` where relevant. To combine shapes,
offset the tags yourself: tag = position in the final wire list.

Conventions: Z is height above ground. Horizontal radiators run along Y, so the main lobe
is along X (azimuth 0°/180°). Beams point towards +X (azimuth 0°).
"""
from __future__ import annotations

import math

from .model import Wire, wavelength


def segments_for(length: float, f_max: float, per_wavelength: int = 40, minimum: int = 1) -> int:
    """Odd segment count giving at least `per_wavelength` segments per λ at f_max
    (40/λ = 20 per half-wave, comfortably under the λ/10 limit)."""
    n = max(minimum, math.ceil(length / wavelength(f_max) * per_wavelength))
    return n if n % 2 else n + 1


def dipole(length: float, height: float, radius: float, segments: int = 21) -> tuple[list[Wire], dict]:
    """Straight centre-fed dipole along Y. Feed is the centre segment of wire 1."""
    h = length / 2
    if segments % 2 == 0:
        segments += 1
    wires = [Wire((0, -h, height), (0, h, height), radius, segments)]
    return wires, dict(feed=(1, segments // 2 + 1))


def inverted_v(total: float, apex: float, end_height: float, radius: float,
               gap: float = 0.25, segments: int = 61) -> tuple[list[Wire], dict]:
    """Inverted-V along Y with `total` metres of wire (incl. a short horizontal feed
    wire of length `gap` at the apex). Feed is (tag 2, seg 1).
    info: feed, leg, angle (included, deg), span."""
    leg = (total - gap) / 2
    dz = apex - end_height
    if leg <= dz:
        raise ValueError(f"legs {leg:.2f} m too short to drop {dz:g} m from apex to ends")
    dy = math.sqrt(leg**2 - dz**2)
    y0 = gap / 2
    wires = [
        Wire((0, -y0 - dy, end_height), (0, -y0, apex), radius, segments),
        Wire((0, -y0, apex), (0, y0, apex), radius, 1),   # feed segment
        Wire((0, y0, apex), (0, y0 + dy, end_height), radius, segments),
    ]
    info = dict(feed=(2, 1), leg=leg, angle=2 * math.degrees(math.atan2(dy, dz)), span=2 * (dy + y0))
    return wires, info


def trap_dipole(inner: float, outer: float, height: float, radius: float,
                inner_segments: int = 21, outer_segments: int = 11) -> tuple[list[Wire], dict]:
    """Dipole along Y with a trap position each side: centre section `inner` m total,
    plus `outer` m beyond each trap. Each trap is a 1-segment wire for a `Load`.
    info: feed, traps = [(tag, seg), (tag, seg)] for Load.trap(...)."""
    hi = inner / 2
    s = hi * 2 / inner_segments            # trap segment matches the centre segment length
    y_out = hi + s
    wires = [
        Wire((0, -hi, height), (0, hi, height), radius, inner_segments),
        Wire((0, hi, height), (0, y_out, height), radius, 1),             # trap +Y
        Wire((0, y_out, height), (0, y_out + outer, height), radius, outer_segments),
        Wire((0, -hi, height), (0, -y_out, height), radius, 1),           # trap −Y
        Wire((0, -y_out, height), (0, -y_out - outer, height), radius, outer_segments),
    ]
    return wires, dict(feed=(1, inner_segments // 2 + 1), traps=[(2, 1), (4, 1)],
                       total=inner + 2 * s + 2 * outer)


def end_fed(length: float, height: float, radius: float, counterpoise: float = 2.0,
            segments: int = 61, cp_segments: int = 5) -> tuple[list[Wire], dict]:
    """End-fed wire along +Y at `height`, fed against a short counterpoise hanging below
    the feed point (a stand-in for the coax shield; about 0.05 λ, and its length moves
    the resonance noticeably). Feed is the top segment of the
    counterpoise. A half-wave gives thousands of ohms: set Model(z0=...) to the
    transformer-referred value (e.g. 2450 for a 49:1) or report raw Z."""
    if counterpoise >= height:
        raise ValueError("counterpoise reaches the ground")
    wires = [
        Wire((0, 0, height - counterpoise), (0, 0, height), radius, cp_segments),
        Wire((0, 0, height), (0, length, height), radius, segments),
    ]
    return wires, dict(feed=(1, cp_segments))


def vertical(height: float, radius: float, base: float = 0.0, radials: int = 4,
             radial_length: float | None = None, radial_droop: float = 0.0,
             segments: int = 21, radial_segments: int = 11) -> tuple[list[Wire], dict]:
    """Vertical monopole from `base` up to `base + height`, fed at its bottom segment.
    `radials` > 0 adds elevated radials (length defaults to `height`), drooping
    `radial_droop` m at their ends; they must stay above z=0 over real ground.
    With radials=0 use Ground.perfect() and base=0 (ideal ground plane)."""
    rl = radial_length or height
    wires = [Wire((0, 0, base), (0, 0, base + height), radius, segments)]
    if radials and base - radial_droop <= 0:
        raise ValueError("radials would touch the ground; raise `base` or reduce `radial_droop`")
    for k in range(radials):
        a = 2 * math.pi * k / radials
        r = math.sqrt(max(rl**2 - radial_droop**2, 0))
        wires.append(Wire((0, 0, base), (r * math.cos(a), r * math.sin(a), base - radial_droop),
                          radius, radial_segments))
    return wires, dict(feed=(1, 1))


def quad_loop(perimeter: float, bottom: float, radius: float, segments: int = 21) -> tuple[list[Wire], dict]:
    """Square full-wave loop in the YZ plane (vertical), bottom edge at `bottom` m,
    fed at the centre of the bottom side (horizontal polarisation, lobes along X)."""
    s = perimeter / 4
    h = s / 2
    z0, z1 = bottom, bottom + s
    if segments % 2 == 0:
        segments += 1
    corners = [(0, -h, z0), (0, h, z0), (0, h, z1), (0, -h, z1)]
    wires = [Wire(corners[i], corners[(i + 1) % 4], radius, segments) for i in range(4)]
    return wires, dict(feed=(1, segments // 2 + 1), side=s)


def delta_loop(perimeter: float, bottom: float, radius: float, segments: int = 21) -> tuple[list[Wire], dict]:
    """Equilateral full-wave delta loop in the YZ plane, apex up, horizontal base at
    `bottom` m, fed at the centre of the base (horizontal polarisation)."""
    s = perimeter / 3
    h = s / 2
    top = bottom + s * math.sqrt(3) / 2
    if segments % 2 == 0:
        segments += 1
    a, b, c = (0, -h, bottom), (0, h, bottom), (0, 0, top)
    wires = [Wire(a, b, radius, segments), Wire(b, c, radius, segments), Wire(c, a, radius, segments)]
    return wires, dict(feed=(1, segments // 2 + 1), side=s, top=top)


def yagi(elements: list[tuple[float, float]], height: float, radius: float, driven: int = 1,
         segments: int = 21) -> tuple[list[Wire], dict]:
    """Yagi with elements along Y, boom along X, beam towards +X (azimuth 0°).
    `elements` = [(x_position, length), ...] from the reflector forward; `driven` is the
    0-based index of the fed element. Tags follow the list order."""
    if segments % 2 == 0:
        segments += 1
    wires = [Wire((x, -L / 2, height), (x, L / 2, height), radius, segments) for x, L in elements]
    xs = [x for x, _ in elements]
    return wires, dict(feed=(driven + 1, segments // 2 + 1), boom=max(xs) - min(xs))
