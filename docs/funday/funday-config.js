// ============================================================
// GCB Family Fun Day — shared config for board.html + score.html
// This is the ONLY file you edit. tools/build_funday_qr.py also
// reads the STATIONS block below, so stations never drift.
// ============================================================
window.FUNDAY = {

  // 1) Paste your Firebase web-app config here (see FUNDAY-SETUP.md).
  //    While this is null, both pages run in DEMO MODE with fake data
  //    so you can preview everything before Firebase exists.
  firebaseConfig: {
    apiKey: "AIzaSyBp_fUe_1JsfddtlBTcL9qbIymIzgz_j6c",
    authDomain: "gcb-team-hub.firebaseapp.com",
    databaseURL: "https://gcb-team-hub-default-rtdb.firebaseio.com",
    projectId: "gcb-team-hub",
    storageBucket: "gcb-team-hub.firebasestorage.app",
    messagingSenderId: "475220168104",
    appId: "1:475220168104:web:901032c8189b6c6990219d"
  },

  // 2) Where this event's data lives in the database. Change this for
  //    a future event and you get a fresh, empty leaderboard.
  eventPath: "events/funday-2026-08-02",

  eventName: "FAMILY FUN DAY",

  // 3) Quick-tap point buttons on the volunteer scoring page.
  //    Adjust once Halima finalizes scoring. Custom amounts always allowed.
  pointButtons: [5, 10, 25, 50],

  // 4) Stations. Keep slugs short and lowercase-with-dashes.
  //    Edit names/emoji freely, then re-run: python3 tools/build_funday_qr.py
  //    KEEP THIS BLOCK VALID JSON between the markers — the QR script parses it.
  //    ONE-SCORER MODEL (Hannah): stations do NOT get individual QRs anymore.
  //    score.html shows ALL of these as always-visible tap-chips — tap a
  //    station, log players, tap another to switch. build_funday_qr.py prints
  //    one "Score Keeper" QR (staff only) plus the leaderboard QR.
  //    score.html?st=<slug> still works as a deep link that preselects a chip.
  stations: /*STATIONS_START*/[
    { "slug": "cornhole",      "name": "Cornhole",        "emoji": "🌽" },
    { "slug": "ring-toss",     "name": "Ring Toss",       "emoji": "🎯" },
    { "slug": "balloon-darts", "name": "Balloon Darts",   "emoji": "🎈" },
    { "slug": "skeeball",      "name": "Skeeball",        "emoji": "🎳" },
    { "slug": "half-court",    "name": "Half-Court Shot", "emoji": "🏀" }
  ]/*STATIONS_END*/
};
