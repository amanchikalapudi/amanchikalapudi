#!/usr/bin/env python3
"""Render data/contributions.json as a dark, animated, terminal-style SVG.

Animation is SMIL-only (<animate>/<animateTransform>), on purpose:
CSS @keyframes inside an <svg> do not run once GitHub's camo image proxy
re-serves the file as a plain <img>, so the whole thing would render as a
frozen (or blank) frame. SMIL animation is intrinsic to the SVG document and
plays regardless of how the image is embedded.

Two hard rules baked into every animated element below:
  1. An element's un-animated attribute values are its *finished* visible
     state. If a browser ever paints the very first tick of a cached SMIL
     timeline (t=0) before advancing it, what's on screen must already look
     complete/plausible, never blank.
  2. Every <animate>/<animateTransform> begins at "0.01s", never "0". A
     literal 0 start can coincide exactly with a frozen/paused t=0 frame; a
     hair after that guarantees the timeline is observed to be running.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = REPO_ROOT / "data" / "contributions.json"
OUTPUT_PATH = REPO_ROOT / "assets" / "heatmap.svg"

# ---- palette (GitHub dark theme) -------------------------------------------------
BG = "#0d1117"
PANEL_BORDER = "#30363d"
TITLEBAR_BG = "#161b22"
TEXT_DIM = "#8b949e"
TEXT_BRIGHT = "#c9d1d9"
GREEN_BRIGHT = "#39d353"
GREEN_FLASH = "#7CFFB2"
LEVEL_COLORS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
DOT_RED, DOT_YELLOW, DOT_GREEN = "#ff5f56", "#ffbd2e", "#27c93f"

RAIN_CHARSET = "01ABCDEFGHIJKLMNOPQRSTUVWXYZ$%#@*+=~"

MONTH_ABBR = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]

# ---- layout ------------------------------------------------------------------
CELL = 10
GAP = 3
PITCH = CELL + GAP
LEFT_MARGIN = 32
RIGHT_MARGIN = 16
TITLEBAR_H = 28
MONTH_LABEL_H = 16
GRID_TOP_PAD = 4
FOOTER_H = 34
BOTTOM_PAD = 14


def load_data() -> dict:
    return json.loads(DATA_PATH.read_text())


def month_labels(days: list[dict]) -> list[tuple[int, str]]:
    """Return (week_index, abbreviated month) for each month transition."""
    by_week: dict[int, str] = {}
    for d in days:
        by_week.setdefault(d["week"], d["date"])
    labels = []
    last_month = None
    for week in sorted(by_week):
        month = int(by_week[week][5:7])
        if month != last_month:
            labels.append((week, MONTH_ABBR[month - 1]))
            last_month = month
    return labels


def rain_column_svg(rng: random.Random, x: float, height: float, line_h: float, clip_h: float) -> str:
    """One vertical stream of glyphs, tall enough to loop seamlessly."""
    n = int((clip_h * 2) // line_h) + 2
    parts = [f'<text x="0" y="0" font-family="SFMono-Regular,Consolas,monospace" font-size="{line_h - 3:.0f}" text-anchor="middle">']
    for i in range(n):
        ch = xml_escape(rng.choice(RAIN_CHARSET))
        bright = (i % 6 == 0)
        fill = GREEN_BRIGHT if bright else "#1c6b3c"
        opacity = "0.9" if bright else "0.4"
        dy = f'{line_h:.0f}' if i else "0"
        parts.append(f'<tspan x="0" dy="{dy}" fill="{fill}" opacity="{opacity}">{ch}</tspan>')
    parts.append("</text>")
    return (
        f'<g transform="translate({x:.1f},0)">'
        + "".join(parts)
        + f'{rain_translate_anim(line_h, n)}'
        + "</g>"
    )


def rain_translate_anim(line_h: float, n: int) -> str:
    """Shared discrete-step clock reused, unchanged, by every rain column.

    calcMode="discrete" jumps between values with no interpolation, so a
    panel full of these columns costs one repaint-worth of work per step
    instead of a continuously-repainted smooth translate on dozens of
    elements.
    """
    steps = 12
    values = ";".join(f"0,{(line_h * n / steps) * i:.1f}" for i in range(steps))
    values = f"0,0;{values};0,0"
    keytimes = ";".join(f"{i / (steps + 1):.4f}" for i in range(steps + 2))
    return (
        '<animateTransform attributeName="transform" type="translate" attributeType="XML" '
        f'additive="sum" calcMode="discrete" values="{values}" keyTimes="{keytimes}" '
        'dur="6s" begin="0.01s" repeatCount="indefinite"/>'
    )


def matrix_rain(seed: int, x: int, y: int, w: int, h: int, col_spacing: int = 14, line_h: int = 14) -> str:
    rng = random.Random(seed)
    clip_id = f"clip-{seed}"
    cols = max(1, w // col_spacing)
    body = []
    for i in range(cols):
        cx = i * col_spacing + col_spacing / 2
        body.append(rain_column_svg(rng, cx, h, line_h, h))
    return (
        f'<clipPath id="{clip_id}"><rect x="0" y="0" width="{w}" height="{h}"/></clipPath>'
        f'<g transform="translate({x},{y})" clip-path="url(#{clip_id})" opacity="0.5">'
        + "".join(body)
        + "</g>"
    )


def titlebar(width: int, title: str) -> str:
    cy = TITLEBAR_H / 2
    dots = "".join(
        f'<circle cx="{16 + i * 18}" cy="{cy:.1f}" r="5.5" fill="{color}"/>'
        for i, color in enumerate((DOT_RED, DOT_YELLOW, DOT_GREEN))
    )
    return (
        f'<rect x="0" y="0" width="{width}" height="{TITLEBAR_H}" fill="{TITLEBAR_BG}" rx="10"/>'
        f'<rect x="0" y="{TITLEBAR_H / 2:.1f}" width="{width}" height="{TITLEBAR_H / 2:.1f}" fill="{TITLEBAR_BG}"/>'
        f"{dots}"
        f'<text x="{width / 2:.1f}" y="{cy + 4:.1f}" text-anchor="middle" '
        f'font-family="SFMono-Regular,Consolas,monospace" font-size="12" fill="{TEXT_DIM}">{xml_escape(title)}</text>'
    )


def cell_svg(rng: random.Random, cx: float, cy: float, level: int, count: int, week: int, weekday: int, is_active: bool) -> str:
    color = LEVEL_COLORS[level]
    reveal_begin = 0.01 + week * 0.028 + weekday * 0.010
    rx = 2.5
    half = CELL / 2

    reveal_anim = (
        f'<animate attributeName="opacity" values="0;0;1" keyTimes="0;0.02;1" '
        f'dur="0.5s" begin="{reveal_begin:.3f}s" fill="freeze"/>'
    )

    if not is_active:
        # Empty day: participates in the left-to-right reveal wave only.
        return (
            f'<g transform="translate({cx:.1f},{cy:.1f})">'
            f'<rect x="{-half:.1f}" y="{-half:.1f}" width="{CELL}" height="{CELL}" rx="{rx}" '
            f'fill="{color}" opacity="1">{reveal_anim}</rect>'
            f"</g>"
        )

    pop_begin = reveal_begin
    flash_dur = 0.55
    shimmer_dur = 3.2 + rng.random() * 2.6
    shimmer_begin = 0.01 + rng.random() * 4.0
    do_twinkle = rng.random() < 0.4
    twinkle_dur = 4.5 + rng.random() * 3.5
    twinkle_begin = 0.01 + rng.random() * 3.0

    twinkle_svg = ""
    if do_twinkle:
        twinkle_svg = (
            f'<circle r="1.6" fill="#ffffff" opacity="0">'
            f'<animate attributeName="opacity" values="0;0;0;0.95;0;0" '
            f'keyTimes="0;0.01;0.9;0.94;0.98;1" dur="{twinkle_dur:.2f}s" '
            f'begin="{twinkle_begin:.2f}s" repeatCount="indefinite"/>'
            f"</circle>"
        )

    title = f"{count} contribution{'s' if count != 1 else ''}"

    return (
        f'<g transform="translate({cx:.1f},{cy:.1f})">'
        f'<title>{xml_escape(title)}</title>'
        f'<g transform="scale(1)">'
        f'<animateTransform attributeName="transform" type="scale" attributeType="XML" '
        f'values="0.3;0.3;1.35;0.92;1" keyTimes="0;0.15;0.62;0.85;1" '
        f'dur="0.6s" begin="{pop_begin:.3f}s" fill="freeze"/>'
        f'<g opacity="1">{reveal_anim}'
        f'<rect x="{-half:.1f}" y="{-half:.1f}" width="{CELL}" height="{CELL}" rx="{rx}" fill="{color}">'
        f'<animate attributeName="fill" values="{color};{GREEN_FLASH};{color}" keyTimes="0;0.5;1" '
        f'dur="{flash_dur}s" begin="{pop_begin:.3f}s" fill="freeze"/>'
        f"</rect>"
        f'<rect x="{-half:.1f}" y="{-half:.1f}" width="{CELL}" height="{CELL}" rx="{rx}" fill="#ffffff" opacity="0">'
        f'<animate attributeName="opacity" values="0;0;0.32;0" keyTimes="0;0.4;0.55;1" '
        f'dur="{shimmer_dur:.2f}s" begin="{shimmer_begin:.2f}s" repeatCount="indefinite"/>'
        f"</rect>"
        f"{twinkle_svg}"
        f"</g></g></g>"
    )


def scan_beam(grid_w: int, grid_h: int) -> str:
    grad_id = "scanGrad"
    return (
        f'<defs><linearGradient id="{grad_id}" x1="0" y1="0" x2="1" y2="0">'
        f'<stop offset="0%" stop-color="{GREEN_BRIGHT}" stop-opacity="0"/>'
        f'<stop offset="50%" stop-color="{GREEN_BRIGHT}" stop-opacity="0.35"/>'
        f'<stop offset="100%" stop-color="{GREEN_BRIGHT}" stop-opacity="0"/>'
        f"</linearGradient></defs>"
        f'<rect x="0" y="0" width="46" height="{grid_h}" fill="url(#{grad_id})">'
        f'<animateTransform attributeName="transform" type="translate" attributeType="XML" '
        f'values="-46,0;-46,0;{grid_w + 46},0;{grid_w + 46},0" keyTimes="0;0.02;0.6;1" '
        f'dur="9s" begin="0.01s" repeatCount="indefinite"/>'
        f"</rect>"
    )


def typed_total(x: int, y: int, text: str) -> str:
    font_size = 13
    char_w = font_size * 0.62
    n = len(text)
    steps = max(1, min(n, 30))
    # breakpoints[0] == 0, breakpoints[-1] == n, length steps + 1.
    breakpoints = [round(n * i / steps) for i in range(steps + 1)]

    # Two-entry hold at width 0 (the "values=0;0;..." reveal pattern), then
    # one entry per remaining breakpoint. Lengths of values/keyTimes must
    # match exactly for SMIL: 2 + steps each.
    values = [0.0, 0.0] + [bp * char_w for bp in breakpoints[1:]]
    keytimes = [0.0, 0.02] + [0.02 + (1 - 0.02) * k / steps for k in range(1, steps + 1)]
    keytimes[-1] = 1.0

    values_s = ";".join(f"{v:.1f}" for v in values)
    keytimes_s = ";".join(f"{k:.4f}" for k in keytimes)
    full_w = n * char_w
    clip_id = "typeClip"
    cursor_x = x + full_w + 6

    return (
        f'<clipPath id="{clip_id}"><rect x="{x}" y="{y - font_size}" width="{full_w:.1f}" height="{font_size + 8}">'
        f'<animate attributeName="width" values="{values_s}" keyTimes="{keytimes_s}" '
        f'calcMode="discrete" dur="2.4s" begin="0.01s" fill="freeze"/>'
        f"</rect></clipPath>"
        f'<text x="{x}" y="{y}" clip-path="url(#{clip_id})" '
        f'font-family="SFMono-Regular,Consolas,monospace" font-size="{font_size}" '
        f'fill="{TEXT_BRIGHT}">{xml_escape(text)}</text>'
        f'<rect x="{cursor_x:.1f}" y="{y - font_size + 2:.1f}" width="7" height="{font_size + 2}" fill="{GREEN_BRIGHT}" opacity="1">'
        f'<animate attributeName="opacity" values="1;1;0;0;1" keyTimes="0;0.4;0.5;0.9;1" '
        f'dur="1s" begin="0.01s" repeatCount="indefinite"/>'
        f"</rect>"
    )


def legend(x: int, y: int) -> str:
    parts = [f'<text x="{x}" y="{y + 4}" font-family="SFMono-Regular,Consolas,monospace" font-size="11" fill="{TEXT_DIM}">Less</text>']
    lx = x + 34
    for i, color in enumerate(LEVEL_COLORS):
        parts.append(f'<rect x="{lx + i * 14}" y="{y - 8}" width="10" height="10" rx="2.5" fill="{color}"/>')
    parts.append(
        f'<text x="{lx + len(LEVEL_COLORS) * 14 + 6}" y="{y + 4}" '
        f'font-family="SFMono-Regular,Consolas,monospace" font-size="11" fill="{TEXT_DIM}">More</text>'
    )
    return "".join(parts)


def build_svg(data: dict) -> str:
    days = data["days"]
    weeks = data["weeks"]
    total = data["total"]
    username = data["username"]

    grid_w = weeks * PITCH - GAP
    width = LEFT_MARGIN + grid_w + RIGHT_MARGIN
    height = TITLEBAR_H + MONTH_LABEL_H + GRID_TOP_PAD + 7 * PITCH - GAP + FOOTER_H + BOTTOM_PAD

    grid_top = TITLEBAR_H + MONTH_LABEL_H + GRID_TOP_PAD
    rain_h = height - TITLEBAR_H

    rng = random.Random(1337)

    svg = []
    svg.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{xml_escape(username)} contribution activity">'
    )
    svg.append(f'<rect x="0" y="0" width="{width}" height="{height}" rx="10" fill="{BG}"/>')
    svg.append(f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="10" fill="none" stroke="{PANEL_BORDER}"/>')

    svg.append(titlebar(width, f"{username} — contributions.sh"))
    svg.append(matrix_rain(seed=42, x=0, y=TITLEBAR_H, w=width, h=rain_h))

    # weekday labels (Mon/Wed/Fri)
    for row, label in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        ly = grid_top + row * PITCH + CELL - 1
        svg.append(
            f'<text x="{LEFT_MARGIN - 8}" y="{ly}" text-anchor="end" '
            f'font-family="SFMono-Regular,Consolas,monospace" font-size="9" fill="{TEXT_DIM}">{label}</text>'
        )

    # month labels
    for week, label in month_labels(days):
        lx = LEFT_MARGIN + week * PITCH
        svg.append(
            f'<text x="{lx}" y="{TITLEBAR_H + MONTH_LABEL_H - 4}" '
            f'font-family="SFMono-Regular,Consolas,monospace" font-size="10" fill="{TEXT_DIM}">{label}</text>'
        )

    # grid cells
    for d in days:
        cx = LEFT_MARGIN + d["week"] * PITCH + CELL / 2
        cy = grid_top + d["weekday"] * PITCH + CELL / 2
        svg.append(cell_svg(rng, cx, cy, d["level"], d["count"], d["week"], d["weekday"], d["count"] > 0))

    # ghost scan beam sweeping the grid
    svg.append(f'<g transform="translate({LEFT_MARGIN},{grid_top})">' + scan_beam(grid_w, 7 * PITCH - GAP) + "</g>")

    # footer: typed total + legend
    footer_y = grid_top + (7 * PITCH - GAP) + 26
    svg.append(typed_total(LEFT_MARGIN, footer_y, f"{total} contributions in the last year"))
    svg.append(legend(width - RIGHT_MARGIN - 150, footer_y))

    svg.append("</svg>")
    return "".join(svg)


def main() -> int:
    data = load_data()
    svg = build_svg(data)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(svg)
    print(f"wrote {OUTPUT_PATH} ({len(svg)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
