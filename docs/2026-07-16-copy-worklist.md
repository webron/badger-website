# Website copy worklist - Field Journal redesign

> Source of truth for all outward-facing copy in the redesign. Drafted 2026-07-16
> (Fable design session), grounded in `badger-fit/docs/competitive_research_2026-07.md`
> Part 12 (gap audit). **Status meanings:** APPROVED = Ron signed off on the exact
> wording in the design session; DRAFT = direction approved, exact wording still
> needs Ron's sign-off before the site deploys. Nothing deploys before the app
> redesign ships regardless of status.
>
> House writing rules apply to every string on the site: no em-dashes or
> en-dashes, no "not X, it's Y" constructions, straight quotes, plain direct
> voice. The future-proofing rule (spec §1.3) applies to every privacy claim:
> phrase as never required / opt-in, never as an absolute.

## 1. Homepage

### Hero - APPROVED (headline), DRAFT (sub)

- Kicker: `WORKOUT & STRENGTH TRACKER · ANDROID & IOS`
- H1: `As capable as the big trackers. As private as a notebook.`
  (Approved 2026-07-16. Revisit only if a paid tier launches; Ron flagged the
  potential future conflict and accepted it for now.)
- Sub: `Badger logs your sets, runs your programs, and tracks your PRs, and it
  keeps all of it on your phone. No account needed, no subscription, no ads.`
- Meta description / OG description should carry the same positioning:
  `Badger is a workout and strength tracker for Android and iOS. As capable as
  the big trackers, as private as a notebook. No account needed, no
  subscription, works offline.` (DRAFT)

### Positioning strip - DRAFT (this is research Part 12 item P4)

| Value | Detail line |
|---|---|
| No account needed | no sign-up, no login |
| No subscription | free, no caps |
| Works offline | basement-gym proof |
| Your data stays yours | on your phone, export anytime |

### Feature ledger - DRAFT (10 rows; fixes the missing-StrongLifts gap, P5)

1. **Logging that keeps up** - Weight, reps, time, distance, whatever the
   exercise needs. Warmup sets, RPE, RIR, tempo, and per-set notes included.
2. **Rest timer** - Auto-starts after each working set. Per-exercise defaults,
   live countdown on your lock screen, sound or vibration.
3. **Routines and programs** - Build your own or start from 7 built-in programs
   (StrongLifts, 5/3/1, PPL, and more). Supersets, scheduled days, predefined sets.
4. **Progress you can read** - PR detection for every exercise type, estimated
   1RM, 12+ graphs per exercise, activity heatmap, weekly volume by muscle group.
5. **Your gym, modeled** - Track which gym and which machine every set was done
   on. Machine-scoped PRs, real weight increments, attachments and grips.
6. **Plate calculator** - Barbell, machine, and single-lever modes. Finds the
   best combination from the plates your gym actually has.
7. **Planned vs. actual** - Finish a routine workout and the summary shows what
   you hit against what the plan asked for, set by set.
8. **Bring your history** - Import from FitNotes, Strong, Hevy, or StrongLifts.
   Export every set to CSV or back up the full database anytime.
9. **Deload, handled** - Optional deload detection by time, RPE, or stalled
   lifts. Reduces the load for a week and never lets it drag your next session down.
10. **Backup on your terms** - Automatic backup to a private folder in your own
    Google Drive, or a plain file you keep wherever you like. Optional, off by
    default. (Never say "encrypted backup"; the app does not encrypt the archive.)

### Capable / shouldn't spread - DRAFT

**Everything a tracker should do**

| Row | Annotation |
|---|---|
| Unlimited routines, unlimited history | no free-tier caps |
| Full-depth set logging | RPE · RIR · tempo · warmups |
| PRs and graphs for every exercise type | est. 1RM included |
| Per-gym equipment and machine tracking | machine-scoped PRs |
| Plate calculator and warmup generator | your plates, your increments |
| Imports from four other trackers | FitNotes · Strong · Hevy · StrongLifts |

