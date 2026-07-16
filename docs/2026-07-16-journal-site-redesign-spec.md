# Field Journal - Website Redesign Spec

> **Status: approved direction, build not started.** Decided with Ron on 2026-07-16
> in a Fable design session. This spec is the single source of truth for the build
> sessions (run on Opus). Companion files: `docs/mockups/` (home.html, promise.html,
> help.html, journal.css; open in a browser, swap `class="paper"` for `class="slate"`
> to see the dark theme) and `docs/2026-07-16-copy-worklist.md` (all outward-facing
> copy with approval status). The design conversation itself is NOT available to
> build sessions; everything needed is in these files plus the app repo's design
> constitution at `badger-fit/docs/superpowers/specs/2026-07-13-field-journal-design.md`.

---

## 1. What was decided (do not relitigate)

1. **The site adopts the app's Field Journal identity** so app and site read as one
   artifact: bone paper light theme, warm slate dark theme, Literata for structure,
   Exo 2 for UI and data, ledger rows and ink rules instead of card grids, the
   three-band stripe in chrome. Ron approved the rendered mockups 2026-07-16
   ("looks good and consistent with the app").
2. **Hero headline:** "As capable as the big trackers. As private as a notebook."
   (approved; subject to the future-proofing rule below).
3. **Future-proofing rule for ALL privacy copy (Ron, 2026-07-16).** The product
   roadmap contains a possible future optional paid account with AI features.
   Every "no account / private" claim on the site must therefore be phrased as
   **never required / opt-in only**, not as an absolute that a future optional
   feature would falsify. Concretely: "No account needed", never "there is no
   account"; "nothing leaves your phone unless you turn it on", never "nothing
   ever leaves your phone". The hero strip wording gets revisited if and when a
   paid tier is announced. This rule is why promise entries 1 and 2 read the way
   they do; do not "tighten" them back into absolutes.
4. **The promise page ships** (new page, route `/promise`, nav label "The promise").
   Five numbered commitments; entry 4 ("nothing you use moves behind a paywall")
   approved by Ron as worded, including the forward-looking commitment.
5. **Header wordmark: icon + text.** The ink badger mark (source:
   `public/assets/badger_icon_only.svg`, same art as app icon Direction E)
   recolored to the ink token, next to a Literata "Badger" wordmark. The mockups
   show a text-only wordmark with a stripe underline; Ron picked icon + text, so
   builders replace the mockup's mark accordingly (keep the type treatment,
   drop the mini stripe underline if it fights the icon; judgment call, goldens
   both ways in the PR description).
   **RESOLVED in M-web-0 (endorsed by design session 2026-07-16): NO mini
   stripe under the wordmark.** Goldens (`docs/goldens/`) show it clipping the
   "g" descender and reading as a hyperlink underline; the header stripe band
   already carries the motif (one stripe per region). Variant A ships.
6. **Information architecture does not change.** Help and guides structure is
   load-bearing (the in-app Help screen links to these URLs and anchors). Pages
   may be restyled freely; URLs, anchors, sidebar grouping, and pagefind search
   stay. The only IA addition is `/promise` (plus footer/nav links to it).
7. **Publish gate (absolute):** everything lands on `redesign/journal-site` or
   milestone branches off it. Nothing merges to `main` and nothing deploys until
   Ron ships the app redesign AND approves the new site. All outward-facing copy
   is draft until Ron signs it off, even after it is committed.

## 2. Principles (web restatement of the app constitution)

- **Ink on paper, not gray on white.** Every neutral is warm-biased. No pure
  #FFF/#000 anywhere. The current gray palette in `global.css` is replaced entirely.
- **Rules, not boxes.** Hairline rules and ledger rows replace card grids. A box
  survives only for genuinely floating content (the tip callout keeps a border).
- **Serif is structure, sans is information.** Literata for headlines, page
  titles, section display lines, the promise numbers. Exo 2 for body, labels,
  nav, buttons, and every numeral-as-data. Serif never renders body copy, data,
  or button labels.
- **The identity lives in shape, type, and motif; color second.** Petrol is the
  only accent. As a fill it is used raw; as text it must be the accent-ink
  variant (see tokens).
- **Static and fast.** Astro static output only. No new client JS beyond the
  existing theme toggle and pagefind. No font CDNs, no analytics, no trackers
  (the site must be as private as the app it advertises).

## 3. Tokens

Replace the `@theme` block in `src/styles/global.css`. Names are suggestions;
keep them semantic, not per-theme.

