#!/usr/bin/env python3
"""Render a neofetch-style "who am I" info card as a dark, animated SVG.

Same SMIL-only animation rules as scripts/render_heatmap_svg.py:
  - un-animated attributes are the finished, visible state
  - every <animate>/<animateTransform> begins at "0.01s", never "0"
  - reveals hide content only while an animation is actively running

The card's pixel height is fixed to exactly match the meme gif's *display*
height (see README table) so the two columns line up. If you change the
gif's display height, update CARD_HEIGHT to match.
"""
from __future__ import annotations

import random
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = REPO_ROOT / "assets" / "info_card.svg"

# Must match the meme gif's display height in README.md exactly.
CARD_WIDTH = 420
CARD_HEIGHT = 380

BG = "#0d1117"
PANEL_BORDER = "#30363d"
TITLEBAR_BG = "#161b22"
TEXT_DIM = "#8b949e"
TEXT_BRIGHT = "#c9d1d9"
GREEN_BRIGHT = "#39d353"
ACCENT = "#58a6ff"
DOT_RED, DOT_YELLOW, DOT_GREEN = "#ff5f56", "#ffbd2e", "#27c93f"

RAIN_CHARSET = "01ABCDEFGHIJKLMNOPQRSTUVWXYZ$%#@*+=~"
SWATCHES = ["#0d1117", "#ff5f56", "#39d353", "#ffbd2e", "#58a6ff", "#bc8cff", "#39c5cf", "#c9d1d9"]

TITLEBAR_H = 28

FIELDS = [
    ("OS", "Raspberry Pi OS (SIP Lab)"),
    ("Host", "Voice/UC Engineer, 8+ yrs"),
    ("Kernel", "SIP 2.0 / RTP/SRTP"),
    ("Uptime", "24x7, 10k+ users"),
    ("Shell", "zsh"),
    ("Stack", "Python, Ansible, Docker"),
    ("Ships", "Carrier-grade voice infra"),
    ("Socials", "GitHub, LinkedIn, Email"),
]

USERNAME = "amanchikalapudi"
HOST = "github"


