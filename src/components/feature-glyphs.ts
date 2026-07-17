/**
 * Names of the feature-ledger line glyphs drawn by FeatureGlyph.astro.
 *
 * Lives in its own module rather than in the component's frontmatter: Astro
 * hands the frontmatter to esbuild as JS, so a `export type` union there fails
 * the build.
 */
export type GlyphName =
  | 'barbell'
  | 'stopwatch'
  | 'program'
  | 'trend'
  | 'gym'
  | 'plate'
  | 'compare'
  | 'import'
  | 'wave'
  | 'shield';
