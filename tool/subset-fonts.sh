#!/usr/bin/env bash
# Regenerate the self-hosted woff2 subsets in public/fonts/.
#
# Source faces live in the app repo (badger-fit/assets/fonts/) so the site and the
# app ship byte-identical typography. Both families are OFL. Run this only when the
# source TTFs change; the generated woff2 files are committed.
#
# Requires fontTools + brotli:
#   python3 -m venv .fontenv && .fontenv/bin/pip install fonttools brotli
#   PYBIN=.fontenv/bin ./tool/subset-fonts.sh
#
# Design notes (see docs/2026-07-16-journal-site-redesign-spec.md section 4):
#   - Variable axes are preserved: Exo 2 keeps wght 100..900; Literata keeps
#     wght 200..900 AND opsz 7..72 (browsers apply optical sizing automatically,
#     which matters because the design sets Literata from 18px to 44px).
#   - Layout features are trimmed to what the design actually uses. tnum is
#     load-bearing: the journal language sets numerals-as-data in tabular figures.
#     Dropping the unused smallcaps/superscript/alternate sets saves ~35% because
#     their glyphs would otherwise be retained by feature closure.
#   - Latin subset = the Google Fonts "latin" range, plus U+2116 (No) for the
#     promise page numbers and U+2190..2193 (arrows) for link affordances.

set -euo pipefail

SRC="${SRC:-/Users/ron/Development/badger-fit/assets/fonts}"
OUT="$(cd "$(dirname "$0")/.." && pwd)/public/fonts"
PYBIN="${PYBIN:-}"
SUBSET="${PYBIN:+$PYBIN/}pyftsubset"

UNICODES='U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+2116,U+2190-2193,U+20AC,U+2122,U+2212,U+2215,U+FEFF,U+FFFD'
FEATURES='ccmp,locl,kern,liga,clig,calt,rvrn,tnum,lnum,mark,mkmk'

subset() {
  local infile="$1" outfile="$2"
  "$SUBSET" "$SRC/$infile" \
    --output-file="$OUT/$outfile" \
    --flavor=woff2 \
    --unicodes="$UNICODES" \
    --layout-features="$FEATURES" \
    --no-hinting
  printf '  %-34s %5s KB\n' "$outfile" "$(( $(stat -f%z "$OUT/$outfile") / 1024 ))"
}

mkdir -p "$OUT"
echo "Subsetting to $OUT"
subset Exo2-VariableFont_wght.ttf exo2-latin-var.woff2
subset Literata-Roman.ttf         literata-latin-var.woff2
subset Literata-Italic.ttf        literata-latin-var-italic.woff2
echo "Done."
