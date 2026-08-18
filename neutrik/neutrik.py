"""NEUTRIK cable-connector part family generator.

Generates one Harnice ``part`` per Neutrik cable-connector SKU across the five
cable-connector product lines:

    XLR (XX series)   NC*FXX / NC*MXX
    etherCON          NE8MX / NE8MC / NE8MX6
    powerCON          NAC3FCA / NAC3FCB / powerCON TRUE1 / TRUE1 TOP
    TRS (1/4" phone)  NP2X / NP3X / jumboPLUG / silentPLUG
    speakON           NL*FX / NL*FC / STX NLT*

Each part gets a revision folder containing an attributes JSON, a side-view
drawing SVG, and a low-fidelity revolved STEP envelope, plus a family revision
history TSV one level up — the same product contract the D38999 family uses.

Neutrik cable connectors have no separate backshell: the chuck-type strain
relief, bushing and housing ship as one assembly. So unlike D38999 (which pairs
with an M85049 banding backshell as a second part number), the whole cable exit
is embedded in this part's envelope and the origin sits on the cable-entry face
rather than inboard of a rear accessory thread. There is no mating-side
``find_backshell()`` lookup and no accessory csys.

Dimensions are low-fidelity catalog envelopes. Sources are cited per series in
CABLE_CONNECTOR_SERIES; where Neutrik does not tabulate an internal station the
value is a drawing estimate that preserves the published overall length and
maximum diameter.
"""

import os
import json
import math
import subprocess
import sys

from harnice.lists import rev_history
from harnice import state


def _load_step_utils():
    try:
        from harnice.utils import step_utils as module
        return module
    except ImportError:
        pass
    import importlib.util

    sibling = os.path.normpath(
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            "..",
            "Harnice",
            "src",
            "harnice",
            "utils",
            "step_utils.py",
        )
    )
    spec = importlib.util.spec_from_file_location("harnice_step_utils", sibling)
    if spec is None or spec.loader is None:
        raise ImportError(
            "Generating STEP envelopes requires harnice.utils.step_utils "
            "(Harnice src/harnice/utils/step_utils.py)."
        )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


step_utils = _load_step_utils()

REVISION = "1"
DATE_STARTED = "8/18/26"
delete_pngs = True

LIBRARY_REPO = "https://github.com/harnice/harnice-av-library"
LIBRARY_SUBPATH = "neutrik"
MANUFACTURER = "Neutrik"

# ---------------------------------------------------------------------------
# Drawing conventions
# ---------------------------------------------------------------------------
# SVG px per inch — must match harnice products/part.py csys rendering.
PX_PER_IN = 96.0
MM_PER_IN = 25.4
STROKE_COLOR = "#222222"
STROKE_WIDTH = 1.5
# Everything is embedded (no backshell), so nothing overlaps −X: the origin is
# on the cable-entry face and +X runs toward the mating face.
ORIGIN_FROM_REAR_MM = 0.0

FLAGNOTE_ANGLES_DEG = [0, 15, -15, 30, -30, 45, -45, 60, -60, -75, 75, -90, 90]
FLAGNOTE_RADIUS_IN = 3.0
# Neutrik envelopes are ~3 in long, so a 3 in circle about the cable-entry
# origin lands on the body. Center the circle on the mating face instead:
# the −90°…+90° arc then sits in empty space to the right of every part.

# Housing palettes. Neutrik plates zinc-diecast shells nickel or black chrome
# and moulds the glass-reinforced housings in black.
SHELL_PALETTES = {
    "nickel": {
        "body": "#C5CAD0",
        "light": "#DDE1E5",
        "dark": "#8E959C",
        "rim": "#6E747A",
        "knurl": "#6B7176",
    },
    "black_chrome": {
        "body": "#3A3C3F",
        "light": "#55585C",
        "dark": "#26282A",
        "rim": "#141516",
        "knurl": "#6A6B6D",
    },
    "white": {
        "body": "#E8E8E6",
        "light": "#F5F5F3",
        "dark": "#C4C4C1",
        "rim": "#9A9A97",
        "knurl": "#A8A8A5",
    },
    "plastic": {
        "body": "#2B2D30",
        "light": "#3E4145",
        "dark": "#1C1D1F",
        "rim": "#0E0F10",
        "knurl": "#4A4C4F",
    },
}
_DEFAULT_PALETTE = SHELL_PALETTES["nickel"]

# Bushing / boot colors, including the speakON and powerCON color codes.
BUSHING_COLORS = {
    "black": "#1A1A1A",
    "blue": "#1D4ED8",
    "grey": "#8A8F94",
    "red": "#B91C1C",
    "yellow": "#D9A400",
    "green": "#15803D",
    "white": "#EDEDEB",
}

# Contact plating.
PLATING_COLORS = {"Ag": "#D8DCE0", "Au": "#C9A227", "Ni": "#BFC4C9"}
PLATING_NAMES = {"Ag": "silver", "Au": "gold", "Ni": "nickel"}
INSULATOR_COLOR = "#1A1A1A"

HOUSING_NAMES = {
    "": "nickel",
    "B": "black chrome",
    "BAG": "black chrome",
    "WT": "white painted",
}
HOUSING_PALETTES = {
    "": "nickel",
    "B": "black_chrome",
    "BAG": "black_chrome",
    "WT": "white",
}


def palette_for(name):
    return {**_DEFAULT_PALETTE, **SHELL_PALETTES.get(name, {})}


def contact_plating(family, finish):
    """Plating code for a housing finish. -B is the gold-contact option."""
    if finish == "B":
        return "Au"
    if family == "TRS":
        return "Ni"
    return "Ag"


def finish_name(family, finish):
    plating = contact_plating(family, finish)
    return f"{HOUSING_NAMES[finish]} housing, {PLATING_NAMES[plating]} contacts"


def px_mm(mm):
    return mm / MM_PER_IN * PX_PER_IN


def px_in(inches):
    return inches * PX_PER_IN


# ---------------------------------------------------------------------------
# SVG primitives
# ---------------------------------------------------------------------------
def _stroke_attr(stroke, stroke_width):
    if stroke is None:
        return ' stroke="none"'
    return f' stroke="{stroke}" stroke-width="{stroke_width}"'


def _rect(x, y, w, h, fill="#C0C0C0", stroke=STROKE_COLOR, stroke_width=STROKE_WIDTH):
    return (
        f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" '
        f'fill="{fill}"{_stroke_attr(stroke, stroke_width)}/>'
    )


def _poly(points, fill="#C0C0C0", stroke=STROKE_COLOR, stroke_width=STROKE_WIDTH):
    pts = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
    return (
        f'<polygon points="{pts}" fill="{fill}"'
        f'{_stroke_attr(stroke, stroke_width)}/>'
    )


def _line(x1, y1, x2, y2, stroke=STROKE_COLOR, stroke_width=1.0):
    return (
        f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
        f'stroke="{stroke}" stroke-width="{stroke_width}"/>'
    )


def _path(d, fill="#C0C0C0", stroke=STROKE_COLOR, stroke_width=STROKE_WIDTH):
    return f'<path d="{d}" fill="{fill}"{_stroke_attr(stroke, stroke_width)}/>'


