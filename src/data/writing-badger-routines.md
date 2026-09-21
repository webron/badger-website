<!--
  A COPY of badger-fit `badger-skill/skills/writing-badger-routines/SKILL.md`,
  written by `scripts/sync-skill.mjs`. Do not edit it here: edit the skill and
  re-run the script, or the two disagree and only one of them is tested.

  The YAML frontmatter is dropped on the way in. It is plumbing for a skill
  loader and means nothing to somebody pasting this into a chat.
-->
# Writing a routine for Badger

Badger imports a routine from a `.badger` file: one JSON object, saved with a
`.badger` extension. The person opens it from Files (iOS) or the share sheet
(Android), sees a preview, and taps Import.

The full schema is at <https://badger.fit/badger-format/> and it is the
authority. This does not repeat it. What follows is the short list of things
that go wrong, plus one worked example that exercises every key the routine
format defines: `example-routine.badger` beside this file, or
<https://badger.fit/skill/example-routine.badger> if you are reading this
pasted into a chat.

If the program uses anything past the plain `reps` and `weight` case, read the
format page first. If you cannot open links, ask for the page to be pasted in.

## The shape

The smallest file that imports:

```json
{
  "badger": "share/v1",
  "type": "routine",
  "payload": {
    "routine": { "name": "Push Pull Legs" },
    "exercises": [
      { "name": "Flat Barbell Bench Press", "type": "weight_reps", "category_name": "Chest" }
    ],
    "days": [
      {
        "name": "Push",
        "exercises": [
          {
            "exercise_name": "Flat Barbell Bench Press",
            "exercise_type": "weight_reps",
            "predefined_sets": [
              { "is_warmup": false, "reps": 8 },
              { "is_warmup": false, "reps": 8 },
              { "is_warmup": false, "reps": 8 }
            ]
          }
        ]
      }
    ]
  }
}
```

`badger` and `type` are the envelope and are not optional. A `type` other than
`gym`, `machines` or `routine` makes the whole file unreadable, and a `badger`
value other than `share/v1` warns the user that the file came from a newer
version. `app_version` and `created_at` are written by the app and can be left
out of a file you write by hand.

Everything else is a key in `payload`: `routine`, `days`, `exercises` and
`machines`. Only `routine` is required, but a day with no resolvable exercises
imports as an empty day, which is not what anybody wanted.

## The rules that get broken

**1. Every exercise a day names must be defined in the same file.** A day slot
carries `exercise_name` and `exercise_type`; `payload.exercises` carries the
matching `name` and `type`. If the two disagree, or the definition is missing,
the slot is dropped silently and the day comes out one exercise shorter. The
same rule applies to `alternatives` and to `percent_reference`. Write both keys
on every slot and make them identical to the definition.

**2. Use the person's own exercise names.** Import matches an exercise against
their library by name and type, trimmed and case-insensitive. "Bench Press"
when their library says "Flat Barbell Bench Press" does not fail: it creates a
second exercise, and their whole bench history stops feeding the new routine.
If they pasted a Badger snapshot, copy the names out of it exactly. If they did
not, ask rather than guess.

**3. Array order is the order.** Days, exercises within a day, sets within a
slot and clauses within a rule are all ordered by their position in the array.
There is no `sort_order` key. Writing one is harmless and does nothing.

**4. `scheduled_days` is an array of integers, 1 for Monday to 7 for Sunday.**
Not day names, not 0-based. An entry outside 1 to 7 is dropped without a word.
Omit the key when the day is not on a fixed weekday.

**5. Enum values are snake_case.** `weight_reps`, `plate_loaded`,
`last_performance`, `all_sets_met`. Not `weightReps`, not `Weight + Reps`.

**6. A weight carries its unit.** Write `weight` with `weight_unit`, either
`"kg"` or `"lbs"`. An untagged weight is read as kilograms, which turns a
225 lb squat into a 496 lb one. Never convert a number the person gave you;
write it in the unit they said it in and tag it.

