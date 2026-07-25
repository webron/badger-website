# SEO trio, pages 1 and 2 - sign-off notes (2026-07-25)

Branch `site/seo-pages`, cut off `site/m-web-4` (not off `main`: the StrongLifts
page links the gallery's `stronglifts-5x5.badger`, which only exists on that
branch). The two branches merge together, on Ron's word.

Built: `/guides/stronglifts-5x5-tracker`, `/guides/workout-tracker-no-subscription`.
Not built: `/guides/fitnotes-on-iphone`, parked for the iOS launch moment.

Source: research Part 12 P7 (the punch list), Part 7 (search language), Part 9
(competitor wounds), Part 5 (FitNotes and StrongLifts detail).

## Why these two read the way they do

Part 7's finding was that the privacy demand people actually type is "no
subscription" and "no account", never "private", which is why the positioning
page leads with money. Part 9's finding was that the loudest complaint across
858 negative competitor reviews is trust betrayal, which is why both pages spend
as much space on limits as on features: a page that only sells is exactly what
the reader has been burned by.

So on both pages the unflattering half is deliberate, not hedging:

- StrongLifts page, "What you still decide yourself": no automatic weight
  increase, no fail-three-drop-ten rule, no stall detection unless switched on,
  no watch app, no sync. Plus a full list of what the CSV import leaves behind.
- No-subscription page, "The catch": no sync, no web or desktop, no watch app,
  iOS is TestFlight, no social, no AI in the app, support is one person.

## Claims checked against the app, not the feature list

Verified against app source at 1.1.1 on 2026-07-25. The ones worth knowing were
checked because a marketer would want to claim more:

| Claim on the page | What the code actually does |
|---|---|
| Template ships with the app: A = squat, bench, row 5x5; B = squat, press 5x5, deadlift 1x5 | `_seedProgramsV24`, folder "Beginner Programs", both days unscheduled so Today rotates them |
| "The template carries the rep scheme and no weights at all" | `mkSets` writes reps and sort order only. Saying otherwise would be the first thing a new user caught |
| "Badger does not add the weight for you" | Suggestion chip only, after 3 sessions at the same top weight with every working set complete. It is display-only and does not fill the field |
| Optional write-back "never invents an increment" | Auto-progress routine weights is off by default, raise-only, records loads already lifted above plan, asks per exercise |
| "No fail three times, drop ten percent rule" | Deload is off by default and is a whole light week at 50% starting the next Monday, not a per-lift reset on missed reps |
| "Nothing decides you have stalled" | Plateau detection off by default, weight-and-reps only, needs 5+ sessions across 21+ days of flat estimated 1RM, and outputs a banner |
| Import leaves behind bodyweight, session times, program name, warmup and failure distinction | Those columns exist in the real export and the parser never indexes them. Every set lands complete and working |
| "will not compute working weights as percentages of a training max" | Nothing in the app does percentage-of-TM. The seeded 5/3/1 BBB is predefined sets plus a note |
| No subscription, no in-app purchase, no ads, no analytics | No billing, ads, or analytics dependency exists in `pubspec.yaml` |

## Trademark hygiene

StrongLifts is someone else's mark. Everything is phrased as compatibility
(Badger reads the CSV their app exports; Badger ships a 5x5 template written for
Badger), never as affiliation. The page title is "StrongLifts 5x5 tracker",
which describes what Badger is, and the h1 is "StrongLifts 5x5 in Badger". The
closing section says in words that there is no affiliation, endorsement, or
sponsorship, and that Badger's own template was written by us from the publicly
known shape of the program. Per Part 13, no Wisconsin references and no mascot
anywhere.

## The competitor roundup

Four rows: FitNotes, Hevy, Strong, StrongLifts, sourced from Parts 5 and 9.

Rules applied, and worth keeping if the table is ever edited:

- **No prices.** Free tiers and prices move, and a stale number about someone
  else's product is worse than none. Rows describe the shape (subscription,
  capped free tier) instead.
- **Each row says what is good about the app.** Hevy is well made, Strong is
  established, FitNotes charges nothing at all. It is a roundup, not a takedown.
- **A checked-on date and a "read their store listing" caveat sit under the
  table**, in fine print, and they are what keeps it honest in six months.

Two claims were softened during the build because the research did not support
them as first written: Strong's forced account is "a lot of" its unhappy reviews
rather than "most" (account and watch sync are roughly level, ~15 and ~16
percent of negatives), and StrongLifts' revoked-lifetime complaints are "a lot
of its recent reviews" rather than "largely" (~31 percent of its negative
corpus).

## Nav placement

Both pages join the help sidebar's Starting Guides group, which is really the
`/guides/*` index (`/guides/ai` and `/guides/overview` already sit there). On
the guides index they get a "More guides" subgroup below the persona picker,
under a caps label over a hairline, rather than being mixed into the picker:
they answer a question the reader arrived with instead of describing how someone
trains. The m-web-4 trailing pointers to `/guides/overview` and `/guides/ai` were
left exactly as they are, so nothing already awaiting sign-off moved.

Header and footer needed no change: both already carry `/guides` as a section.

## Verification

- `npm run build` clean, 28 pages, pagefind indexed, sitemap generated.
- Every internal link across all 28 built pages resolves; same-page fragments on
  the new pages check out too.
- No horizontal scroll at 360, 390, 768, or 1280, on both new pages and the
  guides index.
- All 38 text-on-background pairs across both themes clear 4.5:1, minimum 4.86.
  That includes the new fine-print and table styles.
- No em-dashes, en-dashes, smart quotes, or ellipsis characters in any new or
  changed file.

## Status

All copy is DRAFT pending Ron's sign-off. Nothing deploys; `main` untouched.
