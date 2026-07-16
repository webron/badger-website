# Opus build prompts - Field Journal website redesign

> Copy-paste one prompt per build session, in order. Each is self-contained.
> Issued 2026-07-16 by the Fable design session; the authority for every design
> question is the committed spec, not this file.

---

## Prompt 1 - M-web-0: theme foundation

You are building milestone M-web-0 of the Badger website's Field Journal redesign, in /Users/ron/Development/badger-website (Astro + Tailwind 4 + pagefind, static output). You restyle the site's foundation only; no page content changes in this milestone.

Read first, in this order: docs/2026-07-16-journal-site-redesign-spec.md (the spec; its sections on tokens, typography, components, and quality bar govern everything), docs/2026-07-16-copy-worklist.md, the mockups in docs/mockups/ (open home.html in a browser; swap class="paper" for class="slate" to see the dark theme), and for background the app design constitution at /Users/ron/Development/badger-fit/docs/superpowers/specs/2026-07-13-field-journal-design.md.

Branching model (follow exactly): Create a long-lived integration branch redesign/journal-site off main if it doesn't exist. The design spec, copy worklist, and every build milestone commit there or on milestone branches off it (e.g. feat/site-m0-theme) that merge back into redesign/journal-site when green. Never commit to main: main is the live, deployed site and stays untouched so fixes to the current site remain possible. redesign/journal-site merges to main only when Ron ships the app redesign and approves the new site, and only that merge triggers a deploy. Before any git operation, check git branch and git status: parallel build sessions share this working tree, and if the checkout is on another session's branch or dirty, work in a git worktree instead of switching branches. For this milestone: branch feat/site-m0-theme off redesign/journal-site, merge back when green.

Scope:
1. Fonts: subset Literata-Roman.ttf, Literata-Italic.ttf, and Exo2-VariableFont_wght.ttf from /Users/ron/Development/badger-fit/assets/fonts/ to latin woff2 with fontTools (pyftsubset, keep variable axes), place in public/fonts/, wire @font-face (Exo 2 weight 100 900; Literata 200 900 roman + italic). Remove the Google Fonts CDN links and preconnects from BaseLayout.astro. Preload the woff2 files used above the fold. font-display: swap plus metric-tuned fallbacks (size-adjust/ascent-override; Georgia for Literata, system sans for Exo 2) so CLS stays 0.
2. Tokens: replace the gray palettes in src/styles/global.css with the paper/slate token table from spec section 3, keeping the existing theme mechanism (prefers-color-scheme default, data-theme override, localStorage toggle). Links and all accent-as-text become --accent-ink; accent fills stay raw petrol.
3. Chrome: rebuild Header.astro (ground background, ink badger icon + Literata "Badger" wordmark per spec section 1.5, nav links, accent Get-the-app button, theme toggle) with the full-width stripe band below it; rebuild Footer.astro (hairline rule, centered mini-stripe, muted links including a "The promise" link that may 404 until M-web-1, copyright). Build the stripe as a reusable Astro component or utility class per docs/mockups/journal.css.
4. Shared styles: update the .prose and .callout styles in global.css to the journal treatments (Literata headings, callout with accent-ink TIP label) so all prose pages inherit acceptably. Full page restyles are M-web-2; after M-web-0 every page must merely look coherent on the new tokens with no broken contrast.
5. Inline styles in the components you touch may be converted to classes; do not refactor pages you are not touching.

Quality bar (spec section 7, all of it): Lighthouse mobile ≥95 across the four categories on home and one help page, CLS 0, both themes screenshotted for every changed surface (check prefers-color-scheme AND the toggle), 360/390/768/1280 widths, AA contrast (accent text = accent-ink), no new client JS, no external requests, npm run build clean, pagefind and sitemap intact, no em-dashes anywhere. Verify with a local build + headless screenshots, not by assertion.

The publish gate is absolute: nothing you do deploys. Do not push to main, do not touch any deploy config. All outward-facing copy is draft-for-Ron even when committed.

Summarize what changed, list any departures from the spec with reasons, and flag anything that needs Ron's eyes.

---

## Prompt 2 - M-web-1: homepage + promise page

You are building milestone M-web-1 of the Badger website's Field Journal redesign, in /Users/ron/Development/badger-website (Astro, static). M-web-0 (theme foundation) is merged into redesign/journal-site; you build the two marketing surfaces on top of it.

Read first: docs/2026-07-16-journal-site-redesign-spec.md (sections 5, 6, 7 especially), docs/2026-07-16-copy-worklist.md (the exact copy; use it verbatim, statuses included), the mockups docs/mockups/home.html and docs/mockups/promise.html in a browser (paper and slate), and docs/mockups/journal.css for measurements.

