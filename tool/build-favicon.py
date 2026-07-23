#!/usr/bin/env python3
"""Regenerate the site favicon (Direction E journal identity).

The favicon is the ink badger HEAD on a paper rounded square - the same mark as
the app icon (badger-fit assets/app_icon_full.png), but with the two stripe
bands DROPPED: at 16-32px the bands turn to noise, so the head alone is the mark
(design ruling, 2026-07-23). Head geometry comes from the shared source vector
public/assets/badger_icon_only.svg via the exact transform the app-icon
generator uses (badger-fit tool/icon_splash/generate_icon_splash.py), so the
head is pixel-identical to the app icon.

Two intentional departures from the app icon, both to serve a head-only mark:
  - re-centre the head (cy 45 -> 54; the bars no longer occupy the lower third)
  - scale it 1.2x so it stays legible at 16px
The silhouette and colours are unchanged.

Outputs (public/):
  favicon.svg   the source of truth (pure Python, no tools needed)
  favicon.ico   16/32/48 legacy fallback (needs headless Chrome + ImageMagick)

Run: python3 tool/build-favicon.py
"""
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "public" / "assets" / "badger_icon_only.svg"
SVG_OUT = ROOT / "public" / "favicon.svg"
ICO_OUT = ROOT / "public" / "favicon.ico"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

INK = "#262219"    # journal ink (app icon head)
PAPER = "#F1EDE3"  # bone paper ground + muzzle knockout
BADGER_ICON_TRANSFORM = "translate(15.437 6.811) scale(0.07488)"  # app-icon placement
RX = 22            # rounded-square corner radius on the 108 artboard (~20%)
SCALE = 1.2        # head-only legibility bump; identity unchanged
ICO_SIZES = (16, 32, 48)


def load_paths():
    svg = SOURCE.read_text()
    head, white = [], []
    for m in re.finditer(r'<path fill="([^"]+)" d="([^"]+)"', svg):
        fill, d = m.groups()
        (head if fill.lower() == "#2e7e90" else white).append((fill, d))
    head = [d for f, d in head if f.lower() == "#2e7e90"]
    white = [d for f, d in white if f.lower() == "white"]
    if len(head) != 2 or len(white) != 8:
        raise SystemExit(f"source vector changed: {len(head)} head / {len(white)} white paths")
    return head, white


def build_svg():
    head, white = load_paths()
    paths = "".join(f'\n      <path fill="{INK}" d="{d}"/>' for d in head)
    paths += "".join(f'\n      <path fill="{PAPER}" d="{d}"/>' for d in white)
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 108 108" '
        'width="32" height="32" role="img" aria-label="Badger">\n'
        '  <defs>\n'
        f'    <clipPath id="badge"><rect width="108" height="108" rx="{RX}" ry="{RX}"/></clipPath>\n'
        '  </defs>\n'
        '  <g clip-path="url(#badge)">\n'
        f'    <rect width="108" height="108" fill="{PAPER}"/>\n'
        f'    <g transform="translate(54 54) scale({SCALE}) translate(-54 -45) {BADGER_ICON_TRANSFORM}">{paths}\n'
        '    </g>\n'
        '  </g>\n'
        '</svg>\n'
    )
    SVG_OUT.write_text(svg)
    print(f"wrote {SVG_OUT.relative_to(ROOT)} ({len(svg)} bytes)")
    return svg


def build_ico(svg):
    if not Path(CHROME).exists() or not shutil.which("magick"):
        print("skip favicon.ico: needs Google Chrome + ImageMagick (`magick`); SVG is enough for modern browsers")
        return
    with tempfile.TemporaryDirectory() as td:
        pngs = []
        for s in ICO_SIZES:
            # Give the SVG the target intrinsic size so Chrome SCALES via the
            # viewBox instead of cropping (a 16px window on a 32px-intrinsic SVG
            # shows the top-left quarter).
            sized = svg.replace('width="32" height="32"', f'width="{s}" height="{s}"', 1)
            svg_p = Path(td) / f"f{s}.svg"
            png_p = Path(td) / f"f{s}.png"
            svg_p.write_text(sized)
            subprocess.run(
                [CHROME, "--headless=new", f"--screenshot={png_p}", f"--window-size={s},{s}",
                 "--default-background-color=00000000", "--hide-scrollbars", f"file://{svg_p}"],
                check=True, capture_output=True)
            pngs.append(str(png_p))
        subprocess.run(["magick", *pngs, str(ICO_OUT)], check=True)
    print(f"wrote {ICO_OUT.relative_to(ROOT)} ({'/'.join(map(str, ICO_SIZES))}px)")


if __name__ == "__main__":
    sys.exit(build_ico(build_svg()))
