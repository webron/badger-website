import { test } from 'node:test';
import assert from 'node:assert/strict';
import { addHeadingAnchors, slugify, headingText } from './heading-anchors.mjs';

test('a heading with no id gets a slug id and a link to it', () => {
  const out = addHeadingAnchors('<h2>Organize days and routines</h2>');
  assert.match(out, /^<h2 id="organize-days-and-routines">Organize days and routines<a class="heading-anchor" href="#organize-days-and-routines"/);
  assert.match(out, /aria-label="Link to Organize days and routines"/);
});

test('a hand-written id is kept, never replaced', () => {
  const out = addHeadingAnchors('<h3 id="schedule-a-day">Schedule a day</h3>');
  assert.match(out, /^<h3 id="schedule-a-day">Schedule a day<a class="heading-anchor" href="#schedule-a-day"/);
  assert.equal((out.match(/ id=/g) || []).length, 1);
});

test('a generated id never collides with another id on the page', () => {
  const html = '<p id="tempo">x</p><h3>Tempo</h3><h3>Tempo</h3>';
  const out = addHeadingAnchors(html);
  assert.match(out, /<h3 id="tempo-2">/);
  assert.match(out, /<h3 id="tempo-3">/);
});

test('a hand-written id later in the page still wins over a generated one', () => {
  const html = '<h2>Starting</h2><h3 id="starting">Start a routine</h3>';
  const out = addHeadingAnchors(html);
  assert.match(out, /<h2 id="starting-2">Starting/);
  assert.match(out, /<h3 id="starting">Start a routine/);
});

test('other attributes are kept and h1/h4 are left alone', () => {
  const out = addHeadingAnchors('<h1>Title</h1><h2 class="x" data-astro-cid-a>Body &amp; weight</h2><h4>Small</h4>');
  assert.match(out, /^<h1>Title<\/h1>/);
  assert.match(out, /<h2 class="x" data-astro-cid-a id="body-weight">Body &amp; weight<a /);
  assert.match(out, /<h4>Small<\/h4>$/);
  assert.match(out, /aria-label="Link to Body &amp; weight"/);
});

test('inline markup in the heading is kept and stripped from the slug', () => {
  const out = addHeadingAnchors('<h3>The <strong>Day options</strong> menu</h3>');
  assert.match(out, /^<h3 id="the-day-options-menu">The <strong>Day options<\/strong> menu<a /);
});

test('running twice does not add a second link', () => {
  const once = addHeadingAnchors('<h2>Once</h2>');
  assert.equal(addHeadingAnchors(once), once);
});

test('a heading with no letters or digits is left alone', () => {
  assert.equal(addHeadingAnchors('<h2>&mdash;</h2>'), '<h2>&mdash;</h2>');
});

test('slugify and headingText', () => {
  assert.equal(slugify("5/3/1: Boring But Big"), '5-3-1-boring-but-big');
  assert.equal(slugify('Café  set-up'), 'cafe-set-up');
  assert.equal(headingText('Don&#39;t <em>skip</em>'), "Don't skip");
});