def _circle(cx, cy, r, fill="#C0C0C0", stroke=STROKE_COLOR, stroke_width=STROKE_WIDTH):
    return (
        f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" '
        f'fill="{fill}"{_stroke_attr(stroke, stroke_width)}/>'
    )


def _clip_seg(x1, y1, x2, y2, xmin, ymin, xmax, ymax):
    """Liang-Barsky clip of a segment to an axis-aligned rectangle."""
    dx = x2 - x1
    dy = y2 - y1
    t0, t1 = 0.0, 1.0
    for p, q in (
        (-dx, x1 - xmin),
        (dx, xmax - x1),
        (-dy, y1 - ymin),
        (dy, ymax - y1),
    ):
        if p == 0.0:
            if q < 0.0:
                return None
            continue
        r = q / p
        if p < 0.0:
            if r > t1:
                return None
            if r > t0:
                t0 = r
        else:
            if r < t0:
                return None
            if r < t1:
                t1 = r
    return (x1 + t0 * dx, y1 + t0 * dy, x1 + t1 * dx, y1 + t1 * dy)


def _diamond_hatch(x, y, w, h, color, spacing=6.5, stroke_width=0.85):
    """Diamond knurl as clipped <line> segments (Harnice paints lines, not patterns)."""
    if w <= 0.5 or h <= 0.5:
        return []
    left, right = x, x + w
    top, bot = y, y + h
    lines = []

    def emit(ax, ay, bx, by):
        clipped = _clip_seg(ax, ay, bx, by, left, top, right, bot)
        if clipped is None:
            return
        x1, y1, x2, y2 = clipped
        if abs(x2 - x1) < 0.15 and abs(y2 - y1) < 0.15:
            return
        lines.append(_line(x1, y1, x2, y2, stroke=color, stroke_width=stroke_width))

    c = left - bot
    c_max = right - top
    while c <= c_max + 1e-6:
        emit(left, left - c, right, right - c)
        c += spacing
    c = left + top
    c_max = right + bot
    while c <= c_max + 1e-6:
        emit(left, c - left, right, c - right)
        c += spacing
    return lines


def _axial_ribs(x, y, w, h, color, count, stroke_width=0.8):
    """Evenly spaced circumferential ticks, drawn as short edge marks."""
    if w <= 0.5 or count < 1:
        return []
    tick = max(1.8, h * 0.10)
    out = []
    for i in range(count):
        xx = x + (i + 0.5) * w / count
        out.append(_line(xx, y, xx, y + tick, stroke=color, stroke_width=stroke_width))
        out.append(
            _line(xx, y + h, xx, y + h - tick, stroke=color, stroke_width=stroke_width)
        )
    return out


# ---------------------------------------------------------------------------
# Envelope profiles
# ---------------------------------------------------------------------------
# A profile is a rear-to-front list of segments. Each segment is a dict:
#   length      axial length, mm
#   dia         diameter at the rear of the segment, mm
#   dia_front   diameter at the front (omit for a plain cylinder), mm
#   role        drives the 2D fill: bushing | shell | grip | latch | barrel
#               | contact | insulator
#   knurl       True to hatch a diamond knurl over the segment (2D only)
#   ribs        integer count of axial edge ticks (2D only)
#   grooves     integer count of circumferential groove lines (2D only)
def seg(length, dia, role, dia_front=None, knurl=False, ribs=0, grooves=0):
    out = {"length": length, "dia": dia, "role": role}
    if dia_front is not None:
        out["dia_front"] = dia_front
    if knurl:
        out["knurl"] = True
    if ribs:
        out["ribs"] = ribs
    if grooves:
        out["grooves"] = grooves
    return out


def profile_stations(profile):
    """Revolution stations ``(x_mm, radius_mm)`` about +X for a profile."""
    x = ORIGIN_FROM_REAR_MM
    stations = []
    for segment in profile:
        r_rear = segment["dia"] / 2.0
        r_front = segment.get("dia_front", segment["dia"]) / 2.0
        stations.append((x, r_rear))
        x += segment["length"]
        stations.append((x, r_front))
    return stations


def profile_length_mm(profile):
    return sum(segment["length"] for segment in profile)


def _radius_at_x(profile, x_query):
    """Interpolate envelope radius (mm) at an axial station."""
    x = ORIGIN_FROM_REAR_MM
    for segment in profile:
        x1 = x + segment["length"]
        d0 = segment["dia"]
        d1 = segment.get("dia_front", d0)
        if x - 1e-9 <= x_query <= x1 + 1e-9:
            t = 0.0 if abs(segment["length"]) < 1e-12 else (x_query - x) / segment["length"]
            t = max(0.0, min(1.0, t))
            return (d0 + t * (d1 - d0)) / 2.0
        x = x1
    return profile[-1].get("dia_front", profile[-1]["dia"]) / 2.0


def _mating_tip_length_mm(profile):
    """Length of the stepped-in barrel at the mating face, or 0 if none."""
    if profile and profile[-1]["role"] == "barrel":
        return profile[-1]["length"]
    return 0.0


def make_tab(profile, length_mm, height_mm, width_mm, from_front_mm):
    """Latch tongue on the shell face, toward the viewer (+Z).

    2D: rounded U on the drawing, vertically centered on the axis (front of
    view, not the top silhouette). Open at the mating end, round cap toward
    the boot. 3D: box on +Z. The open end sits on the diameter step.
    """
    total = profile_length_mm(profile)
    x1 = total - from_front_mm
    x0 = x1 - length_mm
    return {
        "x_mm": x0,
        "length_mm": length_mm,
        "height_mm": height_mm,
        "width_mm": width_mm,
        "shell_radius_mm": _radius_at_x(profile, (x0 + x1) / 2.0),
    }


def attach_iconic_tab(variant):
    """Neutrik latch: tongue on females, window on XLR males and etherCON.

    XLR / speakON / powerCON females get a rounded U on the shell face (open
    at the mating end, round cap toward the boot). XLR males and etherCON get
    a rectangular latch *window* — the slot the female claw drops into —
    near the front of the metal, on the face toward the camera. speakON male
    (NLT*MX), powerCON male (NAC3MX-*), and TRS have no latch feature.
    """
    profile = variant["profile"]
    family = variant["family"]
    gender = variant["gender"]
    tip = _mating_tip_length_mm(profile)
    tab = None
    if family == "XLR" and gender == "female":
        length = 14.0
        tab = make_tab(profile, length, 3.0, 7.0, from_front_mm=tip)
    elif family == "XLR" and gender == "male":
        tab = make_tab(profile, 8.0, 2.0, 5.0, from_front_mm=4.0)
        tab["style"] = "window"
    elif family == "speakON" and gender == "female":
        length = 18.0
        tab = make_tab(profile, length, 5.0, 10.0, from_front_mm=tip)
    elif family == "powerCON" and gender == "female":
        true1 = "TRUE1" in variant["series"]
        length = 14.0 if true1 else 18.0
        tab = make_tab(
            profile,
            length,
            4.0 if true1 else 5.0,
            8.0 if true1 else 10.0,
            from_front_mm=tip,
        )
    elif family == "etherCON":
        tab = make_tab(profile, 8.0, 2.0, 5.0, from_front_mm=4.0)
        tab["style"] = "window"
    variant["tab"] = tab
    variant["cavity"] = mating_cavity(variant)
    return variant


