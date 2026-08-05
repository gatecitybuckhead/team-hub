# GCB Team Hub — Agent Brief

Shareable dashboards for the GateCity Buckhead team, published via GitHub Pages
on the **GateCity Buckhead GitHub account** (separate from Andrew's personal
`andrewfaletti` account). This folder is its own git repo and is gitignored by
the parent `gatecity-buckhead-ai-ops` repo.

## What's live
- `docs/index.html` — public hub landing page (no data).
- `docs/staff/metrics.html` — Metrics dashboard (5 Behaviors charts + monthly/
  quarterly rollups). **Encrypted** with the shared team password.
  - **Sanctuary count is the headline number.** `attendance_in_sanctuary` gets a
    double-width hero KPI at the top (with ▲/▼ vs the 4-week average) and is the
    bold blue, always-pointed, top-drawn series in the Attendance chart. Total and
    Kids stay on the chart for context but their value labels are suppressed
    (`noLabel:true`) so the sanctuary numbers don't get crowded out.
  - **Value labels**: hand-rolled `valueLabels` Chart.js plugin in the template —
    NOT chartjs-plugin-datalabels, deliberately, since only `chart.umd` is loaded
    from CDN and the encrypted page must not gain a second dependency. It prints
    each week's number on a dark plate, auto-thins to every Nth point when the
    range is too dense (always keeping the newest), flips a label below the point
    if it would clip the top, and skips any label that would collide.
    `opts.fmt` customizes formatting (`fmt$k` for dollars, `v=>v+'%'` for rates).
  - **"% of members giving" now comes from Planning Center**, with the sheet kept
    as history. Two series on one chart, deliberately distinct:
    - `data/giving_participation.json` (blue, live) — PCO People lists
      **"Members Giving (Last 90 Days)"** (id 5145818) ÷ **"Members (All)"**
      (id 4019918). 54/91 = 59.3% on 2026-07-28. `Members (All)` is the right
      denominator because it matches the sheet's `# Total Members` (91) exactly,
      keeping the new number comparable to the old series.
    - `of_members_giving` from the sheet (green) — recorded **periodically, not
      weekly**: holds flat for stretches then jumps, so it's drawn
      `stepped:true, span:false` to leave real gaps visible rather than
      interpolating readings nobody took. 10 Sundays behind as of 2026-07-28
      (last entry 2026-05-17 at 56%).
    `giveStaleness()` writes the provenance note under the chart from the data —
    both the live figure with its list names and the sheet's staleness count.
    The "Members giving" KPI prefers PCO, falls back to the most recent non-null
    sheet value (labelled with its date), then to "—".
  - **The PCO figure is a ROLLING 90-DAY WINDOW and carries no history** — the
    lists answer "as of right now" and cannot be asked what March looked like.
    So `tools/add_giving_reading.py` is **append-only**: one reading per weekly
    run, building a real series going forward. Never backfill it; a reading taken
    today is not evidence about an earlier Sunday. Re-running for the same Sunday
    replaces that reading instead of duplicating.
    PCO is only reachable through the MCP connector (no PCO credentials in this
    repo), so the agent pulls the two counts and pipes them in — same split as
    `add_metrics_week.py`:
    `python3 tools/add_giving_reading.py --giving 54 --members 91 --sunday 2026-07-26 --refreshed <ts>`
  - **A scheduled task captures this every Sunday 9pm** —
    `gcb-giving-participation-reading` (`~/Claude/Scheduled/`). It exists because a
    missed week is unrecoverable, so capture is decoupled from the Tuesday pipeline
    and from publishing. It only appends the reading + runs `build.py`; it never
    encrypts or pushes. Sanity checks it reports on: list `refreshed_at` older than
    ~3 days, a swing >10 points (usually a changed list definition, not real), and
    `giving > members` (swapped/re-pointed list IDs).
  - The chart plots PCO readings against the Sundays present in `metrics.json`. If
    the metrics step is skipped for a week, that reading has no column to sit in —
    `giveStaleness()` prints a red "N readings can't be charted" warning listing the
    orphaned dates, so a lost point can't fail silently.
  - Percentages come out of the sheet as fractions (0.56), but a few old rows were
    typed as whole numbers — `pct()`/`pctNum()` treat anything >1.5 as already-%.
