// Node bridge for the App Store + Play Store scrapers.
//
// Per ADR-0000 Q10: tool wrappers reference npm libraries via
// subprocess.run. This file is the bridge — it receives a JSON
// spec via argv[2], dispatches to the right npm package, and
// writes the JSON result to stdout.
//
// ⚠️ google-play-scraper v10.x ESM-CJS quirk:
//     const g = require('google-play-scraper'); g.search(...)  // ❌ TypeError
//     const { search } = require('google-play-scraper').default;  // ✅
//
// app-store-scraper is plain CJS:
//     const { search } = require('app-store-scraper');  // ✅
//
// If you remove the `.default` from the google-play-scraper import,
// the call will crash with "g.search is not a function". This is
// the #1 thing that will trip up anyone editing this bridge —
// the Phase 0b smoke test caught it once already (see
// backend/output/phase_0b_smoke_test_2026-06-02.md).

'use strict';

async function main() {
  let payload;
  try {
    payload = JSON.parse(process.argv[2]);
  } catch (e) {
    console.error(`bridge: failed to parse argv[2] as JSON: ${e.message}`);
    process.exit(2);
  }

  const { store, query, limit } = payload;
  if (!store || !query) {
    console.error(
      `bridge: payload must have 'store' and 'query'. Got: ${JSON.stringify(payload)}`
    );
    process.exit(2);
  }

  let apps;
  try {
    if (store === 'apple') {
      // Plain CJS — no .default indirection.
      const { search } = require('app-store-scraper');
      apps = await search({ term: query, num: limit || 10 });
    } else if (store === 'play') {
      // ESM-style CJS — MUST use .default (Phase 0b smoke-test gotcha).
      const { search } = require('google-play-scraper').default;
      apps = await search({ term: query, num: limit || 10 });
    } else {
      console.error(`bridge: unknown store '${store}'. Use 'apple' or 'play'.`);
      process.exit(2);
    }
  } catch (e) {
    console.error(`bridge: ${store} search failed: ${e.message}`);
    process.exit(1);
  }

  // Normalise the two libraries' output to a common shape so the
  // Python wrapper doesn't need to know which library was called.
  // Each app: { title, app_id, score, ... }.
  const normalised = apps.map((a) => {
    if (store === 'apple') {
      return {
        title: a.title,
        app_id: String(a.id),
        score: a.score,
        ratings_count: a.ratings,
        price: a.price,
        currency: a.currency,
        developer: a.developer,
        url: a.url,
      };
    } else {
      // google-play-scraper
      return {
        title: a.title,
        app_id: a.appId,
        score: a.score,
        ratings_count: a.ratings,
        installs: a.installs,
        price: a.price,
        currency: a.currency,
        developer: a.developer,
        url: a.url,
      };
    }
  });

  // Print as the final stdout line. The Python wrapper takes the
  // last non-empty line and parses it as JSON.
  console.log(JSON.stringify(normalised));
}

main().catch((e) => {
  console.error(`bridge: unhandled error: ${e.message}`);
  process.exit(1);
});