**Nothing a tracker shouldn't**

| Row | Annotation |
|---|---|
| No account needed | no sign-up, no login, no email |
| No subscription | free, nothing paywalled |
| No ads, no data collection | your training is nobody's product |
| No connection needed | fully offline, syncs with nothing |
| No lock-in | export everything, anytime |
| No streak guilt | no XP, no badges, no nagging |

### Promise teaser - DRAFT

`Your data is yours. That is the whole business model.` + link
`Read the Badger promise →`

(If a paid tier ever launches, "the whole business model" needs revisiting at
the same time as the hero strip.)

### CTA - DRAFT

`Ready to start?` / `Badger is free on Google Play, with an iOS beta open in
TestFlight.` (Update the iOS clause at App Store launch, along with the JSON-LD
`operatingSystem` value which currently claims iOS while it is TestFlight-only.)

### Screenshot caption (placeholder era) - DRAFT

`preview frames · swapped for real screenshots when the app redesign ships`
(This caption exists only until M-web-3; it must never ship to production, since
production deploy is gated on the real screenshots existing.)

## 2. The promise page (`/promise`)

Title: `The Badger promise` · Kicker: `The fine print, in large print` - DRAFT

Lede: `Five commitments about your data and your money. Most tracker regret
comes from one of these five going wrong, so they are written down where you can
hold us to them.` - DRAFT

1. **No account needed** - `Badger works completely without an account. There is
   no sign-up gate and no login wall; tracking your training never requires
   telling us who you are. If Badger ever grows optional cloud features, they
   will be exactly that: optional.` - DRAFT (reframed per the future-proofing
   rule after Ron's 2026-07-16 note about the possible paid account/AI tier)
2. **Your data stays on your phone** - `Workouts live in a local database on
   your device. Badger ships with no analytics and nothing that phones home.
   Nothing leaves your phone unless you turn it on yourself: today that means
   the optional backup to a private app folder in your own Google Drive, and
   anything cloud we ever add will be opt-in the same way.` - DRAFT (same
   reframing; also deliberately avoids the "encrypted" overstatement)
3. **Export anytime** - `Every set exports to CSV. The full database backs up to
   a single file you can keep anywhere. Routines and gym setups share as plain
   files. There is no export tax and no premium gate in front of your own
   numbers.` - DRAFT
4. **Nothing you use moves behind a paywall** - `Everything in Badger today is
   free, with no caps on routines or history. If paid extras ever exist, they
   will be new things. A feature you already rely on will not be taken away and
   sold back to you. Lifters have been burned this way before; not here.` -
   **APPROVED as worded (Ron, 2026-07-16)**
5. **Easy to leave** - `Badger imports from FitNotes, Strong, Hevy, and
   StrongLifts, and it exports everything it holds. If it turns out not to be
   for you, take your history and go. We think easy to leave is the best reason
   to stay.` - DRAFT

Closing line: `A notebook does not spy on you, cap your pages, or charge rent.
Neither does Badger.` / sign-off: `The Badger promise. Hold us to it.` - DRAFT

## 3. Everything else

- Help/guides/glossary/changelog/legal: **content unchanged** in the restyle.
  Only the tip-callout label ("TIP") and purely structural strings may be
  touched. Any copy edit beyond that needs its own worklist entry.
- Footer: add `The promise` link. Keep the rest as is.
- While restyling, grep the site for `encrypt` and fix any Drive-backup
  overstatement to "private backup to your own Google Drive" (bump Last updated
  on legal pages only if their wording actually changes).

## 4. Explicitly out of scope for the website build

- Play listing rewrite (Part 12 P1, P2, P3) and capturing the canonical listing
  text into a tracked doc: separate outward-facing task, Ron approves.
- SEO landing pages (Part 12 P7): post-redesign backlog.
- Store screenshot re-render with a no-account/no-subscription slot (P8): part
  of the store refresh after the app ships.
