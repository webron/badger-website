#!/usr/bin/env node
// Copies the published .badger routine-writing skill out of the badger-fit
// repo into this one, where /guides/ai serves it as a pasteable block.
//
// The skill's own home is badger-fit `badger-skill/`, where two tests hold it
// honest: one asserts the example exercises every key the writer can emit, the
// other imports the example through the real importer. Neither can run from
// here, so this is a copy step with a script rather than a cross-repo test -
// the same arrangement the program gallery files already have.
//
// Run it whenever SKILL.md changes:
//   node scripts/sync-skill.mjs [path-to-badger-fit]
//
// It rewrites two files and prints what moved. The only edit it makes is
// dropping the skill's YAML frontmatter, which is plumbing for a skill loader
// and means nothing to somebody pasting the text into a chat. Everything else
// is byte-for-byte, so the page cannot quietly disagree with the skill.

import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { join, resolve } from 'node:path';

const repo = process.argv[2] ?? resolve(process.cwd(), '..', 'badger-fit');
const skillDir = join(repo, 'badger-skill', 'skills', 'writing-badger-routines');

if (!existsSync(skillDir)) {
  console.error(`No skill at ${skillDir}.`);
  console.error('Pass the badger-fit checkout as an argument if it is elsewhere.');
  process.exit(1);
}

const HEADER = `<!--
  A COPY of badger-fit \`badger-skill/skills/writing-badger-routines/SKILL.md\`,
  written by \`scripts/sync-skill.mjs\`. Do not edit it here: edit the skill and
  re-run the script, or the two disagree and only one of them is tested.

  The YAML frontmatter is dropped on the way in. It is plumbing for a skill
  loader and means nothing to somebody pasting this into a chat.
-->
`;

const raw = readFileSync(join(skillDir, 'SKILL.md'), 'utf8');
if (!raw.startsWith('---\n')) {
  console.error('SKILL.md has no frontmatter to strip. Check the file.');
  process.exit(1);
}
const body = raw.split('\n---\n').slice(1).join('\n---\n').replace(/^\n+/, '');

const out = join('src', 'data', 'writing-badger-routines.md');
writeFileSync(out, HEADER + body);
console.log(`${out}  (${body.split(/\s+/).length} words)`);

// The example the skill names by URL, so the pasted form works too.
const example = join('public', 'skill', 'example-routine.badger');
writeFileSync(example, readFileSync(join(skillDir, 'example-routine.badger')));
console.log(example);
