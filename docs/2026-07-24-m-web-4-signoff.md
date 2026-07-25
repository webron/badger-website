# M-web-4 sign-off package - the three orphaned pages

Built 2026-07-24 on `site/m-web-4`. **Nothing is deployed.** `main` is untouched
and these pages reach badger.fit only when Ron approves the copy and merges.

Spec (the contract): `badger-fit
docs/superpowers/specs/2026-07-18-m-web-4-orphaned-pages.md`. Stance for the AI
page: `badger-fit docs/superpowers/specs/2026-07-18-ai-integration-direction.md`
rungs 1-2.

Screenshots for review: `/Users/ron/Development/badger-site-m-web-4-signoff-2026-07-24/`
(12 full-page PNGs: three pages x paper and slate x desktop 1280 and mobile 390).

---

## What shipped

**1. `/programs` - the program gallery.** Six starter programs as downloadable
`.badger` files, each with days per week, level, computed counts, and a
two-sentence description that says where the program runs out as well as what it
does. Then a "Not yet" section listing 5/3/1 and nSuns as programs Badger cannot
run honestly today, each with a `mailto:hello@badger.fit` that fills in the
subject. That mailto is the demand instrument: the site has no analytics and no
cookies, so asking is the only measurement available.

**2. `/badger-format` - the file format.** The `share/v1` envelope, the routine /
gym / machines payloads field by field, what import does with each field, what a
file deliberately does not carry, and the versioning promise. Audience is named
on the page: curious users, tool authors, and AI assistants.

**3. `/guides/ai` - use your own AI.** Three prompt templates with copy buttons
(analyze the CSV export, review a routine, write a program as a valid `.badger`),
what to check before importing what the AI writes back, and a plain account of
what pasting an export costs in privacy.

Navigation: `Programs` added to the footer index; the help sidebar's Reference
group gained "Program files" and "The .badger format", and its Starting Guides
group gained "Use your own AI"; `/guides` picked up one line pointing at the AI
guide. The header nav is unchanged (three links plus the CTA is already tight,
and it hides links below 640px).

## The files are generated, not written

Every `.badger` file in `public/programs/` came out of the app's own export path
(`BadgerExportService`) against a freshly seeded database, and each one was then
imported into a clean database with the real `BadgerImportService` and compared
field by field against the original payload. Generator:
`badger-fit test/tools/program_gallery_export_test.dart`, on branch
`tool/program-gallery-export`. Re-run it and re-copy the output whenever the
schema or the seeded templates change.

Both new pages read those files at build time - the gallery for its counts and
the app version, the format page for its worked example - so neither page can
drift from what it is handing out.

## Quality bar

| Page | Lighthouse mobile (P/A/BP/SEO) | CLS |
|------|-------------------------------|-----|
| /programs | 98 / 100 / 100 / 100 | 0 |
| /badger-format | 99 / 100 / 100 / 100 | 0 |
| /guides/ai | 99 / 100 / 100 / 100 | 0 |

- `npm run build` clean, 26 pages, pagefind indexes 26, sitemap intact.
- 1793 internal links and anchors across the site resolve, including the
  download links.
- No horizontal scroll at 360, 390, 768 or 1280 on the three new pages, and the
  same re-checked on `/guides` and `/help/settings` after the HelpLayout fix.
- Both themes captured for every page, paper and slate.
- Contrast: every new token pair measured. Lowest is `--text-muted` on the ground
  at 4.86:1; the "Not yet" tag uses `--warning` at 5.23:1 (paper) and 8.24:1
  (slate).
- No em-dashes, en-dashes, smart quotes or British spellings in the new copy
  (scanned source and rendered HTML).
- No new external requests. One new inline script, see the flags.

## Flags for Ron

