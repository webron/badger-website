// Build the homepage phone-frame captures from the app repo's demo pipeline.
//
// Source: badger-fit demo/marketing/screens/*.png - raw 1080x2400 device
// captures of the seeded demo dataset (see that repo's demo/README.md). We take
// the raw captures, NOT the branded 1080x1920 Play composites: the site frames
// the screens in its own journal chrome.
//
// Each screen ships in both app themes. Paper (light) and slate (dark) are the
// app's own theme names; the site swaps between them so the frame always matches
// the theme the page is rendering in.
//
// Run:  node tool/build-screenshots.mjs
// Then commit the generated files in public/assets/screenshots/.

import sharp from 'sharp';
import { mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SRC = '/Users/ron/Development/badger-fit/demo/marketing/screens';
const OUT = path.join(HERE, '..', 'public', 'assets', 'screenshots');

// Measured against the 1080x2400 captures: the OS status bar occupies the top
// 96px (its glyphs sit at y 48-80) and the gesture pill the bottom 62px. Both
// are the phone's chrome, not Badger's, so they come off - same reasoning as the
// store renderer's STATUS_CROP.
const CROP_TOP = 96;
const CROP_BOTTOM = 62;

// The widest frame renders at 244 CSS px, so 540 covers it at better than 2x.
const OUT_WIDTH = 540;

const SHOTS = [
  { src: 'today', out: 'today' },
  { src: 'training', out: 'training' },
  { src: 'progress', out: 'progress' },
];

await mkdir(OUT, { recursive: true });

for (const shot of SHOTS) {
  for (const [theme, suffix] of [
    ['slate', ''],
    ['paper', '_light'],
  ]) {
    const from = path.join(SRC, `${shot.src}${suffix}.png`);
    const to = path.join(OUT, `${shot.out}-${theme}.webp`);

    const meta = await sharp(from).metadata();
    const info = await sharp(from)
      .extract({
        left: 0,
        top: CROP_TOP,
        width: meta.width,
        height: meta.height - CROP_TOP - CROP_BOTTOM,
      })
      .resize({ width: OUT_WIDTH })
      .webp({ quality: 82, effort: 6 })
      .toFile(to);

    console.log(`${path.basename(to)}  ${info.width}x${info.height}  ${Math.round(info.size / 1024)} KB`);
  }
}
