# M-web-3 sign-off package - Field Journal website

Built 2026-07-23 on `feat/site-m3-launch`, merged into `redesign/journal-site`
(merge commit `339277c`). **Nothing is deployed.** `main` is untouched and the
redesign branch reaches badger.fit only when Ron approves and merges it.

Screenshot set for review: `/Users/ron/Development/badger-site-signoff-2026-07-23/`
(28 full-page PNGs, before/after on the homepage, after-only for the other page
families; paper + slate, desktop 1280 and mobile 390. The four `band-*.png` are
tight crops of the one surface that changed.)

---

## Gate check (passed)

- App's Field Journal redesign shipped as **v1.1.0, 2026-07-22** (`redesign/journal`
  merged to `main` in badger-fit).
- Capture pipeline re-run on the redesigned app, **including light-theme variants**
  (`badger-fit demo/marketing/screens/*_light.png`, committed 2026-07-22).

## What changed

**1. Real screenshots, theme-matched.** The three homepage phone frames now hold
real captures of the shipped app: Today, a live set log, the progress overview.
Each screen ships in both app themes; the frame shows paper when the site renders
light and slate when it renders dark, following the OS preference *and* the manual
toggle. Implementation is two `<img>`s swapped by CSS (`.paper-only` / `.slate-only`
in `global.css`), not a `<picture>` media source, because the toggle is a
`data-theme` attribute no media query can see. The placeholder caption is gone;
the new one reads "Today, logging a set, and progress. Real screens from the app."
(the one new outward-facing string in this milestone - see Flags).

Captures are cropped free of the phone's own status bar and gesture pill, resized
to 540px wide, encoded webp: ~23 KB each, ~70 KB per theme for the visible three.
The hidden theme variant is never fetched, and the third frame is `display: none`
below 640px so a phone loads two images, not six.
`tool/build-screenshots.mjs` rebuilds the whole set from the app repo.

**2. OG image.** Verified intact - the journal book-cover card landed ahead of this
milestone (commit `a9894b4`). Not touched.

**3. JSON-LD `operatingSystem`.** Re-checked: iOS is **still TestFlight-only**, the
App Store submission has not gone in. Both the claim (`Android, iOS`) and the CTA's
"with an iOS beta open in TestFlight" stand as written; the field states which
operating systems the app runs on, not where it can be bought, and the CTA says
TestFlight in plain words. The source comment now records the check instead of
asking for it. Revisit at App Store launch.

**4. Launch QA.** One real defect found and fixed: `/help/logging#summary` was a
dead anchor (no such section; broken on `main` too). The fragment is dropped, so
the link lands on the logging page. All **605** internal anchors now resolve.

**5. Cleanup.** Deleted the placeholder-era `PhoneFrame` and `TallyMarks`
components and the eight pre-redesign screenshot PNGs, all unreferenced after the
swap.

## Quality bar

| Page | Lighthouse mobile (P/A/BP/SEO) | CLS |
|------|-------------------------------|-----|
| Home | 97 / 100 / 100 / 100 | 0 |
| /promise | 98 / 100 / 100 / 100 | 0 |
| /help/logging | 99 / 100 / 100 / 100 | 0 |
| /guides/overview | 99 / 100 / 100 / 100 | 0 |
| /changelog | 97 / 100 / 100 / 100 | 0 |

Home on desktop: 100 across all four.

- Both themes verified at **360, 390, 768, 1280**; no horizontal scroll at any width.
- Theme match verified three ways: OS preference, forced `data-theme`, and a real
  click on the toggle. All six permutations serve the matching capture.
- Every `<img>` on the site carries width and height; the phone captures are lazy
  and below the fold. No new client JS, no external requests.
- `npm run build` clean, 23 pages. Pagefind indexes 23 pages and its results render
  legibly on the journal tokens. Sitemap intact, `/promise` included.
- Every route the in-app Help screen links to returns 200.
- No em-dashes or en-dashes introduced.

## Drift since M-web-2

- **`main` has not moved.** No hotfixes to fold in; the redesign branch is 23
  commits ahead and contains everything on `main`.