def rain_column_svg(rng: random.Random, x: float, line_h: float, clip_h: float) -> str:
    n = int((clip_h * 2) // line_h) + 2
    parts = [f'<text x="0" y="0" font-family="SFMono-Regular,Consolas,monospace" font-size="{line_h - 3:.0f}" text-anchor="middle">']
    for i in range(n):
        ch = xml_escape(rng.choice(RAIN_CHARSET))
        bright = (i % 6 == 0)
        fill = GREEN_BRIGHT if bright else "#1c6b3c"
        opacity = "0.9" if bright else "0.4"
        dy = f"{line_h:.0f}" if i else "0"
        parts.append(f'<tspan x="0" dy="{dy}" fill="{fill}" opacity="{opacity}">{ch}</tspan>')
    parts.append("</text>")

    steps = 12
    values = ";".join(f"0,{(line_h * n / steps) * i:.1f}" for i in range(steps))
    values = f"0,0;{values};0,0"
    keytimes = ";".join(f"{i / (steps + 1):.4f}" for i in range(steps + 2))
    anim = (
        '<animateTransform attributeName="transform" type="translate" attributeType="XML" '
        f'additive="sum" calcMode="discrete" values="{values}" keyTimes="{keytimes}" '
        'dur="6s" begin="0.01s" repeatCount="indefinite"/>'
    )
    return f'<g transform="translate({x:.1f},0)">' + "".join(parts) + anim + "</g>"


def matrix_rain(seed: int, w: int, h: int, col_spacing: int = 14, line_h: int = 14) -> str:
    rng = random.Random(seed)
    cols = max(1, w // col_spacing)
    body = "".join(rain_column_svg(rng, i * col_spacing + col_spacing / 2, line_h, h) for i in range(cols))
    return (
        f'<clipPath id="cardRainClip"><rect x="0" y="0" width="{w}" height="{h}"/></clipPath>'
        f'<g clip-path="url(#cardRainClip)" opacity="0.35">{body}</g>'
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


def logo_glyph(cx: float, cy: float, size: float) -> str:
    """A small ">_" terminal glyph standing in for a neofetch distro logo."""
    half = size / 2
    return (
        f'<g transform="translate({cx:.1f},{cy:.1f})">'
        f'<rect x="{-half:.1f}" y="{-half:.1f}" width="{size:.0f}" height="{size:.0f}" rx="10" '
        f'fill="none" stroke="{GREEN_BRIGHT}" stroke-width="2" opacity="1"/>'
        f'<text x="0" y="{size * 0.14:.1f}" text-anchor="middle" font-family="SFMono-Regular,Consolas,monospace" '
        f'font-size="{size * 0.42:.0f}" fill="{GREEN_BRIGHT}" font-weight="bold">&gt;_</text>'
        f'<animate attributeName="opacity" values="1;0.55;1" keyTimes="0;0.5;1" dur="3.6s" '
        f'begin="0.01s" repeatCount="indefinite"/>'
        f"</g>"
    )


def reveal_wrap(inner: str, begin: float, dur: float = 0.45) -> str:
    return (
        f'<g opacity="1">'
        f'<animate attributeName="opacity" values="0;0;1" keyTimes="0;0.02;1" '
        f'dur="{dur}s" begin="{begin:.3f}s" fill="freeze"/>'
        f"{inner}"
        f"</g>"
    )


def build_svg() -> str:
    W, H = CARD_WIDTH, CARD_HEIGHT
    pad_x = 20
    header_y = TITLEBAR_H + 34
    logo_size = 46
    logo_cx = pad_x + logo_size / 2
    logo_cy = header_y - 6

    info_x = pad_x + logo_size + 22
    field_label_w = max(len(k) for k, _ in FIELDS)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
        f'role="img" aria-label="neofetch style info card for {xml_escape(USERNAME)}">'
    ]
    parts.append(f'<rect x="0" y="0" width="{W}" height="{H}" rx="10" fill="{BG}"/>')
    parts.append(f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="10" fill="none" stroke="{PANEL_BORDER}"/>')
    parts.append(titlebar(W, "whoami.sh"))
    parts.append(matrix_rain(seed=99, w=W, h=H - TITLEBAR_H))
    # shift rain into place below titlebar
    parts[-1] = f'<g transform="translate(0,{TITLEBAR_H})">' + parts[-1] + "</g>"

    parts.append(reveal_wrap(logo_glyph(logo_cx, logo_cy, logo_size), begin=0.05))

    header_text = f"{USERNAME}@{HOST}"
    parts.append(
        reveal_wrap(
            f'<text x="{info_x}" y="{header_y - 20}" font-family="SFMono-Regular,Consolas,monospace" '
            f'font-size="16" font-weight="bold" fill="{GREEN_BRIGHT}">{xml_escape(header_text)}</text>',
            begin=0.08,
        )
    )
    sep = "-" * len(header_text)
    parts.append(
        reveal_wrap(
            f'<text x="{info_x}" y="{header_y}" font-family="SFMono-Regular,Consolas,monospace" '
            f'font-size="13" fill="{TEXT_DIM}">{xml_escape(sep)}</text>',
            begin=0.12,
        )
    )

    line_h = 22
    y = header_y + line_h + 6
    for i, (key, value) in enumerate(FIELDS):
        line = f"{key.ljust(field_label_w)} : {value}"
        # split key (accent) and rest (dim label / bright value) for a bit of color
        key_part = f"{key.ljust(field_label_w)}"
        rest_part = f" : {value}"
        begin = 0.16 + i * 0.09
        text_svg = (
            f'<text x="{info_x}" y="{y}" font-family="SFMono-Regular,Consolas,monospace" font-size="12.5">'
            f'<tspan fill="{ACCENT}">{xml_escape(key_part)}</tspan>'
            f'<tspan fill="{TEXT_BRIGHT}">{xml_escape(rest_part)}</tspan>'
            f"</text>"
        )
        parts.append(reveal_wrap(text_svg, begin=begin))
        y += line_h

    # neofetch-style color swatch row
    swatch_y = y + 6
    swatch_begin = 0.16 + len(FIELDS) * 0.09 + 0.1
    swatches_svg = "".join(
        f'<rect x="{info_x + i * 18}" y="{swatch_y - 12}" width="14" height="14" rx="3" fill="{c}" '
        f'stroke="{PANEL_BORDER}" stroke-width="0.5"/>'
        for i, c in enumerate(SWATCHES)
    )
    parts.append(reveal_wrap(swatches_svg, begin=swatch_begin))

    # bottom prompt line with blinking cursor
    prompt_y = H - 20
    prompt = f"{USERNAME}@{HOST}:~$"
    prompt_begin = swatch_begin + 0.25
    char_w = 12.5 * 0.62
    cursor_x = pad_x + len(prompt) * char_w + 14
    parts.append(
        reveal_wrap(
            f'<text x="{pad_x}" y="{prompt_y}" font-family="SFMono-Regular,Consolas,monospace" '
            f'font-size="12.5" fill="{TEXT_BRIGHT}">{xml_escape(prompt)}</text>',
            begin=prompt_begin,
        )
    )
    parts.append(
        f'<rect x="{cursor_x:.1f}" y="{prompt_y - 11:.1f}" width="7" height="14" fill="{GREEN_BRIGHT}" opacity="1">'
        f'<animate attributeName="opacity" values="1;1;0;0;1" keyTimes="0;0.4;0.5;0.9;1" '
        f'dur="1s" begin="0.01s" repeatCount="indefinite"/>'
        f"</rect>"
    )

    parts.append("</svg>")
    return "".join(parts)


def main() -> int:
    svg = build_svg()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(svg)
    print(f"wrote {OUTPUT_PATH} ({len(svg)} bytes), {CARD_WIDTH}x{CARD_HEIGHT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