| Token | Paper (light) | Slate (dark) | Use |
|---|---|---|---|
| `--bg` | `#F1EDE3` | `#1C1A16` | page ground |
| `--surface` | `#F7F3EA` | `#232019` | callouts, raised sheets |
| `--panel` | `#EAE4D6` | `#2B2820` | code chips, input fills |
| `--ink` | `#262219` | `#ECE5D4` | strong rules (2px section tops), wordmark |
| `--outline` | `#C6BEA9` | `#423E36` | moderate dividers, input underlines |
| `--hair` | `#D9D3C2` | `#33302A` | hairline row rules |
| `--text` | `#262219` | `#ECE5D4` | primary text |
| `--text-secondary` | `#5A5344` | `#A89F8A` | body copy |
| `--text-muted` | `#6E664F` | `#8F8772` | captions, footer (AA-checked; slate value nudged from the app's #8D8570 in M-web-0: 4.42:1 on `--surface`, 4.5+ after. Site-only for now; app parity flagged separately) |
| `--text-disabled` | `#B3AB97` | `#565040` | decorative only, never copy |
| `--accent` | `#2E7E90` | `#2E7E90` | fills: buttons, stripe band, chart lines |
| `--accent-ink` | `#23677A` | `#4FA3B8` | accent as TEXT or icon (links, active nav) |
| `--on-accent` | `#FFFFFF` | `#FFFFFF` | text on accent fills |

Rules:
- **Accent as text is always `--accent-ink`** (petrol raw fails 4.5:1 on paper).
  Every `a { color }` and active-nav state uses it. Accent fills stay raw petrol.
- Theme mechanism unchanged: `prefers-color-scheme` default plus the existing
  `data-theme` override + localStorage toggle. Both themes are first-class.
- Semantic colors if needed: success `#3E7D4E`/`#6FBF8E`, warning `#92520A`/
  `#E0A94F`, error `#B03A2E`/`#E07B6E` (paper/slate). The site rarely needs them.

### Stripe motif

Three bands, 6px total: 2px ink top, 2px ground middle, 2px accent bottom
(`docs/mockups/journal.css` `.stripe`). Usage: full-width band directly under the
header on every page; a 34px mini-stripe as the footer mark. Never more than one
stripe element per screen region. It is chrome, not a decoration to sprinkle.

## 4. Typography

- **Faces:** Literata (Roman + Italic variable) and Exo 2 (variable), both OFL.
  **Self-hosted woff2 only; remove the Google Fonts CDN links from
  `BaseLayout.astro`.** Subset to latin with fontTools from the TTFs in the app
  repo (`badger-fit/assets/fonts/`), place in `public/fonts/`, and add
  `@font-face` with `font-weight: 100 900` (Exo 2) / `200 900` (Literata).
- **No CLS from fonts:** preload the two woff2 files used above the fold,
  `font-display: swap`, plus metric-tuned local fallbacks via `size-adjust` /
  `ascent-override` (Georgia fallback for Literata, system sans for Exo 2).
  Lighthouse CLS must stay at 0 on the homepage.
- **Slots** (see mockups for exact sizes in context):

| Slot | Face | Treatment | Use |
|---|---|---|---|
| Hero h1 | Literata w600 | clamp(28-44px), lh 1.18 | homepage headline |
| Page title | Literata w600 | 30-38px | help h1, promise h1 |
| Section heading | Literata w600 | 20-24px | help h2 (above a 2px ink rule), CTA heading |
| Display line | Literata w500 italic | 18-22px | spread column heads, promise teaser, closing lines |
| Kicker / caps | Exo 2 w700 | 11px, tracking 0.13-0.16em, uppercase | section labels, strip values pair with it |
| Body | Exo 2 w400-500 | 14.5-15px, lh 1.6-1.7 | everything else |
| Promise number | Literata w500 italic | "№ 1" style | promise entries only |

- Serif never for numerals-as-data, body copy, or buttons (house rule).

## 5. Components

All reference implementations live in `docs/mockups/`. Build them as Astro
components where reused (Stripe, PositioningStrip, LedgerRow/FeatureRow,
PhoneFrame, Callout); keep one-offs inline.

- **Header:** ground bg (not a gray surface), icon + Literata wordmark, nav links
  Exo 2 13.5px (`--text-secondary`; active = `--accent-ink` w600), "Get the app"
  accent button (radius 10, w700), theme toggle. Stripe band directly below.
- **Positioning strip (homepage):** 2px ink rule top, hairline bottom, four cells
  with hairline verticals; caps value + muted detail line. Wraps 2x2 under 640px.
- **Feature ledger:** two-column grid of rows (hairline bottom), each row =
  20px line glyph (1.6px stroke, `--accent-ink`) + title (Exo 2 w600 15px) +
  body (13.5px secondary). Single column on mobile. Glyph SVGs from the mockups
  are starting points; redraw cleanly, inline them (no icon font).
- **Capable/shouldn't spread:** two columns, each 2px ink rule top + Literata
  italic head + ledger rows with right-aligned muted annotations.
- **Phone frames (placeholder era):** 1.5px ink border, radius 26, ground fill,
  schematic journal UI inside (stripe, serif date, ledger rows, tally marks, one
  hero number). Caption underneath: "preview frames · swapped for real
  screenshots when the app redesign ships". These are honest illustrations, not
  fake screenshots; do not add fake status bars or real-looking chrome. Swapped
  in M-web-3.
- **Tally marks (decorative use only):** 3.5px × 13px sticks, skew -12°, accent
  fill for done, `--text-disabled` outline for todo. On the site they only appear
  inside phone-frame illustrations; never as real UI.
- **Callout (help pages):** `--surface` bg, 1px hairline border, 3px accent left
  rule, caps "TIP" label in `--accent-ink`. Replaces the current `.callout`.
- **Help sidebar:** journal index. Caps group labels (10px, muted) over a
  hairline; items 13.5px secondary; active item `--accent-ink` w600 with a 2px
  accent left keyline. Search field becomes an underline style (1.5px
  `--outline` bottom border). Pagefind behavior unchanged.
- **Footer:** hairline top rule, centered 34px mini-stripe, muted links
  (add "The promise"), copyright. No boxes.
- **Buttons:** accent fill / radius 10 / w700 primary; chrome links (nav,
  footer, sidebar) are `--accent-ink` with underline on hover only. In-text
  prose links are ALWAYS underlined (M-web-0 endorsed departure: WCAG 1.4.1
  needs more than color at 3:1 to distinguish links inside body text).

## 6. Pages

- **Homepage** (`index.astro`): hero (kicker, serif h1, sub, store badges,
  docs link), positioning strip, phone-frame band + caption, "WHAT'S IN THE APP"
  feature ledger (10 rows; copy in the worklist, import row names all four
  sources), capable/shouldn't spread, promise teaser line, CTA section (2px ink
  rule, serif heading, badges), footer. Kill the current card grid and boxed CTA.
  Keep the JSON-LD block; see worklist for the `operatingSystem` note.
