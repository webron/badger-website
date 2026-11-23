---
name: self-verify
description: Checks Claude runs on its own after changing any badger.fit page, layout, style, component, image or help copy, before reporting the change done, opening or updating a PR, or recording a demo video. Use when asked to verify, check, test or confirm a website change works, to run or preview the site to see a change, or before merging a site/ or release/ branch. Covers the build, internal links and #anchors, layout shift (CLS), the Lighthouse budget, the prose check and screenshots, what to do when one fails, and what output proves each check.
---

# Self-verify a badger.fit change

Run these yourself after a change and before you say it works. Ron does not run them. The
output of each check is the proof: quote it in the PR body or the report, never paraphrase
it. Claude Code's built-in `run` skill (launch the app to see a change) defers to this one
here.

Run from the repo root (a worktree is fine; symlink or install `node_modules` first).

## The checks, in order

| # | Check | Command | Proof |
|---|---|---|---|
| 1 | Build | `npm run build` | `[build] Complete!` and the page count |
| 2 | Source anchors (what CI runs) | `npm run test:anchors` | `# fail 0` |
| 3 | Every internal link and `#anchor` in the built site | `node tool/check-dist-links.mjs` | `OK: N internal links in M pages all resolve.` |
| 4 | Lighthouse budget and CLS | `node tool/lighthouse-budget.mjs [pages]` | one `OK`/`MISS` line per page with the four scores and CLS |
| 5 | Prose (any copy change) | `/Users/ron/Development/badger-fit/tools/prose_check.py <changed .astro files>` | `0 banned`, and no file over budget that was not over on the base branch |
| 6 | Screenshots of each changed page | built-in browser, see below | the images, attached or embedded |

Checks 3 and 4 read `dist/`, so run check 1 first and again after any fix.

**Check 4 pages.** Default is `/`, `/promise/` and `/help/getting-started/`. Add every page
the change touched: `node tool/lighthouse-budget.mjs / /help/csv-export/`. It runs Lighthouse
13.4.0 three times per page (mobile emulation) and takes the median. It takes about 20 s
per run and needs Google Chrome.

**Budget** (from `docs/2026-07-16-journal-site-redesign-spec.md` section 7): 95 or more on
Performance, Accessibility, Best Practices and SEO, and CLS exactly 0. A page that was already
under budget on the base branch must not get worse: run check 4 on the base branch too
(`git stash` is shared with other sessions, so use a second worktree) and compare. Known
baseline on 2026-11-22: home Performance about 92, every other number in budget.

**Check 6.** Run `npm run preview` through the built-in browser's `preview_start` (add a
`.claude/launch.json` entry if there is none for preview), then screenshot each changed page
at 360, 390, 768 and 1280 px, in both themes (the paper/slate toggle and
`prefers-color-scheme`). Look at them: no horizontal scroll, nothing overlapping, the change
is visible. These screenshots are the dry run for the `demo-video` skill when the change is
user-visible.

## When a check fails

- **Build fails:** fix the error it names. Never commit a red build; CI builds every PR.
- **Broken link or anchor:** the line names the page, the href and what is missing. Fix the
  link or the target's heading/`id=`. Do not add to `KNOWN` in `tool/check-dist-links.mjs`
  unless the miss is harmless by design, with a comment saying why.
- **Lighthouse MISS:** rerun that page once. Still a miss and the base branch passes: your
  change caused it. Open the full report to see which audit dropped (`npx --yes
  lighthouse@13.4.0 <url> --view`) and fix that. Common causes here: an image without
  `width`/`height` (CLS), a new font or script (render-blocking), an unsized embed.
- **CLS above 0:** something moves after first paint. Usually an image or font without
  reserved space. Fix it; do not loosen the budget.
- **Prose check flags:** rewrite the sentence; follow `badger-fit/docs/writing_style.md`.
- **A check cannot run** (exit 2, Chrome missing, port busy): say so in the report with the
  error. Never report it as passed.

## What this does not cover

- The release rules in `CLAUDE.md` (only the release branch merges to `main`, on Ron's word).
- Whether the help text matches the app's behavior: check that against the app repo.
- `npm run test:sheets`, needed only when `public/programs/` changes.