1. **All copy on three pages is new and outward-facing, so all of it needs your
   yes.** Read the rendered pages end to end rather than only the diff. The
   sharpest lines, in case you want them softened: "A program is a plan, not a
   subscription. Take the file." (gallery close), "a file that pretends to run a
   program it cannot is worse than no file" (Not yet lede), and the privacy
   section on the AI page, which says plainly that pasting your export into a
   chat hands it to that company under their terms.

2. **The versioning promise is a forward-looking commitment, not a description of
   today's code.** The spec asked for "v1 files keep importing", and the page
   says a file exported today should still import years from now. Today the app
   accepts exactly the version it knows (`share/v1`) and refuses anything else,
   so keeping that promise means multi-version support whenever the schema
   changes. Fine to publish as an intent, but it is a promise you are making.

3. **The download-and-tap flow needs a real device check before this goes live.**
   The Android intent filter matches `application/x-badger` only, and GitHub
   Pages will serve a `.badger` download as `application/octet-stream` (Pages
   supports no custom headers). Tapping a downloaded file may therefore not
   route to Badger. The page already hedges with "if tapping the download does
   nothing, open it from your file manager", but the honest test is: download
   one of the six on your phone, tap it, and see. If it does not open Badger, the
   fix is app-side (broaden the intent filter to match the extension), not a site
   change. I could not test this from here.

4. **New client JS, one small script.** The site spec says no new client JS
   beyond the theme toggle and pagefind; the M-web-4 spec asks for copy buttons.
   I took the later spec and kept the script tiny, local and non-blocking: it
   injects the buttons itself, so with JS off there is no dead control, and the
   prompts are plain selectable text either way. Say the word and the buttons go.

5. **Per-card help links.** The spec says each card links the relevant help
   sections. Six cards repeating the same two links read as noise, so the links
   live once in the "How to import one" section directly under the cards. Easy to
   change if you want them per card.

6. **The gallery duplicates what the app already ships.** These six are the same
   templates seeded inside Badger, which the page says outright. The value is
   being able to read one before installing anything, to hand one to an AI, and
   to have a link to send someone. If you would rather the gallery hold programs
   the app does not seed, that is a content decision and a different session.

7. **The SEO trio was skipped.** Your decision was left unfilled in the request,
   and the build prompt's default is skip unless you said include. Say the word
   and `/guides/stronglifts-5x5-tracker`, `/guides/fitnotes-on-iphone` and
   `/guides/workout-tracker-no-subscription` get their own pass.

## Two app bugs this turned up (not fixed here)

Both are pre-existing, both are in `badger-fit`, neither blocks these pages.

1. **Three seeded program templates silently lose an exercise.** The routine seed
   references `Cable Pushdown`, `Dumbbell Overhead Triceps Extension` and
   `Seated Calf Raise Machine`, none of which exist in the seeded exercise
   catalog (the closest real names are `Tricep Pushdown (Cable)`,
   `Overhead Tricep Extension` and `Calf Raise (Seated)`). `mkEx` returns null
   and the exercise is skipped without complaint, so PPL's Push day ships with
   five exercises instead of six, and Upper/Lower loses one from each of Upper B
   and Lower B. The published files mirror the app exactly, so they have the same
   gap; regenerate them after the fix.

2. **The CSV export has no completion column.** `getAllSetsForCsvExport` selects
   every set row with no `is_complete` or `is_skipped` filter, and the header
   carries neither field, so a routine session that was started and abandoned
   exports as though every set was performed. The AI guide's prompt tells the
   assistant to watch for this, which is a workaround, not a fix.

## Before you merge

- [ ] Read the three pages end to end as the site's owner, in whichever theme you
      prefer, and rule on flag 1.
- [ ] Answer flag 2 (the versioning promise) and flag 4 (the copy buttons).
- [ ] Do the device check in flag 3: download a program on your phone and tap it.
- [ ] Say include or skip on the SEO trio (flag 7).
- [ ] Then, and only then: merge `site/m-web-4` into `main`. That push is what
      deploys badger.fit.