- **`/promise`** (new): kicker, serif h1, lede, five numbered ledger entries,
  closing italic line, small CTA. Full copy in the worklist. Add to footer
  everywhere and to the Header nav on desktop if it fits cleanly (builder
  judgment); at minimum footer + homepage teaser link to it.
- **Help pages + HelpLayout + HelpSidebar:** restyle only (sidebar index, serif
  headings, callout, prose colors). Zero content moves, zero anchor changes.
- **Guides** (`/guides/*` incl. `overview.astro`): same prose restyle; the guide
  picker cards on `guides/index.astro` become ledger rows.
- **Glossary:** prose restyle; terms as ledger entries (term Exo 2 w600,
  definition secondary) if the current markup allows it cheaply.
- **Changelog:** each release becomes a journal entry: Literata version heading,
  date line, 2px ink rule between releases. Content source unchanged.
- **Legal (privacy/terms):** prose restyle only. Do not reword legal copy in the
  restyle milestone; flag any factual drift for a separate pass. While touching
  these pages, verify no page claims Badger "encrypts" the Drive backup (the
  research flagged this overstatement on the Play listing; if the site says it
  anywhere, change to "private backup to your own Google Drive" and bump the
  page's Last updated date only if wording actually changes).
- **404 / any stray pages:** inherit tokens; verify they look acceptable.

## 7. Quality bar (every milestone PR)

- Lighthouse (mobile emulation) ≥ 95 on Performance, Accessibility, Best
  Practices, SEO for home, one help page, and the promise page. CLS = 0.
- Both themes screenshotted (paper + slate) for every changed page in the PR
  description; check `prefers-color-scheme` AND the manual toggle.
- Mobile-first: verify at 360px, 390px, 768px, 1280px. No horizontal scroll.
- Text contrast AA: run the changed pages' token pairs through a checker;
  `--accent-ink` for accent text, never raw `--accent`.
- No new client JS, no external requests (fonts self-hosted; the only external
  assets are the store badge images already in the repo).
- `npm run build` clean; pagefind still indexes; sitemap still generates.
- No em-dashes or en-dashes in any copy; straight quotes; plain voice
  (house writing rules).

## 8. Milestones

1. **M-web-0 - theme foundation:** tokens, self-hosted fonts, global.css rewrite,
   header/footer/stripe, theme toggle preserved, shared components, wordmark.
   Every existing page must render acceptably on the new tokens (they inherit),
   but only chrome is restyled here.
   **DONE 2026-07-16, merged to redesign/journal-site.** Lighthouse mobile
   96/100/100/100 (home; PNG-bound, closes in M-web-1) and 99/100/100/100
   (help); CLS 0; axe clean 22 routes x 2 themes x 2 widths. Endorsed
   departures: slate `--text-muted` #8F8772 (AA on surface), prose links
   always underlined, wordmark variant A (no mini stripe). Accepted: mobile
   (<=640px) header hides Help/Guides/Glossary (approved mockup; footer
   carries the full index) - flag to Ron at sign-off. Known-and-accepted:
   `--outline` theme-toggle border is decorative (~1.6:1); the glyph carries
   the affordance.
2. **M-web-1 - homepage + promise page:** the two marketing surfaces per the
   mockups and copy worklist.
3. **M-web-2 - long tail:** help/guides/glossary/changelog/legal restyle,
   HelpSidebar index, callouts, prose styles.
   Addenda from M-web-0 findings: (a) Exo 2 has no U+2192 glyph and help copy
   uses "Settings → Training" 65 times; fix by adding 'Literata' to the body
   font-family stack AFTER 'Exo 2' (verified: Literata carries U+2192;
   self-hosted, deterministic on every OS; keep the arrow notation). (b)
   Optional polish: theme-toggle border may move to a stronger token if it
   still reads faint in situ; do not claim AA for `--outline`.
4. **M-web-3 - screenshot swap + launch pass (GATED on the app redesign
   shipping):** replace placeholder phone frames with real journal-app
   screenshots from the app repo's `demo/marketing` pipeline, refresh
   `og_image.png`, re-check schema.org `operatingSystem` against the actual iOS
   status, final Lighthouse pass, and the Ron sign-off review before any merge
   to main.

Each milestone gets its own branch off `redesign/journal-site` (e.g.
`feat/site-m0-theme`) and merges back when green.

## 9. Branching model (verbatim in every build prompt)

Create a long-lived integration branch `redesign/journal-site` off `main` if it
doesn't exist. The design spec, copy worklist, and every build milestone commit
there or on milestone branches off it (e.g. `feat/site-m0-theme`) that merge back
into `redesign/journal-site` when green. Never commit to `main`: `main` is the
live, deployed site and stays untouched so fixes to the current site remain
possible. `redesign/journal-site` merges to `main` only when Ron ships the app
redesign and approves the new site, and only that merge triggers a deploy.

Additional coordination notes:
- Check `git branch` and `git status` before any git operation; parallel build
  sessions share the working trees. If the checkout is on another session's
  branch or dirty, work in a `git worktree` instead of switching branches.
- Deploy mechanics: GitHub Pages, triggered ONLY by push to `main` (plus a
  manual workflow_dispatch button in Actions). Never use "Run workflow" on any
  branch other than `main`: dispatching it on the redesign branch would publish
  the unfinished site to badger.fit. Local preview instead: `npm run dev` (or
  `npm run build && npm run preview` for pagefind) in a worktree on
  `redesign/journal-site`.
- In-flight help-content branches (`redesign/journal-history-followups`,
  `docs/skip-last-set-auto-advance`, possibly newer) document redesigned app
  behavior and must land in `redesign/journal-site`, not `main`. Before M-web-2
  restyles help pages, check whether they have merged; if not and their sessions
  appear complete, merge them into `redesign/journal-site` first (ask Ron if
  unsure).

## 10. Open items

- Real screenshots (M-web-3, gated on the app shipping and a `demo/marketing`
  re-render in the app repo).
- OG image + favicon refresh to the journal identity (M-web-3; favicon may adopt
  the Direction E mark earlier if trivial).
- Play listing text rewrite (research Part 12 P1-P3) is a separate outward-facing
  task, not part of the website build.
- SEO landing pages (Part 12 P7: stronglifts-5x5-tracker, fitnotes-on-iphone,
  workout-tracker-no-subscription) are post-redesign backlog; the promise page
  covers the positioning-page role for now.
- Trademark hygiene (research Part 13): outward phrasing is "Badger - Workout &
  Strength Tracker" / badger.fit; never Wisconsin references, red-and-white
  athletics styling, or a Bucky-like mascot anywhere on the site.