Branching model (follow exactly): Create a long-lived integration branch redesign/journal-site off main if it doesn't exist. The design spec, copy worklist, and every build milestone commit there or on milestone branches off it (e.g. feat/site-m0-theme) that merge back into redesign/journal-site when green. Never commit to main: main is the live, deployed site and stays untouched so fixes to the current site remain possible. redesign/journal-site merges to main only when Ron ships the app redesign and approves the new site, and only that merge triggers a deploy. Before any git operation, check git branch and git status: parallel build sessions share this working tree; if the checkout is busy, use a git worktree. For this milestone: branch feat/site-m1-home-promise off redesign/journal-site, merge back when green.

Scope:
1. Homepage (src/pages/index.astro) per the mockup: hero (kicker, Literata h1 "As capable as the big trackers. As private as a notebook.", sub, store badges, docs link), positioning strip (2x2 on mobile), phone-frame placeholder band with its caption, WHAT'S IN THE APP feature ledger (10 rows, two columns desktop, line glyphs at 1.6px stroke in accent-ink; redraw the mockup SVGs cleanly), the capable/shouldn't two-column spread, promise teaser, CTA section, all on the shared chrome. Kill the card grid and boxed CTA entirely. Keep the JSON-LD; leave operatingSystem as is but add the spec's note as a code comment for the M-web-3 check.
2. Phone-frame placeholders: honest schematic journal UI per the mockup (stripe, serif date, ledger rows, tally sticks, one hero number, PR flag). They are illustrations; no fake status bars, no real-screenshot cosplay. Keep the caption from the worklist.
3. New page src/pages/promise.astro at /promise per the mockup: kicker, Literata h1, lede, five numbered ledger entries (No 1 to No 5 in Literata italic), closing line and sign-off, small CTA. Use the copy worklist text verbatim, including entry 4 which Ron approved as worded. Add /promise to the footer (site-wide) and link the homepage teaser to it. Give it a proper meta description (worklist section 1 has the positioning phrasing).
4. Mobile: match the mockup's responsive behavior (strip 2x2, features single column, two phone frames, spread stacked).

Copy rules: use the worklist strings exactly; no em-dashes or en-dashes anywhere; every privacy claim phrased as never-required/opt-in per spec section 1.3. If you believe a string must change for layout reasons, change it minimally and flag it prominently in your summary for Ron.

Quality bar (spec section 7): Lighthouse mobile ≥95 on home and /promise, CLS 0, both themes screenshotted, 360/390/768/1280, AA contrast, no new client JS, npm run build clean, sitemap picks up /promise. Verify by building and screenshotting, not by assertion.

The publish gate is absolute: nothing deploys, never commit to main. All outward copy remains draft-for-Ron.

Summarize, list departures, flag anything needing Ron.

---

## Prompt 3 - M-web-2: help, guides, glossary, changelog, legal restyle

> **Addendum (from the M-web-0 report, 2026-07-16):** add `'Literata'` to the
> body `font-family` stack immediately after `'Exo 2'` so the 65 "Settings →
> Training" arrows in help copy render from the self-hosted serif (Exo 2 has no
> U+2192; Literata does; keep the arrow notation). Optionally strengthen the
> theme-toggle border token if it reads faint; never claim AA for `--outline`.
> Prose links stay always-underlined and the slate `--text-muted` is #8F8772
> (both endorsed in M-web-0; already in global.css - do not revert).

You are building milestone M-web-2 of the Badger website's Field Journal redesign, in /Users/ron/Development/badger-website (Astro, static). M-web-0 and M-web-1 are merged into redesign/journal-site. You restyle the documentation long tail. This is a restyle: zero content moves, zero URL or anchor changes, zero copy edits beyond what the worklist explicitly allows (the in-app Help screen links to these URLs and anchors, so the IA is load-bearing).

Read first: docs/2026-07-16-journal-site-redesign-spec.md (sections 5, 6, 7), docs/2026-07-16-copy-worklist.md (section 3 governs this milestone), docs/mockups/help.html in a browser (paper and slate).

Branching model (follow exactly): Create a long-lived integration branch redesign/journal-site off main if it doesn't exist. The design spec, copy worklist, and every build milestone commit there or on milestone branches off it (e.g. feat/site-m0-theme) that merge back into redesign/journal-site when green. Never commit to main: main is the live, deployed site and stays untouched so fixes to the current site remain possible. redesign/journal-site merges to main only when Ron ships the app redesign and approves the new site, and only that merge triggers a deploy. Before any git operation, check git branch and git status: parallel build sessions share this working tree; if the checkout is busy, use a git worktree. For this milestone: branch feat/site-m2-longtail off redesign/journal-site, merge back when green.

