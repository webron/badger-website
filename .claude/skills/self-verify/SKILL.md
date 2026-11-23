---
name: self-verify
description: Checks Claude runs on its own after changing any badger.fit page, layout, style, component, image or help copy, before reporting the change done, opening or updating a PR, or recording a demo video. Use when asked to verify, check, test or confirm a website change works, to run or preview the site to see a change, to prove a site bug is fixed, or before merging a site/ or release/ branch. Covers the build, internal links and #anchors, layout shift (CLS), the Lighthouse budget, the prose check, screenshots (before and after for a bug fix), auth and seed state for the preview, what to do when a check fails or is blocked, and what output proves each check.
---

# Self-verify a badger.fit change

Run these yourself after a change and before you say it works. Ron does not run them. The
output of each check is the proof: quote it in the PR body or the report, never paraphrase
it. Claude Code has no built-in skill named verify; its closest one is `run` (launch the
app to see a change). Use `run`, or the built-in browser's `preview_start`, to bring the site
up for check 6; this skill adds the checks and the proof.

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

Section 7 also asks for AA text contrast, no new client JS and no external requests. No
script checks those. When a change touches colors, scripts or embeds, check them by hand
(contrast of the changed token pairs; `git diff` for new `<script>` or external URLs) and say
what you checked.

**Check 6.** Run `npm run preview` through the built-in browser's `preview_start` (add a
`.claude/launch.json` entry if there is none for preview), then screenshot each changed page
at 360, 390, 768 and 1280 px, in both themes (the paper/slate toggle and
`prefers-color-scheme`). Look at them: no horizontal scroll, nothing overlapping, the change
is visible. These screenshots are the dry run for the `demo-video` skill when the change is
user-visible.

## Auth and seed state

**Auth.** The site has no login, accounts or API keys, so no check needs a sign-in. Never sign
in to GitHub, GoatCounter, Cloudflare or a store console to verify a page; the stats tools in
`tool/` are not part of this skill.

**Seed state** for check 6. A fresh preview tab is the state a first-time visitor sees. Set
these on purpose, and say which you set:

- **Analytics.** `npm run preview` serves the production build, so GoatCounter and the
  Cloudflare beacon load. count.js ignores localhost; the beacon does not. Before browsing,
  run `localStorage.setItem('skipgc', 't')` in the preview tab and reload, so your visits are
  not sent to Ron's numbers.
- **Theme.** The paper/slate choice is saved in `localStorage.theme` (`light` or `dark`). With
  no saved value the page follows `prefers-color-scheme`. Shoot the OS preference with the
  browser's `colorScheme` (nothing saved), then the toggle. Run
  `localStorage.removeItem('theme')` before the next page so one choice does not leak into
  the next shot.
- **Search.** The Pagefind index exists only after `npm run build`; `npm run dev` returns no
  results. Check search on the preview server.
- **Program files.** `/programs/` prints the app version read from `public/programs/*.badger`.
  A stale version there means the files need regenerating (see `CLAUDE.md`), not a page bug.

## Bug fixes: before and after

For a bug fix, the proof is a pair of screenshots: one showing the bug on the base branch
(a second worktree, since `git stash` is shared) and one showing it fixed on your branch,
at the same URL, width and theme. Put them side by side in the PR body, labeled before and
after. A fix with only an after shot is not proven.

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

## When a check hits a blocker, fix this file

If a check cannot run, or runs only after a workaround (a missing dependency, a changed flag,
a busy port, a tool that needs an extra step), and you find the fix, add it to the list below
in the same branch as your change: the symptom, the fix, and why it works, so the next
session can handle a blocker that looks a little different. Edit or delete a line that
turned out wrong. Problems in the page itself do not go here; fix the page.

- **`Cannot find module` or `astro: command not found` in a worktree:** `node_modules` is
  not shared between worktrees. Symlink the main checkout's (`ln -s
  /Users/ron/Development/badger-website/node_modules`) or run `npm ci`. The worktree has only tracked files.
- **`Port 4329 is already in use`** (check 4): a preview from an earlier run is still up.
  Stop it (`lsof -ti :4329`, then kill that PID) and rerun. The script refuses a busy port
  so it never measures a stale build.

## What this does not cover

- The release rules in `CLAUDE.md` (only the release branch merges to `main`, on Ron's word).
- Whether the help text matches the app's behavior: check that against the app repo.
- `npm run test:sheets`, needed only when `public/programs/` changes.
