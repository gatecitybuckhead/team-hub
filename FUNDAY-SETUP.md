# Family Fun Day — Live Leaderboard Setup

Everything lives in `docs/funday/` and works in **demo mode right now** — open
`docs/funday/board.html` in a browser to preview the projector board with fake
scores before doing any Firebase setup.

## What was built

- `docs/funday/board.html` — projector leaderboard. Podium for top 3 (crown,
  confetti on lead change), "Chase Pack" for 4th+, live score ticker, rotating
  carnival-barker callouts, player/play counters.
- `docs/funday/score.html` — volunteer phone page. Opens pre-set to a station
  via `?st=<slug>` (from its QR). Pick/add player → tap points → done. Has undo,
  duplicate-name warning, and an online/offline indicator.
- `docs/funday/funday-config.js` — **the only file you edit**: Firebase config,
  station list, point buttons, event name.
- `tools/build_funday_qr.py` — printable QR sheets (one page per station +
  a leaderboard page). Output: `build/funday-qr-sheets.html` (gitignored).

This is also **Phase 2 of getting off the Mac mini**: the same Firebase database
can drive the production checklist next week — just a different `eventPath`.

## One-time Firebase setup (~10 min)

1. Go to https://console.firebase.google.com → **Add project**. Name it
   `gcb-team-hub`. Disable Google Analytics (not needed). Create.
2. In the left sidebar: **Build → Realtime Database → Create Database**.
   Pick `us-central1`. Start in **locked mode**.
3. In the database's **Rules** tab, paste this and **Publish**:

   ```json
   {
     "rules": {
       "events": {
         "$event": {
           ".read": true,
           "players": { "$p": { ".write": true,
             ".validate": "newData.hasChildren(['name']) && newData.child('name').isString() && newData.child('name').val().length < 40" } },
           "scores": { "$s": { ".write": true,
             ".validate": "newData.hasChildren(['p','st','pts']) && newData.child('pts').isNumber() && newData.child('pts').val() > -1000 && newData.child('pts').val() < 1000" } }
         }
       }
     }
   }
   ```

   (Anyone with the URL can log a score — that's the tradeoff for zero logins.
   Writes are shape-validated and undo-able, and the URL isn't listed anywhere.)

4. Project overview → **⚙ Project settings → General → Your apps → Web app
   (`</>` icon)**. Nickname `funday`. No hosting. Register, then copy the
   `firebaseConfig = { ... }` block it shows you.
5. Paste it into `docs/funday/funday-config.js` replacing `firebaseConfig: null`.
   (These keys are safe to publish — Firebase web keys are public by design;
   the rules above are the actual security.)

## Before Sunday

1. Update the `stations` list in `funday-config.js` if the games change
   (keep slugs short and lowercase-with-dashes).
2. SCORING MODEL (final, 2026-07-31): players keep their own score during the
   game and report ONE total to Hannah, who logs it on score.html. Every play
   adds to the leaderboard. Per-station `"quick"` arrays give one-tap total
   buttons (Balloon Darts 10–50, Cornhole 1–12); Kick Dart & Skeeball are
   keypad entry. `"max"` triggers a "really log X?" check above the game's
   max possible. There is no `pointButtons` anymore.
3. `python3 tools/build_funday_qr.py` → open `build/funday-qr-sheets.html` →
   print. Tape each sheet at its station.
4. Publish (on the Mac, as always): commit, then **Publish to GitHub.command**.
   No encryption step needed — these pages are public (first names + points only;
   tell volunteers to use first name + last initial).
5. **Dry run**: open `board.html` on one screen, scan a station QR with your
   phone, log a few scores, watch them appear. Undo one. Do this Thursday, not
   Sunday morning.

## Day-of

- Projector: open `https://gatecitybuckhead.github.io/team-hub/funday/board.html`
  (the QR sheet's last page has this as a QR too). Fullscreen the browser.
- Reset before doors open if you tested on the live path: Firebase console →
  Realtime Database → hover `events/funday-2026-08-02` → ⋮ → Delete.
- Or run a fresh event without deleting anything: change `eventPath` in the
  config, re-publish.

## Phase 2 — production checklist (next week)

Same database, new path (e.g. `events/production-checklist`). The check-off
state that currently lives on the Mac mini LAN dashboard moves to Firebase, so
`docs/production.html` can read/write it from anywhere — booth, phone, home —
with no local hosting. The funday pages are the working reference implementation.