def mating_cavity(variant):
    """Blind bore from the mating face (STEP only), or None.

    XLR males are a socket: the female Ø15.75 × 15 mm sleeve (drawing
    20006264) inserts into this cavity. etherCON carriers are the same
    thin-wall tube so the latch window can punch through into the RJ45
    well. The cut is a cylinder on +X, open at the mating face.
    """
    family, gender = variant["family"], variant["gender"]
    if family == "XLR" and gender == "male":
        return {"dia_mm": 15.75, "depth_mm": 15.0}
    if family == "etherCON":
        return {"dia_mm": 15.75, "depth_mm": 15.0}
    return None


def silhouette_closed_mm(stations, tab=None):
    """Closed outline (x, y) mm from revolution stations.

    The latch faces the camera, so it does not change the XY silhouette.
    ``tab`` is accepted so callers can pass it without changing the outline.
    """
    pts = [(x, r) for x, r in stations]
    pts += [(x, -r) for x, r in reversed(stations)]
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    return pts


def tab_drawing_parts(tab, pal):
    """Latch on the shell face, centered on the axis.

    Default: rounded U, open at the mating end (XLR / speakON / powerCON tongue).
    ``style=window``: rectangular cutout (XLR male / etherCON latch slot).
    """
    x_back = px_mm(tab["x_mm"])
    x_front = px_mm(tab["x_mm"] + tab["length_mm"])
    half = px_mm(tab["width_mm"] / 2.0)
    if tab.get("style") == "window":
        return [
            _rect(
                x_back,
                -half,
                x_front - x_back,
                2.0 * half,
                fill=pal["dark"],
                stroke=pal["rim"],
            )
        ]
    rad = min(half, px_mm(tab["length_mm"]) * 0.45)
    y_top, y_bot = -half, half
    x_arc = x_back + rad
    return [
        _path(
            f"M {x_front:.2f},{y_top:.2f} "
            f"L {x_arc:.2f},{y_top:.2f} "
            f"A {rad:.2f},{rad:.2f} 0 0 0 {x_arc:.2f},{y_bot:.2f} "
            f"L {x_front:.2f},{y_bot:.2f} Z",
            fill=pal["light"],
            stroke=pal["rim"],
            stroke_width=STROKE_WIDTH,
        )
    ]


def part_perimeter_inches(profile, tab=None):
    """Outer silhouette vertices in inches, closed — same outline as SVG/STEP."""
    return [
        (x / MM_PER_IN, y / MM_PER_IN)
        for x, y in silhouette_closed_mm(profile_stations(profile), tab)
    ]


def _ray_edge_intersection_t(origin, angle_rad, p0, p1, eps=1e-9):
    """Distance t>=0 along a ray from origin to segment p0->p1, or None."""
    ox, oy = origin
    dx, dy = math.cos(angle_rad), math.sin(angle_rad)
    ex, ey = p1[0] - p0[0], p1[1] - p0[1]
    det = dx * ey - dy * ex
    if abs(det) < eps:
        return None
    rx, ry = p0[0] - ox, p0[1] - oy
    t = (rx * ey - ry * ex) / det
    u = (rx * dy - ry * dx) / det
    if t < -eps or u < -eps or u > 1 + eps:
        return None
    return max(0.0, t)


def _ray_perimeter_exit_distance(origin, angle_deg, perimeter):
    """Farthest intersection of a polar ray with the part perimeter (inches)."""
    if perimeter[0] != perimeter[-1]:
        perimeter = perimeter + [perimeter[0]]
    angle_rad = math.radians(angle_deg)
    hits = []
    for i in range(len(perimeter) - 1):
        t = _ray_edge_intersection_t(origin, angle_rad, perimeter[i], perimeter[i + 1])
        if t is not None and t > 1e-6:
            hits.append(t)
    if not hits:
        return None
    return max(hits)


def flagnote_csys_children(profile, part_number, tab=None):
    """Flagnote balloons in a circle to the right of the body; leaders on the silhouette.

    Harnice polar csys is always about the drawing origin. D38999 can use that
    directly because its origin sits under a ~1.2 in shell, so a 3 in circle
    clears the part. Neutrik cable connectors are ~3 in long with the origin on
    the cable-entry face, so the same polar circle overlaps the body. Balloons
    are therefore emitted as Cartesian points on a 3 in circle centered at the
    mating face — the −90°…+90° arc sits in empty space to the right of every
    envelope. Leaders still cast from an interior mid-length anchor so their
    tips spread around the silhouette (M85049 Cartesian convention). Harnice
    resolves ``x``/``y`` or ``angle``/``distance`` but never both.
    """
    length_in = profile_length_mm(profile) / MM_PER_IN
    perimeter = part_perimeter_inches(profile, tab)
    leader_anchor = (length_in / 2.0, 0.0)
    balloon_center = (length_in, 0.0)
    children = {}
    for i, angle in enumerate(FLAGNOTE_ANGLES_DEG, start=1):
        r_leader = _ray_perimeter_exit_distance(leader_anchor, angle, perimeter)
        if r_leader is None:
            raise ValueError(
                f"flagnote-{i} ray at {angle} deg does not hit the {part_number} perimeter"
            )
        angle_rad = math.radians(angle)
        children[f"flagnote-{i}"] = {
            "x": round(balloon_center[0] + FLAGNOTE_RADIUS_IN * math.cos(angle_rad), 4),
            "y": round(balloon_center[1] + FLAGNOTE_RADIUS_IN * math.sin(angle_rad), 4),
            "rotation": 0,
        }
        children[f"flagnote-{i}-leader_dest"] = {
            "x": round(leader_anchor[0] + r_leader * math.cos(angle_rad), 4),
            "y": round(leader_anchor[1] + r_leader * math.sin(angle_rad), 4),
            "rotation": 0,
        }
    return children


def _csys_xy_px(csys):
    """Resolve a csys child to SVG px, matching harnice part.py ``csys_svg_xy``.

    Cartesian and polar are alternatives, not additive: ``x``/``y`` win when both
    are present, otherwise ``angle``/``distance`` are used.
    """
    raw_x, raw_y = csys.get("x"), csys.get("y")
    if raw_x not in ("", None) and raw_y not in ("", None):
        x_in, y_in = float(raw_x), float(raw_y)
    elif csys.get("distance") not in ("", None) and csys.get("angle") not in ("", None):
        dist = float(csys["distance"])
        ang = math.radians(float(csys["angle"]))
        x_in, y_in = dist * math.cos(ang), dist * math.sin(ang)
    else:
        x_in, y_in = 0.0, 0.0
    return x_in * PX_PER_IN, y_in * PX_PER_IN


