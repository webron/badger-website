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
