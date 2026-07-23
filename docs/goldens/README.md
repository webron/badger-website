# Goldens

## Wordmark: mini-stripe underline, both ways (M-web-0)

Spec section 1.5 left this as a builder judgment call and asked for goldens both
ways. Ron picked icon + text over the mockup's text-only mark; the open question
was whether to keep the mockup's mini-stripe underline beneath the wordmark.

- `wordmark-A-no-underline__{paper,slate}.png` - what shipped in M-web-0.
- `wordmark-B-mini-stripe__{paper,slate}.png` - the mockup's underline, restored.

M-web-0 shipped A. Two reasons, both from the spec itself:

1. The motif rule (section 3, "Stripe motif") allows one stripe element per
   screen region. The full-width band already sits 6px below the wordmark, so B
   puts two stripes in the same region.
2. With the icon restored, the underline sits under the word rather than under
   the mark, so it reads as a text underline. The "g" descender crosses it.

Flipping to B is a CSS-only change in `src/components/Header.astro` if Ron
prefers it. Nothing else depends on the choice.
