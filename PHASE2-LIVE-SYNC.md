# Phase 2 — Production Dashboard on Firebase (kill the Mac mini hosting)

Handoff brief for a new session. Goal: the Production dashboard's pre-service
checklist becomes live-synced through Firebase — check an item at the booth,
it's checked on every phone — with **no LAN hosting on the Mac mini**. Same
architecture as Family Fun Day, which is the working reference implementation.

## What already exists (do not rebuild)

- **Firebase project `gcb-team-hub`** — Realtime Database live at
  `https://gcb-team-hub-default-rtdb.firebaseio.com`, created 2026-07-28 under
  the gatecitybuckhead.com org. Web-app config is pasted in
  `docs/funday/funday-config.js` (these keys are public-safe; rules are the
  security).
- **Reference implementation**: `docs/funday/board.html` + `score.html` —
  compat SDK 10.12.2 from gstatic CDN, `?ev=` path override for dry runs,
  demo mode when config is null, cache-busted config include (`?v=2`).
- **Production page today**: `docs/production.html`, AES-encrypted by
  `tools/build_production.py "W0rthy247"` (password file at AI Ops root,
  sessionStorage key `gcbprod`). Data from `data/production.json` (Planning
  Center roster, timeline) + checklist from its single source of truth:
  `Production Tech Agent/Sunday Checklist Dashboard/checklist.json`.
  `data/production.json.live_checklist_url` is null — the LAN URL that never
  got wired up. That whole LAN/Mac-mini path is what Phase 2 retires.

## The gotcha that will bite first: database rules

The current RTDB rules ONLY allow `events/$event/players` and
`events/$event/scores` (shape-validated). **Production checklist writes will
be silently denied until a `production` branch is added.** New rules:

```json
{
  "rules": {
    "events": { "...": "keep the existing funday rules exactly as-is" },
    "production": {
      "$sunday": {
        ".read": true,
        "checks": {
          "$item": {
            ".write": true,
            ".validate": "newData.hasChildren(['done','ts']) && newData.child('done').isBoolean() && newData.child('ts').isNumber()"
          }
        }
      }
    }
  }
}
```

(Merge, don't replace — funday runs Aug 2 and its rules must keep working.
Andrew publishes rules in Firebase console → Realtime Database → Rules.)

## Design

- **Data model**: `production/<sunday-date>/checks/<item-id> = {done, ts, by?}`.
  Keyed by service date so every Sunday starts a fresh, unchecked list
  automatically — no reset job. Item ids come from `checklist.json` (they're
  stable across text edits by design). Optional `by` = tapped initials.
- **Page changes** (in `templates/production.template.html`): after the
  password gate decrypts, load the Firebase compat SDK + shared config and
  attach `on('value')` to today's/next Sunday's path. Tap-to-check writes
  `{done:true, ts:Date.now()}`; every open copy updates in ~1s. Keep the
  existing sessionStorage-cached local check state as offline fallback so the
  page still works if the school wifi blocks Firebase (test this at AIS —
  websockets occasionally blocked; the SDK falls back to long-polling).
- **Config sharing**: don't duplicate the Firebase config. Either have
  `build_production.py` read it out of `docs/funday/funday-config.js` at build
  time (regex the object like `build_funday_qr.py` does for stations), or
  promote the config to `docs/shared-config.js` and point funday + production
  at it (bump the `?v=` cache-buster if renaming).
- **Sunday-date logic**: compute "next Sunday" client-side (America/New_York)
  so the page always shows the upcoming service without a rebuild.
- **Retire**: the Mac mini LAN dashboard and `live_checklist_url`. NOTE:
  `checklist.json` in Production Tech Agent stays the source of truth for
  *item definitions* — only the *check-off state* moves to Firebase.
- **GCB Teams / future checklists**: the `production/$sunday/checks` pattern
  generalizes — a future `teams/<team>/<sunday>/checks` branch gives any team
  a live checklist. Don't build it yet; just don't paint the rules into a
  corner (the branch-per-area layout above is fine).

## Verification checklist for the build session

1. Rebuild: `python3 tools/build_production.py "W0rthy247"` (password also in
   `gcb-production-password.txt` at AI Ops root).
2. Test the deployed page in two browser windows: check an item in one,
   see it flip in the other. Test with `?ev=`-style override or a scratch
   date path so real Sunday state stays clean.
3. Confirm funday still works after the rules merge (read
   `.../events/funday-2026-08-02.json` — should still return 200).
4. Publishing runs on the Mac: Encrypt.command is NOT the tool for this page
   (it has its own build script) — just `build_production.py`, then commit +
   **Publish to GitHub.command**. Pushes from the cowork sandbox silently fail;
   never claim it's live without Andrew pushing.
5. QR at the booth already points at the public URL — unchanged, keeps working.

## Lessons from the funday build (avoid repeats)

- **Test the QR/URL-parameter load path, not just the default page** — a
  use-before-init crash only triggered when `?st=` was present and cost a
  debugging round-trip. Smoke-test with the real query string.
- GitHub Pages caches ~10 min; bump `?v=` on shared JS includes when editing.
- The vendored `tools/qr.py` maxes out ~100 bytes — keep URLs short.