def _csys_overlay_svg(csys_children):
    """Harnice-style csys markers (96 px/in, +Y up stored as SVG -Y)."""
    arrow_len = 24
    dot_radius = 4
    arrow_size = 6
    lines = ['  <g id="output csys locations">']
    for csys_name, csys in csys_children.items():
        x, y = _csys_xy_px(csys)
        rotation_rad = math.radians(float(csys.get("rotation", 0)))
        cos_r, sin_r = math.cos(rotation_rad), math.sin(rotation_rad)
        dx_x, dy_x = arrow_len * cos_r, arrow_len * sin_r
        dx_y, dy_y = -arrow_len * sin_r, arrow_len * cos_r

        def arrow(x1, y1, dx, dy, color):
            x2, y2 = x1 + dx, y1 + dy
            length = math.hypot(dx, dy)
            ux, uy = dx / length, dy / length
            px, py = -uy, ux
            base_x = x2 - ux * arrow_size
            base_y = y2 - uy * arrow_size
            return [
                f'      <line x1="{x1:.2f}" y1="{-y1:.2f}" x2="{x2:.2f}" y2="{-y2:.2f}" '
                f'stroke="{color}" stroke-width="2"/>',
                f'      <polygon points="{x2:.2f},{-y2:.2f} '
                f'{base_x + px * arrow_size / 2:.2f},{-(base_y + py * arrow_size / 2):.2f} '
                f'{base_x - px * arrow_size / 2:.2f},{-(base_y - py * arrow_size / 2):.2f}" '
                f'fill="{color}"/>',
            ]

        lines.append(f'    <g id="{csys_name}">')
        lines.append(
            f'      <circle cx="{x:.2f}" cy="{-y:.2f}" r="{dot_radius}" fill="black"/>'
        )
        lines.extend(arrow(x, y, dx_x, dy_x, "red"))
        lines.extend(arrow(x, y, dx_y, dy_y, "green"))
        lines.append("    </g>")
    lines.append("  </g>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# XLR — XX series cable connector (NC*FXX / NC*MXX)
# ---------------------------------------------------------------------------
# Male NC3MXX: 70.1 mm × Ø19 catalog (Adam Hall / Neutrik NC3MXX); Neutrik's
# published STEP (https://www.neutrik.com/media/13485/download/nc3mxx.stp)
# spans 69.64 mm. Photo: black tapered boot + chuck ring, then a smooth
# nickel shell with two circumferential grooves at the chuck end. No knurl.
# Female NC3FXX official drawing 20006264 (NC3FXX-50, same XX envelope):
#   https://www.neutrik.com/media/19514/download/Drawing%20NC3FXX-50.pdf
#   overall 72.5±1 mm, chuck max Ø20.3, housing Ø19.2, mating sleeve Ø15.75.
# Sleeve *length* is not a callout. Scaled from drawing 20006264 side/plan
# views: the Ø15.75 tip is about one-third of the metal body (boot excluded),
# ~15 mm, and begins at the open (mating) end of the latch.
# Envelope length 72.9 mm is the published NC3FXX STEP bbox (within 72.5±1).
def xlr_xx_profile(gender):
    boot = [
        seg(16.0, 10.0, "bushing", dia_front=16.0),
        seg(12.0, 19.0, "bushing", ribs=8),
    ]
    if gender == "male":
        # Solid envelope is a Ø19 tube; the Ø15.75 × 15 mm mating bore is cut
        # in STEP (see mating_cavity), not revolved as an inner station.
        return boot + [seg(42.1, 19.0, "shell", grooves=2)]
    return boot + [
        seg(29.9, 19.0, "shell", grooves=2),
        seg(15.0, 15.75, "barrel"),
    ]


# ---------------------------------------------------------------------------
# etherCON — RJ45 cable carrier (NE8MX / NE8MC / NE8MX6)
# ---------------------------------------------------------------------------
# Overall length 75.5 mm, Ø19.05 shell and Ø20.3 Neutrik ridge from the NE8MX6
# drawing (https://www.neutrik.com/media/10044/download/Drawing%20NE8MX6.pdf).
# NE8MX photo: smooth nickel barrel (no knurl), latch *window* near the front,
# raised logo ridge at the rear of the metal, black ribbed chuck + tapered boot.
# The CAT5 NE8MX / NE8MC carriers share the D-size compatible shell.
def ethercon_profile():
    return [
        seg(12.0, 10.5, "bushing", dia_front=20.3),
        seg(6.0, 20.3, "bushing", grooves=4),
        seg(18.0, 20.3, "bushing", ribs=8),
        seg(5.0, 20.3, "latch"),
        seg(34.5, 19.05, "shell"),
    ]


# ---------------------------------------------------------------------------
# powerCON — NAC3FCA / NAC3FCB and powerCON TRUE1 / TRUE1 TOP
# ---------------------------------------------------------------------------
# Classic 20 A overall length 77–80 mm; TRUE1 TOP max diameter Ø28.4 mm with a
# Ø23.6 mating barrel, per the powerCON product guide
# https://www.neutrik.com/media/10093/download/Neutrik%20Product%20Guide%20-%2006%20powerCON%20and%20Circular%20Connectors%20PG%20EN%20202210-V25.pdf
# TRUE1 TOP-L drawing 20003554
# (https://www.neutrik.com/media/17429/download/NAC3FX-W-TOP-L.pdf):
#   overall 76.5–79 mm, housing Ø26.5, latch extents 16.9 / 31.9 mm.
# Barrel length and classic Ø21 tip are not callouts; they are low-fi estimates
# that keep the published overall length and the stepped mating nose.
# Interior station split is a drawing estimate.
def powercon_classic_profile():
    return [
        seg(22.0, 12.0, "bushing", dia_front=17.0, ribs=6),
        seg(6.0, 17.0, "shell", dia_front=26.0),
        seg(26.5, 26.0, "grip", knurl=True),
        seg(5.0, 26.0, "latch"),
        seg(19.0, 21.0, "barrel"),
    ]


def powercon_true1_profile(large_cable=False):
    bushing_dia = 16.0 if large_cable else 13.0
    return [
        seg(24.0, bushing_dia, "bushing", dia_front=19.0, ribs=6),
        seg(6.0, 19.0, "shell", dia_front=28.4),
        seg(24.0, 28.4, "grip", knurl=True),
        seg(5.0, 28.4, "latch"),
        seg(17.0, 23.6, "barrel"),
    ]


# ---------------------------------------------------------------------------
# TRS — 1/4" phone plugs (NP2X / NP3X, jumboPLUG, silentPLUG)
# ---------------------------------------------------------------------------
# Handle Ø14.5 mm (jumboPLUG Ø17.0) and the 15.88 mm jack pitch constraint from
# the Neutrik jacks & plugs guide; the plug shank is the IEC 60603-11 /
# EIA RS-453 Ø6.35 mm, 31.0 mm long 1/4" profile.
def phone_plug_profile(poles, handle_dia=14.5, bushing_dia=9.0):
    shank = (
        [
            seg(15.0, 6.35, "contact"),
            seg(1.8, 6.35, "insulator"),
            seg(6.4, 6.35, "contact"),
            seg(1.8, 6.35, "insulator"),
            seg(6.0, 6.35, "contact"),
        ]
        if poles == 3
        else [
            seg(22.2, 6.35, "contact"),
            seg(1.8, 6.35, "insulator"),
            seg(7.0, 6.35, "contact"),
        ]
    )
    return [
        seg(8.0, bushing_dia, "bushing", dia_front=handle_dia - 3.0, ribs=4),
        seg(28.0, handle_dia, "grip", knurl=True),
        seg(2.0, handle_dia, "shell", dia_front=6.35),
    ] + shank


# ---------------------------------------------------------------------------
# speakON — NL*FX / NL*FC cable connectors and STX metal NLT*
# ---------------------------------------------------------------------------
# X series overall 71.5–76.5 mm and max Ø26 from NL4FX drawing 20000981
# https://www.neutrik.com/media/8483/download/Drawing%20NL4FX.pdf
# FC series Ø26.0 mm, overall 76.5–80.0 mm, per the speakON product guide
# https://www.neutrik.com/media/10094/download/03%20NEUTRIK%20PG%20E%20-%20speakON%20Connectors%20-%20202104-V21.pdf
# Mating-tip length is not a callout; scaled from drawing 20000981 as about
# one-third of the rigid body (boot excluded). The Ø(body−6) step is a low-fi
# estimate of the stepped nose on that NL4FX side view.
# Interior station split is a drawing estimate.
def speakon_profile(body_dia, total_length, bushing_dia):
    bushing = 22.0
    taper = 5.0
    latch = 5.0
    barrel = 17.0
    grip = total_length - bushing - taper - latch - barrel
    return [
        seg(bushing, bushing_dia, "bushing", dia_front=bushing_dia + 5.0, ribs=6),
        seg(taper, bushing_dia + 5.0, "shell", dia_front=body_dia),
        seg(grip, body_dia, "grip", knurl=True),
        seg(latch, body_dia, "latch"),
        seg(barrel, body_dia - 6.0, "barrel"),
    ]


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------
XLR_XX_POLES = [3, 4, 5, 6, 7]
# Neutrik lists -B / -BAG for the 3 to 5 pole XX housings and -WT for 3 pole.
XLR_XX_FINISHES = {3: ["", "B", "BAG", "WT"], 4: ["", "B", "BAG"], 5: ["", "B", "BAG"], 6: [""], 7: [""]}
XLR_XX_SOURCE = "https://www.neutrik.com/media/19523/download/Assembly%20Instruction%20-%20XLR%20XX%20Series.pdf"
ETHERCON_SOURCE = "https://www.neutrik.com/media/10044/download/Drawing%20NE8MX6.pdf"
POWERCON_SOURCE = "https://www.neutrik.com/media/10093/download/Neutrik%20Product%20Guide%20-%2006%20powerCON%20and%20Circular%20Connectors%20PG%20EN%20202210-V25.pdf"
PHONE_SOURCE = "https://media.djmania.net/manuales/pdf/Manual_Neutrik_NP3X.pdf"
SPEAKON_SOURCE = "https://www.neutrik.com/media/10094/download/03%20NEUTRIK%20PG%20E%20-%20speakON%20Connectors%20-%20202104-V21.pdf"

EMBEDDED_NOTE = (
    "Housing, chuck and bushing ship as one assembly; no backshell or separate "
    "strain relief part is required."
)


def _cable_note(od_min, od_max):
    return (
        f"Chuck-type strain relief accepts {od_min:.1f} - {od_max:.1f} mm cable O.D."
    )


def _xlr_variants():
    for poles in XLR_XX_POLES:
        for gender, gender_code in (("female", "F"), ("male", "M")):
            for finish in XLR_XX_FINISHES[poles]:
                suffix = f"-{finish}" if finish else ""
                yield {
                    "mpn": f"NC{poles}{gender_code}XX{suffix}",
                    "family": "XLR",
                    "series": "XX",
                    "poles": poles,
                    "gender": gender,
                    "finish": finish,
                    "palette": HOUSING_PALETTES[finish],
                    "bushing": "black",
                    "housing_material": "zinc diecast (ZnAl4Cu1)",
                    "termination": "solder cup",
                    "cable_od_mm": [3.5, 8.0],
                    "contact_names": [str(i) for i in range(1, poles + 1)],
                    "tools": ["Soldering iron"],
                    "profile": xlr_xx_profile(gender),
                    "source": XLR_XX_SOURCE,
                    "notes": [],
                }


def _ethercon_variants():
    catalog = [
        ("NE8MX", "", "carrier for pre-assembled RJ45 plugs", [4.5, 8.0], "CAT5e", []),
        ("NE8MX-B", "B", "carrier for pre-assembled RJ45 plugs", [4.5, 8.0], "CAT5e", []),
        ("NE8MC", "", "CAT5e cable connector with RJ45 plug", [5.0, 8.0], "CAT5e", ["RJ45 crimp tool"]),
        ("NE8MC-B", "B", "CAT5e cable connector with RJ45 plug", [5.0, 8.0], "CAT5e", ["RJ45 crimp tool"]),
        ("NE8MX6", "", "CAT6A self-termination cable connector, insulation diameter > 1.1 mm", [7.0, 9.5], "CAT6A", ["Cable stripping tool", "Flush cutter"]),
        ("NE8MX6-B", "B", "CAT6A self-termination cable connector, insulation diameter > 1.1 mm", [7.0, 9.5], "CAT6A", ["Cable stripping tool", "Flush cutter"]),
        ("NE8MX6-T", "", "CAT6A self-termination cable connector, insulation diameter <= 1.1 mm", [7.0, 9.5], "CAT6A", ["Cable stripping tool", "Flush cutter"]),
    ]
    for mpn, finish, desc, cable_od, category, tools in catalog:
        notes = []
        if mpn.startswith("NE8MX") and "6" not in mpn:
            notes.append("Carrier does not include an RJ45 plug; supply a pre-assembled RJ45 cable.")
            notes.append("Does not intermate with the CAT6 chassis connectors NE8FDY-C6 / NE8FDY-C6-B.")
        yield {
            "mpn": mpn,
            "family": "etherCON",
            "series": category,
            "poles": 8,
            "gender": "male",
            "finish": finish,
            "palette": HOUSING_PALETTES[finish],
            "bushing": "black",
            "housing_material": "zinc diecast (ZnAl4Cu1)",
            "termination": "RJ45",
            "cable_od_mm": cable_od,
            "contact_names": [str(i) for i in range(1, 9)],
            "tools": tools,
            "profile": ethercon_profile(),
            "source": ETHERCON_SOURCE,
            "product_desc": desc,
            "notes": notes,
        }


def _powercon_variants():
    catalog = [
        ("NAC3FCA", "powerCON 20 A", "female", "blue", "power-in cable connector, quick lock with securing lever", [6.0, 15.0], False),
        ("NAC3FCB", "powerCON 20 A", "female", "grey", "power-out cable connector, quick lock with securing lever", [6.0, 15.0], False),
        ("NAC3FX-W", "powerCON TRUE1", "female", "black", "locking power-in cable connector, IP65", [6.0, 12.0], True),
        ("NAC3MX-W", "powerCON TRUE1", "male", "black", "locking power-out cable connector, IP65", [6.0, 12.0], True),
        ("NAC3FX-W-TOP", "powerCON TRUE1 TOP", "female", "black", "locking power-in cable connector, IP65", [6.0, 12.0], True),
        ("NAC3MX-W-TOP", "powerCON TRUE1 TOP", "male", "black", "locking power-out cable connector, IP65", [6.0, 12.0], True),
        ("NAC3FX-W-TOP-L", "powerCON TRUE1 TOP Large", "female", "black", "locking power-in cable connector for large cable, IP65", [10.0, 16.0], True),
        ("NAC3MX-W-TOP-L", "powerCON TRUE1 TOP Large", "male", "black", "locking power-out cable connector for large cable, IP65", [10.0, 16.0], True),
    ]
    for mpn, series, gender, bushing, desc, cable_od, true1 in catalog:
        if true1:
            profile = powercon_true1_profile(large_cable=mpn.endswith("-L"))
            tools = ["T8 Torx driver", "13 mm wrench"]
        else:
            profile = powercon_classic_profile()
            tools = ["3 mm flat-blade screwdriver"]
        yield {
            "mpn": mpn,
            "family": "powerCON",
            "series": series,
            "poles": 3,
            "gender": gender,
            "finish": "",
            "palette": "plastic",
            "bushing": bushing,
            "housing_material": "glass-reinforced polyamide",
            "termination": "screw terminal",
            "cable_od_mm": cable_od,
            "contact_names": ["L", "N", "PE"],
            "tools": tools,
            "profile": profile,
            "source": POWERCON_SOURCE,
            "product_desc": desc,
            "notes": ["Connector with breaking capacity: may be mated or unmated under load."]
            if true1
            else ["Do not mate or unmate under load; powerCON 20 A is not a connector with breaking capacity."],
        }


def _phone_variants():
    catalog = []
    for poles, poles_name in ((2, "mono (TS)"), (3, "stereo (TRS)")):
        finishes = ["", "B", "BAG"] + (["WT"] if poles == 2 else [])
        for finish in finishes:
            suffix = f"-{finish}" if finish else ""
            catalog.append(
                (
                    f"NP{poles}X{suffix}",
                    "PX",
                    poles,
                    finish,
                    f"1/4\" phone plug, {poles_name}",
                    [4.0, 7.0],
                    14.5,
                    9.0,
                )
            )
        catalog.append(
            (
                f"NP{poles}XL",
                "jumboPLUG",
                poles,
                "",
                f"1/4\" jumboPLUG for thick instrument and loudspeaker cable, {poles_name}",
                [4.0, 10.0],
                17.0,
                12.0,
            )
        )
    catalog.append(
        (
            "NP2X-AU-SILENT",
            "silentPLUG",
            2,
            "",
            '1/4" silentPLUG with muting switch, mono (TS)',
            [4.0, 7.0],
            14.5,
            9.0,
        )
    )
    for mpn, series, poles, finish, desc, cable_od, handle_dia, bushing_dia in catalog:
        plating = "Au" if mpn.endswith("-AU-SILENT") else contact_plating("TRS", finish)
        yield {
            "mpn": mpn,
            "family": "TRS",
            "series": series,
            "poles": poles,
            "gender": "male",
            "finish": finish,
            "palette": HOUSING_PALETTES[finish],
            "bushing": "white" if finish == "WT" else "black",
            "housing_material": "zinc diecast (ZnAl4Cu1)",
            "termination": "solder cup",
            "cable_od_mm": cable_od,
            "contact_names": ["T", "R", "S"] if poles == 3 else ["T", "S"],
            "tools": ["Soldering iron"],
            "profile": phone_plug_profile(poles, handle_dia=handle_dia, bushing_dia=bushing_dia),
            "source": PHONE_SOURCE,
            "product_desc": desc,
            "plating_override": plating,
            "notes": ["Conforms to IEC 60603-11 / EIA RS-453."],
        }


def _speakon_variants():
    catalog = [
        ("NL2FX", "X", 2, "female", "", "blue", "cable connector with chuck, intermates with 4 pole chassis on +1/-1", [6.0, 10.0], 25.0, 74.0, 11.0, "plastic"),
        ("NL4FX", "X", 4, "female", "", "black", "cable connector with chuck", [7.0, 14.5], 25.0, 74.0, 11.0, "plastic"),
        ("NL4FX-2", "X", 4, "female", "", "red", "cable connector with chuck and red bushing", [7.0, 14.5], 25.0, 74.0, 11.0, "plastic"),
        ("NL4FX-4", "X", 4, "female", "", "yellow", "cable connector with chuck and yellow bushing", [7.0, 14.5], 25.0, 74.0, 11.0, "plastic"),
        ("NL4FX-5", "X", 4, "female", "", "green", "cable connector with chuck and green bushing", [7.0, 14.5], 25.0, 74.0, 11.0, "plastic"),
        ("NL4FX-9", "X", 4, "female", "", "white", "cable connector with chuck and white bushing", [7.0, 14.5], 25.0, 74.0, 11.0, "plastic"),
        ("NL4FC", "FC", 4, "female", "", "black", "cable connector with latch lock", [8.0, 20.0], 26.0, 78.0, 13.0, "plastic"),
        ("NL8FC", "FC", 8, "female", "", "black", "cable connector with latch lock", [8.0, 20.0], 26.0, 78.0, 13.0, "plastic"),
        ("NLT4FX", "STX", 4, "female", "", "black", "female cable connector, metal housing, chuck and bushing", [8.0, 16.0], 26.0, 78.0, 13.0, None),
        ("NLT4FX-BAG", "STX", 4, "female", "BAG", "black", "female cable connector, metal housing, chuck and bushing", [8.0, 16.0], 26.0, 78.0, 13.0, None),
        ("NLT4MX", "STX", 4, "male", "", "black", "male cable connector, metal housing, chuck and bushing", [8.0, 16.0], 26.0, 78.0, 13.0, None),
        ("NLT4MX-BAG", "STX", 4, "male", "BAG", "black", "male cable connector, metal housing, chuck and bushing", [8.0, 16.0], 26.0, 78.0, 13.0, None),
        ("NLT8FX", "STX", 8, "female", "", "black", "female cable connector, metal housing, chuck and bushing", [8.0, 20.0], 30.0, 82.0, 15.0, None),
        ("NLT8FX-BAG", "STX", 8, "female", "BAG", "black", "female cable connector, metal housing, chuck and bushing", [8.0, 20.0], 30.0, 82.0, 15.0, None),
        ("NLT8MX-BAG", "STX", 8, "male", "BAG", "black", "male cable connector, metal housing, chuck and bushing", [8.0, 20.0], 30.0, 82.0, 15.0, None),
    ]
    for (
        mpn,
        series,
        poles,
        gender,
        finish,
        bushing,
        desc,
        cable_od,
        body_dia,
        total_length,
        bushing_dia,
        palette_override,
    ) in catalog:
        contacts = []
        for pair in range(1, poles // 2 + 1):
            contacts.append(f"{pair}+")
            contacts.append(f"{pair}-")
        tools = ["HTFAC hand tool"] if series == "FC" else ["2.5 mm flat-blade screwdriver"]
        yield {
            "mpn": mpn,
            "family": "speakON",
            "series": series,
            "poles": poles,
            "gender": gender,
            "finish": finish,
            "palette": palette_override or HOUSING_PALETTES[finish],
            "bushing": bushing,
            "housing_material": "glass-reinforced polyamide"
            if palette_override == "plastic"
            else "zinc diecast (ZnAl4Cu1)",
            "termination": "screw terminal",
            "cable_od_mm": cable_od,
            "contact_names": contacts,
            "tools": tools,
            "profile": speakon_profile(body_dia, total_length, bushing_dia),
            "source": SPEAKON_SOURCE,
            "product_desc": desc,
            "notes": [],
        }


def iter_variants(families=None):
    builders = {
        "XLR": _xlr_variants,
        "etherCON": _ethercon_variants,
        "powerCON": _powercon_variants,
        "TRS": _phone_variants,
        "speakON": _speakon_variants,
    }
    for family, builder in builders.items():
        if families and family not in families:
            continue
        for variant in builder():
            yield attach_iconic_tab(variant)


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------
def _segment_fill(segment, variant, pal):
    role = segment["role"]
    if role == "bushing":
        return BUSHING_COLORS.get(variant["bushing"], BUSHING_COLORS["black"])
    if role == "grip":
        return pal["dark"]
    if role == "latch":
        return pal["rim"]
    if role == "barrel":
        return pal["light"]
    if role == "contact":
        plating = variant.get("plating_override") or contact_plating(
            variant["family"], variant["finish"]
        )
        return PLATING_COLORS[plating]
    if role == "insulator":
        return INSULATOR_COLOR
    return pal["body"]


def connector_svg(variant):
    """Side-view drawing. Origin on the cable-entry face; +X to the mating face."""
    part_number = variant["mpn"]
    profile = variant["profile"]
    pal = palette_for(variant["palette"])
    parts = [
        f'<!-- {variant["family"]} {variant["series"]} envelope from {variant["source"]} -->',
        "<!-- Cable exit is embedded: chuck-type strain relief is part of this part number -->",
    ]

    x = px_mm(ORIGIN_FROM_REAR_MM)
    for segment in profile:
        length = px_mm(segment["length"])
        r_rear = px_mm(segment["dia"] / 2.0)
        r_front = px_mm(segment.get("dia_front", segment["dia"]) / 2.0)
        fill = _segment_fill(segment, variant, pal)
        if abs(r_front - r_rear) < 1e-9:
            parts.append(_rect(x, -r_rear, length, 2.0 * r_rear, fill=fill, stroke=None))
            if segment.get("knurl"):
                parts.extend(
                    _diamond_hatch(x, -r_rear, length, 2.0 * r_rear, pal["knurl"])
                )
            if segment.get("ribs"):
                rib_color = (
                    pal["knurl"] if segment["role"] != "bushing" else "#4A4C4F"
                )
                parts.extend(
                    _axial_ribs(
                        x,
                        -r_rear,
                        length,
                        2.0 * r_rear,
                        rib_color,
                        segment["ribs"],
                    )
                )
            if segment.get("grooves"):
                n_g = segment["grooves"]
                groove_span = min(length * 0.28, px_mm(8.0))
                if segment["role"] == "bushing":
                    groove_span = length
                    groove_color = "#4A4C4F"
                else:
                    groove_color = pal["rim"]
                for i in range(n_g):
                    gx = x + (i + 1) * groove_span / (n_g + 1)
                    parts.append(
                        _line(
                            gx,
                            -r_rear,
                            gx,
                            r_rear,
                            stroke=groove_color,
                            stroke_width=1.1,
                        )
                    )
        else:
            parts.append(
                _poly(
                    [
                        (x, -r_rear),
                        (x + length, -r_front),
                        (x + length, r_front),
                        (x, r_rear),
                    ],
                    fill=fill,
                    stroke=None,
                )
            )
        x += length

    tab = variant.get("tab")
    if tab:
        parts.extend(tab_drawing_parts(tab, pal))

    outline = [
        (px_mm(px), -px_mm(py))
        for px, py in silhouette_closed_mm(profile_stations(profile), tab)[:-1]
    ]
    parts.append(_poly(outline, fill="none"))
    csys = flagnote_csys_children(profile, part_number, tab)

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="400" height="400">
<g id="{part_number}-drawing-contents-start">
{chr(10).join(parts)}
</g>
<g id="{part_number}-drawing-contents-end">
</g>
{_csys_overlay_svg(csys)}
</svg>'''


def write_part_step(rev_dir, variant):
    part_number = variant["mpn"]
    path = os.path.join(rev_dir, f"{part_number}-rev{REVISION}-model.step")
    stations = profile_stations(variant["profile"])
    tab = variant.get("tab")
    cavity = variant.get("cavity")
    window = tab if tab and tab.get("style") == "window" else None
    description = f"Neutrik {variant['family']} low-fidelity envelope"
    if tab and window is None:
        try:
            _write_revolution_with_tab_step(path, part_number, stations, tab)
            return path
        except ImportError:
            pass
    if cavity or window:
        try:
            _write_revolution_with_cavity_step(
                path, part_number, stations, cavity, window
            )
            return path
        except ImportError:
            pass
    step_utils.write_revolution_step(path, part_number, stations, description=description)
    return path


def _ocp_positive_solid(stations):
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    body = step_utils._ocp_revolution_solid(stations)
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(body, props)
    if props.Mass() < 0:
        body.Reverse()
    return body


def _ocp_cut(body, tool, label):
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut

    op = BRepAlgoAPI_Cut(body, tool)
    op.SetFuzzyValue(0.05)
    op.Build()
    cut = op.Shape()
    if not op.IsDone() or cut.IsNull():
        raise RuntimeError(f"{label} cut failed")
    return cut


def _window_slot_tool(tab, cavity):
    """Box through the +Z wall: latch window toward the drawing camera."""
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt

    x0 = float(tab["x_mm"])
    length = float(tab["length_mm"])
    width = float(tab["width_mm"])
    outer_r = float(tab["shell_radius_mm"])
    inner_r = float(cavity["dia_mm"]) / 2.0 if cavity else max(0.5, outer_r - 2.0)
    overlap = 0.8
    overshoot = 1.5
    z0 = inner_r - overlap
    return BRepPrimAPI_MakeBox(
        gp_Pnt(x0, -width / 2.0, z0),
        length,
        width,
        (outer_r + overshoot) - z0,
    ).Shape()


def _write_revolution_with_cavity_step(path, part_number, stations, cavity, window=None):
    """Revolve about +X, cut the mating bore, then punch the latch window."""
    body = _ocp_positive_solid(stations)
    if cavity:
        x_face = float(stations[-1][0])
        depth = float(cavity["depth_mm"])
        radius = float(cavity["dia_mm"]) / 2.0
        tool = step_utils._ocp_cylinder(
            (x_face - depth, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            radius,
            depth + 1.0,
        )
        body = _ocp_cut(body, tool, f"{part_number} cavity")
    if window:
        body = _ocp_cut(body, _window_slot_tool(window, cavity), f"{part_number} window")
    step_utils._ocp_write_shape(body, path, part_number)
    return path


def _write_revolution_with_tab_step(path, part_number, stations, tab):
    """Revolve the body about +X and add the latch tongue as a box on +Z.

    +Z is toward the drawing viewer, so the tab faces the camera. OpenCascade
    fuzzy-fuse against the revolved envelope can drop the box, so the tab is
    glued as a compound when the boolean does not grow the bbox.
    """
    from OCP.BRep import BRep_Builder
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    from OCP.TopoDS import TopoDS_Compound
    from OCP.gp import gp_Pnt

    body = step_utils._ocp_revolution_solid(stations)
    x0 = float(tab["x_mm"])
    length = float(tab["length_mm"])
    height = float(tab["height_mm"])
    width = float(tab["width_mm"])
    radius = float(tab["shell_radius_mm"])
    embed = min(3.0, radius * 0.4)
    box = BRepPrimAPI_MakeBox(
        gp_Pnt(x0, -width / 2.0, radius - embed),
        length,
        width,
        height + embed,
    ).Shape()

    def _zmax(shape):
        bnd = Bnd_Box()
        BRepBndLib.Add_s(shape, bnd)
        return bnd.Get()[5]

    op = BRepAlgoAPI_Fuse(body, box)
    op.Build()
    fused = op.Shape()
    if op.IsDone() and not fused.IsNull() and _zmax(fused) > _zmax(body) + 0.5:
        shape = fused
    else:
        builder = BRep_Builder()
        shape = TopoDS_Compound()
        builder.MakeCompound(shape)
        builder.Add(shape, body)
        builder.Add(shape, box)
    step_utils._ocp_write_shape(shape, path, part_number)
    return path


# ---------------------------------------------------------------------------
# Attributes
# ---------------------------------------------------------------------------
def part_description(variant):
    bits = [f"NEUTRIK {variant['family'].upper()} CABLE CONNECTOR"]
    if variant["family"] != "powerCON":
        bits.append(f"{variant['poles']} POLE")
    bits.append(variant["gender"].upper())
    bits.append(HOUSING_NAMES[variant["finish"]].upper())
    return ", ".join(bits)


def compile_part_attributes(variant):
    plating = variant.get("plating_override") or contact_plating(
        variant["family"], variant["finish"]
    )
    contacts = [
        {"name": name, "size": variant["termination"]}
        for name in variant["contact_names"]
    ]
    od_min, od_max = variant["cable_od_mm"]
    build_notes = [_cable_note(od_min, od_max), EMBEDDED_NOTE] + variant.get("notes", [])

    return {
        "tools": list(variant["tools"]),
        "build_notes": build_notes,
        "csys_children": flagnote_csys_children(
            variant["profile"], variant["mpn"], variant.get("tab")
        ),
        "contacts": contacts,
        "mfg": MANUFACTURER,
        "family": variant["family"],
        "series": variant["series"],
        "poles": variant["poles"],
        "gender": variant["gender"],
        "termination": variant["termination"],
        "finish": finish_name(variant["family"], variant["finish"]),
        "contact_plating": plating,
        "housing_material": variant["housing_material"],
        "bushing_color": variant["bushing"],
        "cable_od_mm": variant["cable_od_mm"],
        "overall_length_mm": round(profile_length_mm(variant["profile"]), 2),
        "max_diameter_mm": round(
            max(
                max(s["dia"], s.get("dia_front", s["dia"])) for s in variant["profile"]
            ),
            2,
        ),
        "datasheet": variant["source"],
    }


# ---------------------------------------------------------------------------
# Batch driver
# ---------------------------------------------------------------------------
def _progress_bar(done, total, width=25):
    """Return a text progress bar like: [ x x x . . . ] (35%)."""
    if total <= 0:
        filled = width
        pct = 100
    else:
        filled = min(width, max(0, round(width * done / total)))
        pct = round(100.0 * done / total)
    cells = ["x"] * filled + ["."] * (width - filled)
    return "[ " + " ".join(cells) + f" ] ({pct}%)"


def revision_history_row(variant):
    return {
        "product": state.product,
        "mfg": MANUFACTURER,
        "pn": variant["mpn"],
        "rev": REVISION,
        "desc": part_description(variant),
        "status": "",
        "datestarted": DATE_STARTED,
        "library_repo": LIBRARY_REPO,
        "library_subpath": LIBRARY_SUBPATH,
    }


def main(step_only=False, svg_only=False, families=None, build=True):
    state.set_rev(REVISION)
    state.set_product("part")

    variants = list(iter_variants(families))
    total = len(variants)
    family_dir = os.path.dirname(os.path.abspath(__file__))

    for i, variant in enumerate(variants, start=1):
        part_number = variant["mpn"]
        print("Preparing part number: ", part_number)

        part_dir = os.path.join(family_dir, part_number)
        os.makedirs(part_dir, exist_ok=True)
        rev_dir = os.path.join(part_dir, f"{part_number}-rev{REVISION}")
        revision_history_csv_path = os.path.join(
            part_dir, f"{part_number}-revision_history.tsv"
        )
        attributes = compile_part_attributes(variant)
        json_path = os.path.join(rev_dir, f"{part_number}-rev{REVISION}-attributes.json")
        svg_path = os.path.join(rev_dir, f"{part_number}-rev{REVISION}-drawing.svg")

        if step_only or svg_only:
            os.makedirs(rev_dir, exist_ok=True)
            if not os.path.exists(revision_history_csv_path):
                rev_history.part_family_append(
                    revision_history_row(variant), revision_history_csv_path
                )
            with open(json_path, "w") as f:
                json.dump(attributes, f, indent=2)
            if svg_only:
                with open(svg_path, "w") as f:
                    f.write(connector_svg(variant))
            if step_only:
                write_part_step(rev_dir, variant)
            print(_progress_bar(i, total))
            continue

        # UPDATE THE REVISION HISTORY FILE
        rev_history.part_family_append(
            revision_history_row(variant), revision_history_csv_path
        )

        # CLEAN AND MAKE THE REVISION FOLDER
        if os.path.exists(rev_dir):
            for item in os.listdir(rev_dir):
                item_path = os.path.join(rev_dir, item)
                if os.path.isfile(item_path):
                    os.remove(item_path)
        else:
            os.makedirs(rev_dir)

        # WRITE THE ATTRIBUTES JSON
        with open(json_path, "w") as f:
            json.dump(attributes, f, indent=2)

        # GENERATE THE SVG
        with open(svg_path, "w") as f:
            f.write(connector_svg(variant))

        write_part_step(rev_dir, variant)

        # RENDER THE PART
        if build:
            subprocess.run(["harnice", "-b"], cwd=rev_dir, check=True)
            if delete_pngs:
                for item in os.listdir(rev_dir):
                    if item.endswith(".png"):
                        os.remove(os.path.join(rev_dir, item))

        print(_progress_bar(i, total))

    print(f"Finished rendering all {total} parts in family.")


FAMILY_FLAGS = {
    "--xlr-only": "XLR",
    "--ethercon-only": "etherCON",
    "--powercon-only": "powerCON",
    "--trs-only": "TRS",
    "--speakon-only": "speakON",
}

if __name__ == "__main__":
    selected = [family for flag, family in FAMILY_FLAGS.items() if flag in sys.argv]
    main(
        step_only="--step-only" in sys.argv,
        svg_only="--svg-only" in sys.argv,
        families=selected or None,
        build="--no-build" not in sys.argv,
    )