- **`site/wave-b` (8 commits) must stay out of this deploy.** It documents app Wave
  B behavior (equipment photos, home-screen widget, personal context notes, rep
  ranges, A-Z library, settings regroup) and the app's `wave-b` branch is 33
  commits from shipping. Merging it would publish help for features nobody has.
  It merges after Wave B ships, not before.
- All other in-flight help branches (`docs/backdated-workout-reentry`,
  `docs/skip-last-set-auto-advance`, `docs/training-set-details`,
  `redesign/journal-history-followups`) are already merged into
  `redesign/journal-site`.

## Flags for Ron

1. **New copy string (needs your yes):** the phone band caption, "Today, logging a
   set, and progress. Real screens from the app." The worklist only ever specified
   the placeholder caption, which said outright that it must never ship. Say the
   word and it becomes anything else, or nothing at all.
2. **Mobile header still hides Help / Guides / Glossary** below 640px (footer
   carries the full index). Approved in the mockup at M-web-0 and flagged then for
   this sign-off - raising it once more because it is the last chance before launch.
3. **The progress frame shows the Progress *overview* tab** (weekly volume plus the
   frequency chart), not the exercise graph the demo README describes for
   `progress.png`. It reads well and it is a real screen, but if you would rather
   the third frame show an exercise line chart with a PR, that is a recapture in
   the app repo, not a site change. The same applies to the store set, which uses
   the same file for "Watch your strength climb".
4. **Cosmetic, invisible in use:** the paper and slate Today captures were taken
   moments apart, so their elapsed timers differ (42:37 vs 52:56). Only one theme
   is ever on screen, so nobody can see both. Not worth a recapture on its own.

## Addendum - favicon refresh (2026-07-23, post-launch)

The site favicon was still the old teal badger mark
(`/assets/badger_icon_only.svg`, referenced by the icon `<link>`). Refreshed to
the Direction E journal identity per Ron's ruling: the **ink badger head on a
paper rounded square**, with the two stripe bands **dropped** (they turn to noise
at 16-32px; the head alone is the mark).

- **`public/favicon.svg`** - head geometry is pixel-identical to the app icon
  (`badger-fit assets/app_icon_full.png`): same source paths, same
  `translate(15.437 6.811) scale(0.07488)` placement. Two intentional departures,
  both to serve a head-only mark: the head is re-centred (cy 45 -> 54, since the
  bars no longer hold the lower third) and scaled 1.2x for 16px legibility.
  Colours unchanged: ink `#262219` head, paper `#F1EDE3` ground and muzzle
  knockout. Rounded-square corner radius 22/108 (~20%); corners transparent so it
  reads as a badge on any tab chrome.
- **`public/favicon.ico`** - 16/32/48px legacy fallback packed from the same SVG.
- **`tool/build-favicon.py`** - regenerates both from
  `public/assets/badger_icon_only.svg`, so the favicon is reproducible, not a
  mystery binary. Verified: re-running it reproduces both files byte-identically.
- **`<head>`** now points the SVG `<link>` at `/favicon.svg` and adds the `.ico`
  fallback link; the old teal asset is no longer referenced by the favicon.
  `BadgerMark.astro` (the inline on-page mark) already used theme tokens, not
  teal, and is untouched.

**Light/dark verification** (`favicon-light-slate-16-32-48.png` in this folder):
16/32/48px on light (`#DEE1E6`) and dark (`#202124`) Chrome grounds. 32 and 48
are crisp and unmistakably the journal badger on both; 16 is blocky but symmetric
and centred, reading as the two-tone head (the detail floor at 16px - exactly why
the bands are dropped). Also loaded the built `favicon.svg` in a real browser
engine to confirm the vector renders (not just a CLI raster).

## Before you merge

- [ ] Look at the four `band-*.png` crops: real captures in place of the schematics.
- [ ] Look at `home-*-after.png` (paper and slate, desktop and mobile) end to end.
- [ ] Answer flag 1 (caption wording) and flag 3 (which progress screen).
- [ ] Confirm flag 2 (mobile header nav) is still how you want it.
- [ ] Read the outward-facing copy once as the site's owner: homepage, `/promise`,
      the CTA's TestFlight line.
- [ ] Then, and only then: merge `redesign/journal-site` into `main`. That push is
      what deploys badger.fit. Do not run the Pages workflow on any other branch.
