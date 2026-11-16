// One place for the names and the order of the site's pages, so the header, the
// phone menu, the footer, the sidebar, the 404 page and the "Next" block cannot
// drift apart. One name per page: change a label here and every surface follows.
//
// Paths are compared without a trailing slash ('/help/logging'), matching what
// the layouts already compute. Links keep the slash.

export const strip = (p) => (p || '').replace(/\/$/, '') || '/';

// The four header entries. `match` decides the current-section state, so Programs
// lights on its own page and Guides also lights on the 5/3/1 calculator.
export const mainNav = [
  { href: '/help/', label: 'Help', match: (p) => p === '/help' || p.startsWith('/help/') },
  {
    href: '/guides/',
    label: 'Guides',
    match: (p) => p === '/guides' || p.startsWith('/guides/') || p === '/tools/531-calculator',
  },
  { href: '/programs/', label: 'Programs', match: (p) => p === '/programs' },
  { href: '/glossary/', label: 'Glossary', match: (p) => p === '/glossary' },
];

// Where "Search" in the phone menu and the header search icon go: the field at the top of the help index.
export const searchHref = '/help/#help-search';

// Footer, in three rows. Same links as before, regrouped.
export const footerGroups = [
  {
    label: 'Learn',
    links: [
      { href: '/help/', label: 'Help' },
      { href: '/guides/', label: 'Guides' },
      { href: '/programs/', label: 'Programs' },
      { href: '/glossary/', label: 'Glossary' },
      { href: '/badger-format/', label: '.badger file format' },
    ],
  },
  {
    label: 'Badger',
    links: [
      { href: '/', label: 'Home' },
      { href: '/promise/', label: 'The promise' },
      { href: '/changelog/', label: 'Changelog' },
      { href: '/about/', label: 'About' },
      { href: '/about/#contact', label: 'Contact' },
    ],
  },
  {
    label: 'Legal',
    links: [
      { href: '/legal/privacy/', label: 'Privacy' },
      { href: '/legal/terms/', label: 'Terms' },
    ],
  },
];

// Which part of the site a path belongs to. The sidebar orders its groups by it
// and the toggle label follows it. Legal pages belong to none.
export function sectionOf(p) {
  p = strip(p);
  if (p === '/help' || p.startsWith('/help/')) return 'help';
  if (p === '/guides' || p.startsWith('/guides/') || p.startsWith('/tools/')) return 'guides';
  if (['/glossary', '/badger-format', '/programs', '/changelog'].includes(p)) return 'reference';
  return null;
}

// The mobile sidebar toggle. Named for what the reader is looking at: the help
// index and the guides index say so, everywhere else it is plain "Browse".
export function browseLabel(p) {
  p = strip(p);
  if (p === '/help') return 'Browse help topics';
  if (p === '/guides') return 'Browse guides';
  return 'Browse';
}

// Reading order of the help pages, for the default "Next" block.
export const helpOrder = [
  ['/help/getting-started/', 'Getting started'],
  ['/help/logging/', 'Logging workouts'],
  ['/help/set-types/', 'Drop sets, myo-reps and rest-pause'],
  ['/help/exercises/', 'Exercises'],
  ['/help/routines/', 'Routines'],
  ['/help/progression/', 'Progression'],
  ['/help/gyms/', 'Gyms and equipment'],
  ['/help/history/', 'History'],
  ['/help/progress/', 'Progress tracking'],
  ['/help/goals/', 'Goals per lift'],
  ['/help/body/', 'Body tracking'],
  ['/help/tools/', 'Tools and calculators'],
  ['/help/settings/', 'Settings and data'],
  ['/help/phone-migration/', 'Moving to a new phone'],
];

// Reading order of the guides: how you train, moving over, programs, the rest.
export const guideOrder = [
  ['/guides/just-lifting/', 'Just want to lift?'],
  ['/guides/program-runner/', 'Running a program'],
  ['/guides/machines-and-cardio/', 'Machines and cardio'],
  ['/guides/minimal-equipment/', 'Training with no or minimal equipment'],
  ['/guides/optimizer/', 'Show me the data'],
  ['/guides/switching/', 'Switching to Badger'],
  ['/guides/strong-alternative/', 'Moving to Badger from Strong'],
  ['/guides/hevy-alternative/', 'Moving to Badger from Hevy'],
  ['/guides/fitnotes-alternative/', 'Moving to Badger from FitNotes'],
  ['/guides/fitnotes-on-iphone/', 'FitNotes on iPhone'],
  ['/guides/moving-from-stronglifts/', 'Moving from StrongLifts to Badger'],
  ['/guides/stronglifts-5x5-tracker/', 'StrongLifts 5x5 in Badger'],
  ['/guides/gzclp-app/', 'GZCLP in Badger'],
  ['/guides/531-app/', '5/3/1 Boring But Big in Badger'],
  ['/guides/nsuns-app/', 'nSuns 531LP in Badger'],
  ['/guides/madcow-app/', 'Madcow 5x5 in Badger'],
  ['/guides/starting-strength-app/', 'Starting Strength in Badger'],
  ['/guides/workout-tracker-no-subscription/', 'A workout tracker with no subscription'],
  ['/guides/ai/', 'Use your own AI'],
  ['/guides/overview/', 'Everything Badger does'],
];

const programGuides = new Set(guideOrder.slice(11, 17).map(([h]) => strip(h)));

export const getTheApp = { href: '/#download', label: 'Get the app', note: 'App Store and Google Play.' };

// The default "Next" links for a path, or [] when the page should end plainly.
// A page can pass its own `next` to HelpLayout instead.
export function defaultNext(p) {
  p = strip(p);
  const at = (list) => list.findIndex(([h]) => strip(h) === p);

  let i = at(helpOrder);
  if (i >= 0) {
    const out = [];
    const next = helpOrder[i + 1];
    if (next) out.push({ href: next[0], label: next[1], note: 'Next topic' });
    out.push({ href: '/help/', label: 'All help topics', note: 'Search or browse the whole list.' });
    if (out.length < 3) out.push({ href: '/guides/', label: 'Guides', note: 'Walkthroughs by how you train.' });
    return out;
  }

  i = at(guideOrder);
  if (i >= 0) {
    const out = [];
    const next = guideOrder[i + 1];
    if (next) out.push({ href: next[0], label: next[1], note: 'Next guide' });
    if (programGuides.has(p)) out.push({ href: '/programs/', label: 'Programs', note: 'Download the program files.' });
    else out.push({ href: '/guides/', label: 'All guides', note: 'Back to the list.' });
    out.push(getTheApp);
    return out;
  }
  return [];
}
