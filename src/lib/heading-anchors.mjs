// Gives every h2 and h3 in a help or guide page a stable id and a small link
// icon, so a reader can copy a URL that lands on that section.
//
// Runs at build time over the rendered article HTML (HelpLayout calls it), so
// the ids are in the shipped HTML. A client-side version would add the ids
// after the browser had already tried to scroll to the #fragment, and a
// shared link would open at the top of the page.
//
// An id written by hand in the page always wins: the sidebar, the index pages
// and other pages link to those, and renaming one would break the link. A
// generated id is the heading text as a slug ("Organize days and routines" ->
// "organize-days-and-routines"), suffixed -2, -3 only if it would collide with
// another id on the page.

const HEADING = /<h([23])((?:\s[^>]*)?)>([\s\S]*?)<\/h\1>/g;
const ID_ATTR = /\sid\s*=\s*"([^"]*)"/;
const ALL_IDS = /\sid\s*=\s*"([^"]*)"/g;

const ENTITIES = {
  amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ',
  mdash: '\u2014', ndash: '\u2013', lsquo: '\u2018', rsquo: '\u2019',
  ldquo: '\u201c', rdquo: '\u201d', hellip: '\u2026', times: '\u00d7',
  middot: '\u00b7', rarr: '\u2192',
};

function decodeEntities(text) {
  return text.replace(/&(#x[0-9a-f]+|#[0-9]+|[a-z]+);/gi, (match, code) => {
    if (code[0] === '#') {
      const n = code[1] === 'x' || code[1] === 'X' ? parseInt(code.slice(2), 16) : parseInt(code.slice(1), 10);
      return Number.isFinite(n) ? String.fromCodePoint(n) : match;
    }
    // An entity this table does not know is dropped, so its name never ends
    // up in a slug as if it were a word of the heading.
    return ENTITIES[code] ?? ENTITIES[code.toLowerCase()] ?? ' ';
  });
}

function escapeAttr(text) {
  return text.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
}

export function headingText(innerHtml) {
  return decodeEntities(innerHtml.replace(/<[^>]*>/g, '')).replace(/\s+/g, ' ').trim();
}

export function slugify(text) {
  return text
    .toLowerCase()
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

// A hash mark drawn as four strokes. It inherits the link color.
const ICON =
  '<svg aria-hidden="true" focusable="false" viewBox="0 0 16 16" width="14" height="14">' +
  '<path d="M6 2.5 4.5 13.5M11.5 2.5 10 13.5M2.5 6h11M2 10.5h11" fill="none" ' +
  'stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>';

export function addHeadingAnchors(html) {
  const used = new Set();
  for (const m of html.matchAll(ALL_IDS)) used.add(m[1]);

  return html.replace(HEADING, (whole, level, attrs, inner) => {
    if (inner.includes('class="heading-anchor"')) return whole;

    const text = headingText(inner);
    let id = attrs.match(ID_ATTR)?.[1];

    if (!id) {
      const base = slugify(text);
      if (!base) return whole;
      id = base;
      for (let n = 2; used.has(id); n++) id = `${base}-${n}`;
      used.add(id);
      attrs = `${attrs} id="${id}"`;
    }

    const label = escapeAttr(`Link to ${text || 'this section'}`);
    const link =
      `<a class="heading-anchor" href="#${escapeAttr(id)}" aria-label="${label}" title="Copy link to this section">` +
      `${ICON}</a>`;
    return `<h${level}${attrs}>${inner}${link}</h${level}>`;
  });
}
