/**
 * The two store URLs, in one place, because they are quoted from more than one
 * file: the badge component, the schema.org graph on the home page, and
 * anywhere else that needs to send someone to a store listing.
 */

/**
 * The App Store listing.
 *
 * The numeric id was read from the App Store Connect API on 2026-08-22. It is
 * assigned when the app RECORD is created, not when a version is approved, so
 * it has existed since the first TestFlight build and does not change.
 *
 * The link resolves only once a version is actually released, so this branch
 * still must not be deployed before the App Store listing is live.
 */
export const APP_STORE_URL = 'https://apps.apple.com/app/id6782743069';

/** The Google Play listing. */
export const PLAY_URL = 'https://play.google.com/store/apps/details?id=fit.badger.app';

/**
 * The TestFlight invite for the iOS beta.
 *
 * Not a download affordance any more. Once iOS shipped on the App Store, the
 * public route to Badger is the store, and this link exists only for people
 * who were already testing and want to keep getting builds early. It is linked
 * from the help section, never from the hero.
 */
export const TESTFLIGHT_URL = 'https://testflight.apple.com/join/wqxnbujx';

/**
 * App Store provider token for campaign links (App Store Connect, Account,
 * Membership details). Empty until Ron supplies it: Apple ignores a campaign
 * token without it, so `appStoreUrl` adds nothing while this is empty.
 */
export const APPLE_PROVIDER_TOKEN = '';

/**
 * A page path as a short campaign name: "/" is "home", "/guides/gzclp-app/"
 * is "guides-gzclp-app". Lowercase letters, digits and hyphens only, so it is
 * safe in both stores' link parameters. It names a page of this site and
 * nothing about the visitor.
 */
export function campaignFor(pathname: string): string {
  const slug = pathname
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
  return (slug || 'home').slice(0, 80);
}

/**
 * The Play listing link tagged with the page that sent the visitor. Play
 * Console reports installs by these utm values under store listing
 * acquisition. The `referrer` value is itself URL-encoded, as Google's
 * link format requires.
 */
export function playUrl(campaign: string): string {
  const referrer = `utm_source=badger.fit&utm_medium=web&utm_campaign=${campaign}`;
  return `${PLAY_URL}&referrer=${encodeURIComponent(referrer)}`;
}

/** The App Store link with a campaign token, once a provider token is set. */
export function appStoreUrl(campaign: string): string {
  if (!APPLE_PROVIDER_TOKEN) return APP_STORE_URL;
  return `${APP_STORE_URL}?pt=${APPLE_PROVIDER_TOKEN}&ct=${campaign}&mt=8`;
}