Coordination step BEFORE restyling: in-flight help-content branches (redesign/journal-history-followups, docs/skip-last-set-auto-advance, possibly newer ones) document redesigned app behavior and must land in redesign/journal-site, not main. Check whether they have merged into redesign/journal-site; if not and their sessions appear complete (clean tree, no recent activity), merge them into redesign/journal-site first so content and restyle do not conflict. Ask Ron if unsure whether a branch is finished.

Scope:
1. HelpSidebar.astro: journal index per the mockup (caps group labels over hairlines, quiet item rows, active item accent-ink w600 with 2px accent left keyline, underline-style pagefind search box). Behavior and nav data unchanged.
2. HelpLayout.astro + prose styles: Literata h1/h2 (h2 above a 2px ink rule), journal callout, code chips on panel bg, hairline hr. All help/* pages inherit; spot-fix any page-local styling that fights the new prose.
3. Guides: same prose treatment; guides/index.astro picker cards become ledger rows; guides/overview.astro's per-capability lines become ledger rows if the markup allows it cheaply.
4. Glossary: terms as ledger entries (term Exo 2 w600, definition secondary) if cheap; otherwise plain prose restyle.
5. Changelog: each release as a journal entry (Literata version heading, date line, 2px ink rule between releases). Content source unchanged.
6. Legal: prose restyle only; do not reword. Grep the whole site for "encrypt" and if any page overstates the Drive backup as encrypted, change that phrase to "private backup to your own Google Drive" and bump that page's Last updated date; flag it in your summary.
7. 404 and any stray pages: verify they inherit acceptably.

Quality bar (spec section 7): Lighthouse mobile ≥95 on a help page, a guide, and the changelog; both themes screenshotted for each page family; 360/390/768/1280; AA contrast; pagefind still searches and its result styling is legible on the new tokens; every in-app-linked anchor resolves (spot-check the anchors listed in the app repo's help_screen.dart); npm run build clean; no em-dashes introduced.

The publish gate is absolute: nothing deploys, never commit to main.

Summarize, list departures, flag anything needing Ron.

---

## Prompt 4 - M-web-3: screenshot swap + launch pass (GATED)

GATE CHECK FIRST: this milestone runs only when Ron confirms the app's Field Journal redesign has shipped (redesign/journal merged to main in badger-fit and released) and the demo/marketing screenshot pipeline has been re-run on the redesigned app. If that has not happened, stop and tell Ron what is missing.

You are building the final milestone of the Badger website's Field Journal redesign, in /Users/ron/Development/badger-website. Read first: docs/2026-07-16-journal-site-redesign-spec.md (sections 6, 7, 10), docs/2026-07-16-copy-worklist.md, and the app repo's demo/README.md (screenshot pipeline) in /Users/ron/Development/badger-fit.

Branching model (follow exactly): Create a long-lived integration branch redesign/journal-site off main if it doesn't exist. The design spec, copy worklist, and every build milestone commit there or on milestone branches off it (e.g. feat/site-m0-theme) that merge back into redesign/journal-site when green. Never commit to main: main is the live, deployed site and stays untouched so fixes to the current site remain possible. redesign/journal-site merges to main only when Ron ships the app redesign and approves the new site, and only that merge triggers a deploy. Before any git operation, check git branch and git status: parallel build sessions share this working tree; if the checkout is busy, use a git worktree. For this milestone: branch feat/site-m3-launch off redesign/journal-site, merge back when green.

Scope:
1. Replace the homepage phone-frame placeholders (and their "preview frames" caption) with real device captures of the redesigned app from the demo pipeline: raw seeded-demo captures in journal framing, not the branded 1080x1920 Play composites. Both site themes must pair sensibly with the app screenshots shown (pick app-theme captures per site theme, or one neutral set; judgment call, show Ron).
2. Refresh public/assets/og_image.png to the journal identity (paper ground, wordmark, stripe, positioning line). Keep 1200x630.
3. Re-check the JSON-LD operatingSystem claim against the actual iOS status at that date (TestFlight vs App Store) and update the CTA's iOS clause if the App Store launch happened.
4. Full-site QA pass: Lighthouse mobile ≥95 on home, /promise, a help page, a guide, changelog; CLS 0; both themes; 360 to 1280; every image has dimensions and lazy loading below the fold; pagefind, sitemap, and all in-app-linked anchors intact.
5. Produce a before/after screenshot set (paper + slate, desktop + mobile) for Ron's final sign-off. Do NOT merge redesign/journal-site to main yourself: present the sign-off package and wait. Only Ron's explicit approval triggers the merge, and only that merge deploys.

Summarize, list anything that drifted since M-web-2 (main hotfixes to merge in, stale copy), and hand Ron the sign-off checklist.
