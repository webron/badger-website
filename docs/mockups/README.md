# Field Journal site mockups (approved 2026-07-16)

Open `home.html`, `promise.html`, or `help.html` in a browser. Each page renders
the paper (light) theme; edit `class="paper"` to `class="slate"` on the `<body>`
to see the dark theme. `journal.css` carries the web token values and shared
chrome; it is the measurement reference for builds, not production CSS.

Fonts: the CSS references a `fonts/` directory that is deliberately not
committed here. To render with real type, copy `Literata-Roman.ttf`,
`Literata-Italic.ttf`, and `Exo2-VariableFont_wght.ttf` from
`badger-fit/assets/fonts/` into `docs/mockups/fonts/`. Production uses subsetted
woff2 in `public/fonts/` instead (spec section 4).

Known deltas from the approved verdicts (mockups render the older state):
- Header shows a text-only wordmark with a stripe underline; Ron chose
  icon + text (spec section 1.5).
- The Google Play badge image is referenced but not committed; it lives at
  `public/assets/badges/google-play-badge.png`.