**7. Never invent a starting weight.** `weight` is optional. Leave it out and
Badger fills the set from what the person last lifted, which is what
`"weight_source": "last_performance"` on the routine means and is almost always
what they want. A number you made up looks authoritative on the set row and is
the one thing in the file they cannot tell apart from a number they chose. If
the program genuinely needs specific loads, ask for their current numbers
rather than guessing at them.

**8. Reps, ranges and open sets are three different things.** `reps` alone is
an exact target. `reps` with `reps_max` is a range, and `reps_max` must be
greater than `reps` or it is dropped. `is_amrap: true` makes `reps` a minimum
with no top, and it cancels `reps_max`. A warmup set gets none of this: on a
set with `is_warmup: true`, `reps_max`, `is_amrap`, `target_rpe`, `target_rir`
and `is_progression_driver` are all cleared on import.

**9. A progression rule is all or nothing.** If any part of `progression` is
malformed the whole rule is dropped and the routine imports without it. The
ways to lose one:

- an unrecognized `trigger`, `action`, `target`, `cadence` or `reference_kind`;
- no `clauses`, or a last clause whose trigger is not `always`. Every rule ends
  with `always`, and an `always` anywhere but last is also a drop, because it
  makes the clauses after it dead;
- `driver_reps_at_least` or `driver_reps_between` with no `reps_min`, or a
  `reps_max` below the `reps_min`;
- `add_absolute` or `set_from_remembered` with no `amount`, or `add_percent`
  with no `percent`;
- `"target": "reference"` while `"reference_kind": "working_weight"`. Moving a
  training max needs `"reference_kind": "training_max"`;
- a clause an earlier clause already swallows, for example
  `consecutive_failures_at_least: 2` placed above `consecutive_failures_at_least: 3`.
  The first matching clause wins, so the second could never fire.

If the program is plain linear progression, three clauses cover it: a success
clause, a failure clause and the terminal `always`. See the Lower day of the
example file.

**10. One progression driver per slot, per week, never on a warmup.** The driver
is the set whose logged reps the `driver_reps_*` triggers read. Extra ones are
cleared, first in array order wins.

**11. `target_rpe` and `target_rir` are mutually exclusive.** A set states one
or the other, never both. RPE runs 6 to 10, RIR 0 to 5. They are the same
statement in two dialects, so pick the one the program was written in.

**12. A waved day states `cycle_length`, and its sets state `week_index`.**
`week_index` is 0-based and must be below `cycle_length`; a set outside that
range is quietly rewritten to run in every week. A set with no `week_index`
runs in every week on purpose, which is how accessory work rides through a
four-week wave without being written out four times.

**13. Unknown keys are ignored.** Inventing a field is harmless and achieves
nothing. There is no key for a training max, a start date, a deload percentage
or a note on a day. If the program needs one of those said out loud, put it in
the routine's `notes` or a rule's `note`, which are free text nothing parses.

## What the file does not carry

A `.badger` routine is a program, not somebody's numbers. It carries no
history, no training maxes, no counters or stage indexes, and no progress
against a rule. Percent sets travel with a `weight` alongside
`percent_of_reference` so the person sees a usable number before they have set
a reference of their own; write both.

Superset and progression group keys are opaque strings. Any slots sharing a
`superset_key` within a day are one superset, and any sharing a
`progression_group_key` within the routine are one progression. The importer
never reads them and allocates its own, so `"ss-a"` is as good a key as
anything.

## Before you hand it over

- Parse it as JSON. A trailing comma is the commonest reason an import fails.
- Every `exercise_name` in a day, in `alternatives` and in `percent_reference`
  appears in `payload.exercises` with the same `type`.
- Every `default_machine_name` appears in `payload.machines`, or is a machine
  the person already owns.
- Every rule's last clause is `always`.
- Name the file after the routine, ending in `.badger`.

Tell the person that importing a routine whose name they already use creates
"Name (imported)" rather than overwriting, so trying one is safe.
