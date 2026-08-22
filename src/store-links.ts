/**
 * The two store URLs, in one place, because they are quoted from more than one
 * file: the badge component, the schema.org graph on the home page, and
 * anywhere else that needs to send someone to a store listing.
 */

/**
 * The App Store listing.
 *
 * TODO(Ron): replace APP_STORE_ID_PLACEHOLDER with the numeric App Store app id
 * once the app is approved. App Store Connect shows it as "Apple ID" on the
 * app's App Information page; the public URL is
 * https://apps.apple.com/app/id1234567890.
 *
 * This is the ONLY line that has to change, and it is deliberately left as a
 * URL that cannot resolve rather than a plausible-looking guess or a search
 * page. A broken link is caught the first time anyone clicks it; a link that
 * quietly goes somewhere wrong is not. Nothing here may be deployed until it
 * is filled in, because the App Store badge and the structured data on the home
 * page both read from this constant.
 */
export const APP_STORE_URL = 'https://apps.apple.com/app/idAPP_STORE_ID_PLACEHOLDER';

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