- `docs/staff/debrief.html` — Sunday Debrief dashboard. Encrypted. **Its layout
  deliberately mirrors the live Tuesday meeting agenda** (see "Agenda mirroring"
  below): Prior to Mtg → ① Sunday's DEBRIEF (30 min) → ② Review DASHBOARD (15 min)
  → Debrief-form accountability → History. A sticky agenda bar jumps between them.
  Picking a Sunday in 1.1 re-renders every section for that week, so the whole
  page is one week at a time; clicking a point on the trend chart also jumps there.
- `docs/production.html` — Production dashboard. **Encrypted with its OWN password
  (`W0rthy247`, in `gcb-production-password.txt` at AI Ops root — NOT the staff pw)**,
  and shows a **scannable QR** of its own URL so the team can open it at the booth
  without typing a link. Contains: this Sunday's service timeline, the Production-team
  roster with confirm status (C/U/D), and the pre-service checklist.
  - Roster source: `data/production.json` (Planning Center "Sunday Services", next plan,
    team_id 6342415). Checklist source: single source of truth is
    `Production Tech Agent/Sunday Checklist Dashboard/checklist.json` (build reads it live
    via `checklist_source` — that file still defines the ITEMS; only check-off STATE
    lives in Firebase).
  - Build: `python3 tools/build_production.py "W0rthy247"` → generates QR (vendored
    `tools/qr.py`), injects template + Firebase config, encrypts, writes
    `docs/production.html`. Gate uses sessionStorage key `gcbprod` (distinct from staff
    `gcbpw`).
  - **Checklist is live-synced via Firebase RTDB** (Phase 2, 2026-07-28): path
    `production/<sunday>/checks/<itemId>` = `{done, ts, by}`, keyed by next Sunday
    (America/New_York, computed client-side) so each week starts fresh with no reset job.
    Firebase config is regexed out of `docs/funday/funday-config.js` at build time —
    never duplicated. SDK loads after first render with a 12s watchdog; if gstatic is
    blocked (AIS wifi) the page falls back to per-device localStorage exactly like the
    old behavior. `?ev=<slug>` overrides the date path for dry runs (mirrors funday).
    DB rules for the WHOLE database live in `firebase-rules.json` at repo root (funday +
    production branches merged) — publish via Firebase console → Realtime Database →
    Rules. The old Mac-mini LAN dashboard + `live_checklist_url` are retired.
  - **Crew sign-in (2026-08-05)** — carried over from the retired beta dashboard's
    "Set name," but shared instead of per-device. `production/<sunday>/crew/<slug>` =
    `{name, ts}` where `ts` is the ARRIVAL time; the slug is derived from the name so a
    second device doesn't create a duplicate person, and an existing entry is never
    overwritten (signing in again must not move the time you actually showed up).
    The sign-in sheet lists this Sunday's PCO roster as tap targets plus a free-text box
    for anyone not scheduled — fill-ins like Tristan won't be on the roster until PCO has
    them, so the typed path is load-bearing, not a fallback. **Checking is gated on being
    signed in**: items render `.locked` and a tap opens the sheet instead of toggling, so
    every check carries a name. The name rides along as `by` on the check and renders as
    a "Name · 7:12 AM" pill; a "Who's Here" card lists arrivals in order.
    Two rules-level notes: extra children are legal under the old `checks` validate rule,
    so `by` syncs even on unpublished rules — but `crew` writes are DENIED until the new
    `firebase-rules.json` is published, and the symptom is subtle (each phone shows only
    itself in Who's Here while checks sync fine). Times are formatted in
    America/New_York via `Intl`, not the device clock's zone.
  - **A scheduled task refreshes the roster every Friday 8am** —
    `gcb-production-page-friday-refresh` (`~/Claude/Scheduled/`), 30 min after the
    ProPresenter sync check (the two form the Friday Sunday-prep block). It pulls the
    coming Sunday's plan from PCO (team_id 6342415 only), rewrites `data/production.json`
    against the FIXED position list, rebuilds, and tells Andrew to run Publish to
    GitHub.command. It never pushes, and never overwrites production.json when PCO is
    unreachable or the plan is missing.
- `docs/funday/` — Family Fun Day live leaderboard (Aug 2 2026). **Public, not
  encrypted** (first names + points only). `board.html` = projector view.
  **ONE-SCORER MODEL (2026-07-30):** Hannah logs every game from one page —
  `score.html` shows ALL stations (incl. Half-Court Shot) as always-visible
  tap-chips; no per-station QRs. `tools/build_funday_qr.py` prints just two QR
  sheets (staff Score Keeper + leaderboard). `?st=<slug>` still preselects a chip.
  `funday-config.js` = single config file (Firebase web config, stations —
  the STATIONS block is strict JSON parsed by the QR script).
  **SELF-REPORTED TOTALS (2026-07-31, final):** players track their own score
  and report ONE number per game; Hannah logs that total (every play ADDS —
  no best-of/replace). Per-station `"quick"` arrays render one-tap total
  buttons (Moving Target 10–50 max 50; Cornhole 1–12 max 12); Kick Dart &
  Skeeball (machine shows total) are keypad-only. `"max"` triggers a confirm
  above the game's max. `pointButtons` is GONE from config + score.html.
  Stations final: Cornhole, Kick Dart (replaced Ring Toss 2026-07-31),
  Moving Target (renamed from Balloon Darts 2026-08-01 — Halima, setup
  logistics; name/slug/emoji only, scoring unchanged), Skeeball,
  Half-Court Shot. Config cache-buster now `?v=3` in both pages.
  **Roster preload:** full names live in gitignored `data/funday_roster_names.json`
  (PCO Members (All) + Member (Kids), pulled 2026-07-30); only "First L." display
  names (collision-safe) reach Firebase. `tools/build_funday_admin.py` →
  `build/funday-admin.html` (LOCAL ONLY): one-tap preload (skips names already
  present, safe to re-run), wipe-scores, wipe-players. `board.html` hides
  zero-point players so preloads don't flood the board. Registration-form
  names pending (PCO Forms not reachable via connector — merge into the
  roster JSON + re-run the admin build).
  Backend: **Firebase Realtime DB** (`events/<eventPath>`: `players/`, append-only
  `scores/`; board sums client-side; rules in FUNDAY-SETUP.md). With
  `firebaseConfig: null` both pages run a demo mode. This Firebase project is
  the intended phase-2 backend for moving the production checklist off the
  Mac mini (same DB, different eventPath).
- Planned area: `/volunteers` (QR-friendly).

## Pipeline (weekly, Tuesdays after the debrief meeting)
1. Sources: `DASHBOARD METRICS - 5 Behaviors` (Google Sheet, quarterly tabs,
   transposed layout), `Sunday DEBRIEF Form (Responses)` (Google Sheet), and the
   Meeting Archive folder in Drive (Zoom summaries).
   **Sunday 2026-08-02 (Family Fun Day) used a DIFFERENT form** — responses are
   in `Family Fun Day 2026 Feedback Form (Responses)`, Drive file id
   `1H7WbKV5Bn6JBcPkVV3KQSTzF7WLncnBj0PnTz0ttTmA` (readable via the connector,
   small). Event-specific questions (tone/hospitality/games/flow/outreach);
   the regular parse_debrief.py columns don't apply. A `Name` question was
   added 8/3 AFTER the first response, so it's the LAST column — but by the
   2026-08-04 run all 5 rows HAD names (the 8/3 9:14am row is Sarah), so the
   "nameless first row" note is now stale. Treat 8/2 as a `special` week: fold
   these in as the Fun Day debrief instead of forcing them into the regular
   schema. **Done 2026-08-04 by `tools/_add_funday_week.py`** — a one-off,
   idempotent appender (re-running replaces the 8/2 rows, never duplicates).
   It maps Yes/Somewhat/No → 100/50/0 (matching parse_debrief.py's 0-100
   normalization), doubles the form's 1-5 overall onto the 0-10 scale, and
   names 12 event-specific elements (Event Tone, Guest Flow, Volunteer
   Staffing, On-Time Execution, …). Safe because the template renders
   `elements` as a per-week sorted bar list, NOT as cross-week series — so
   one-off element names don't create phantom trend lines. **Careful: running
   `parse_debrief.py` (full rebuild) WIPES the 8/2 week**, since that Sunday
   isn't in the regular sheet; re-run `_add_funday_week.py` after any full
   rebuild. The Fun Day pros/grows live in `debrief_narratives.json`, and
   `meeting_notes.json` has a `2026-08-04` entry carrying
   `special: "Family Fun Day"` + `respondents: 5` with `has_report:false` and
   `overall_tone:null` (no Tuesday-doc write-up existed yet, so the page
   auto-generates the tone line and labels it as auto).
2. FULL REBUILD: `tools/parse_metrics.py <in.xlsx> [out.json]` +
   `tools/parse_debrief.py` read xlsx exports → `data/metrics.json`,
   `data/debrief.json`. Needed because the Drive MCP connector TRUNCATES both
   sheets (~146K chars) — and it truncates *before* the newest quarterly metrics
   tab, which is why the metrics step kept getting skipped.
   WEEKLY INCREMENT: `tools/add_metrics_week.py <sunday-date> --series .. --special ..`
   reads pipe-delimited `label | dataset cell | sunday cell` lines on stdin (sheet
   row order) and appends one week. Shared cleaning/slug logic lives in
   `tools/metrics_common.py` so the two paths can't drift. The agent only produces
   ~55 short lines; the 96KB JSON never enters context.
   Getting the current quarter out of the sheet: the connector can't reach it —
   use the gviz endpoint in a Chrome session
   (`docs.google.com/spreadsheets/d/<id>/gviz/tq?tqx=out:html&sheet=Q3%202026`),
   which returns the tab complete. The debrief sheet is fine via the connector
   (newest rows first).
   **Do this work in a subagent.** The 2026-07-28 weekly run died with
   "Response stalled mid-stream" from pulling both sheets plus the data files into
   one context; metrics and meetings never ran. Sheet reads belong in a subagent
   that returns only a compact digest.
3. `data/summaries.json` — month/quarter narratives (LLM-written, appended each
   period). `data/meetings.json` — meeting archive digest.
   `data/meeting_notes.json` — per-meeting digest parsed from the **Tuesday
   debrief Google Doc** (`1kCibagLgUsn1RbJFhZ8v3EHiOTZQX-oNRnfMa1-XFFM`): keyed by
   `meeting_date` + the `sunday` it debriefs, carrying `overall_tone`, `big_wins`,
   `growth_areas`, `pros_topics`, `grows_topics`, `respondents`, `special`,
   `attendance`/`visitors`/`giving`, `era`, `has_report`. Built 2026-07-28 covering
   all 76 meetings Jan 2025 → Jul 2026. **Append new weeks by hand** — there's no
   parser to re-run, and the doc's heading formats are too inconsistent to trust one.
   The doc is ~288K chars: reading it blows the connector's token cap, so **read it
   in a subagent** and have it return only the new week's fields.
   `data/debrief_narratives.json` still wins over meeting_notes for pros/grows text
   when an entry exists for that Sunday.
3b. **Pull the giving-participation reading from Planning Center.** Call
   `pco_list_lists`, read `people_count` off "Members Giving (Last 90 Days)"
   (5145818) and "Members (All)" (4019918) — the list metadata already carries the
   counts, so do NOT call `pco_get_list_people` (hundreds of names, no benefit).
   Then `python3 tools/add_giving_reading.py --giving <n> --members <n> --sunday
   <date> --refreshed <refreshed_at>`. Append-only; see the metrics notes above.
4. `tools/build.py` → `build/*.html` (plaintext, NEVER commit).
5. `tools/encrypt.py` (no args) → `docs/staff/*.html` (AES-256-GCM, PBKDF2
   200k; safe for a public repo). **PER-PAGE passwords since 2026-08-04** —
   debrief and metrics each have their own, read from
   `gcb-staff-passwords.json` at the AI Ops root. The script encrypts an
   explicit ALLOWLIST (debrief + metrics only), never a glob of `build/`,
   so stray build files can't leak onto the staff site.
6. Commit + push → GitHub Pages redeploys. **Steps 5-6 must run on the Mac**
   (double-click `Encrypt.command`, then `Publish to GitHub.command`). A `git push`
   from the cowork sandbox looks like it worked but leaves the commit unpushed —
   the mount can't delete `.git/index.lock`. Verified again 2026-07-28: commit
   `950db3b` sat local-only while `origin/main` stayed on 7/23. Always check
   `git status -sb` / `git log origin/main -1` before claiming the site is live.

## Rules
- `data/` and `build/` are gitignored: raw giving numbers, kids-incident notes
  and comments must never land in the public repo — only encrypted output.
- The team password is shared out-of-band; not stored in git. See root
  SECRETS-INVENTORY.md.
- Metrics sheet quirks: labels drift across years (aliases in parse_metrics.py);
  future-dated columns contain stale template values (parser drops date > today);
  Q1 2025 tab uses bare `1/5` headers, later tabs use `Sunday 7/5` + `Data Set` pairs.
  The catalog keeps the FIRST label seen for a key and the earliest tab is Q1 2025,
  from the garage era — so aliased keys inherited stale display names
  (`attendance_in_sanctuary` read "# Attendance (in garage)"). `LABEL_OVERRIDES` in
  `metrics_common.py` wins over first-seen; add to it when the sheet gets renamed.
  Special Sundays spike the attendance series hard and legitimately (PentecostATL
  2026-05-24 = 180 in a room that normally holds ~50) — not an outlier to filter.
- Debrief form quirks: 4-point text scale (old) + 1-10 numeric (new) merged to
  0-100 in parse_debrief.py; respondent name variants normalized there too.
  **Column 19 is NOT the kids-incident field on the current form** — it's the
  catch-all "anything else?" box. Verified 2026-07-28: only 8 of 90 entries mention
  kids, the rest are production/ops notes. It's tagged `other`; the dashboard routes
  it into the Pastoral kids block only when the text matches a kids keyword regex.
  `canon()` keys off the FIRST token, so a surname-first answer ("Faletti") slips
  through — `tools/participation.py` has an ALIASES fallback for the survivors.

## Agenda mirroring (why the debrief page looks the way it does)
Structure comes from a read of all 76 meetings in the Tuesday debrief Doc. The
meeting has run in three eras; the page mirrors **Era 3** (Feb 10 2026 →), the
current one:

    (Prior to Mtg)  All Team COMPLETE DEBRIEF FORM
    (30 min) Sunday's DEBRIEF
       Review FORM Results  ← respondent count belongs on this line
       Discuss PROS:  /  Discuss GROWS:      (PROS always first, grouped by topic)
       Pastoral Same Page on People (Decisions/Guests/New Members)
       Capture Action Items  (What adjustments are we making?)
    (15 min) Review DASHBOARD
       Discuss - What are the metrics telling us?
       Capture Action/Parking Lot Items

Conventions the page reproduces, all taken from the notes:
- Summary format standardized around June 2026: `✅ PROS (What's Working Well)` /
  `🧠 GROWS (Where We Can Improve)` / `📊 Overall Summary` → **Big Wins**,
  **Primary Growth Areas**, then a bolded **Overall Tone:** verdict sentence.
  `renderPG()` follows that order and falls back gracefully: written narrative →
  parsed meeting notes → auto-split from the raw ratings. It never renders blank
  and the tone line is always present (auto-generated + labelled as such if the
  notes have no written verdict — only 26 of 76 weeks do).
- Respondent count is displayed on the "Review FORM Results" line, matching
  "Review FORM Results - **4 Respondents**".
- Parking lot is a **separate bucket** from action items and belongs to the
  dashboard half. Items are routed there by regex on hand-off language
  ("add to tactical", "Thursday tactical", "10:10", "parking lot", "revisit"…).
- Empty sections are normal, not a bug — many weeks were templated and left blank.
- Special Sundays (Baptism, Family Fun Day, PentecostATL, Move Weekend, …) break
  the template; `special` surfaces as a chip in the week picker and history.
- Attendance is NEVER recorded in the doc, so the page never claims to show it.

## Debrief-form accountability
`tools/participation.py` builds the who-filled-it-out tracker; `build.py` imports it.
- ROSTER is the **fixed current core team** given by Andrew 2026-07-28: Hazen,
  Hannah, Son, Halima, Sarah, Andrew, Crystal, Angel, Karissa, Gretchen, Kennah.
  Update ROSTER when the team changes — nothing else needs touching.
- Backfilled free from `debrief.json` (`responses[]` already carry `name` + `sunday`):
  75 Sundays, 2025-01-12 → 2026-07-26, no re-parsing needed.
- **Weeks before a person's first recorded response are "n/a", not "missed."** A
  fixed roster over a year of history would otherwise mark people absent for weeks
  they weren't on the team. Rates are computed over graded weeks only.
- Someone with zero responses ever is flagged explicitly (`no_record`) rather than
  silently scored 0% — currently Gretchen. Alice Yoon (17) and Ben Melancon (11)
  are off-roster and listed separately so they don't distort the grid.
- `python3 tools/participation.py` prints a text report; handy for a sanity check.
- Cross-check when changing it: recompute from `responses[]` (the tracker builds
  from `weekly[]`) and assert the two agree — that caught nothing on 2026-07-28,
  which is the point.
