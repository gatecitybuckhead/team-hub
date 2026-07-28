# GCB Team Hub — Agent Brief

Shareable dashboards for the GateCity Buckhead team, published via GitHub Pages
on the **GateCity Buckhead GitHub account** (separate from Andrew's personal
`andrewfaletti` account). This folder is its own git repo and is gitignored by
the parent `gatecity-buckhead-ai-ops` repo.

## What's live
- `docs/index.html` — public hub landing page (no data).
- `docs/staff/metrics.html` — Metrics dashboard (5 Behaviors charts + monthly/
  quarterly rollups). **Encrypted** with the shared team password.
- `docs/staff/debrief.html` — Sunday Debrief dashboard (scorecard, rating trend,
  what-we-talk-about word visualization, week/month/quarter history). Encrypted.
- `docs/production.html` — Production dashboard. **Encrypted with its OWN password
  (`W0rthy247`, in `gcb-production-password.txt` at AI Ops root — NOT the staff pw)**,
  and shows a **scannable QR** of its own URL so the team can open it at the booth
  without typing a link. Contains: this Sunday's service timeline, the Production-team
  roster with confirm status (C/U/D), and the pre-service checklist.
  - Roster source: `data/production.json` (Planning Center "Sunday Services", next plan,
    team_id 6342415). Checklist source: single source of truth is
    `Production Tech Agent/Sunday Checklist Dashboard/checklist.json` (build reads it live
    via `checklist_source`, so the LAN check-off dashboard and this page never drift).
  - Build: `python3 tools/build_production.py "W0rthy247"` → generates QR (vendored
    `tools/qr.py`), injects template, encrypts, writes `docs/production.html`. Gate uses
    sessionStorage key `gcbprod` (distinct from staff `gcbpw`).
  - `data/production.json.live_checklist_url` is null until the church-LAN booth IP is known.
- Planned area: `/volunteers` (QR-friendly).

## Pipeline (weekly, Tuesdays after the debrief meeting)
1. Sources: `DASHBOARD METRICS - 5 Behaviors` (Google Sheet, quarterly tabs,
   transposed layout), `Sunday DEBRIEF Form (Responses)` (Google Sheet), and the
   Meeting Archive folder in Drive (Zoom summaries).
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
4. `tools/build.py` → `build/*.html` (plaintext, NEVER commit).
5. `tools/encrypt.py <team password>` → `docs/staff/*.html` (AES-256-GCM,
   PBKDF2 200k; safe for a public repo).
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
- Debrief form quirks: 4-point text scale (old) + 1-10 numeric (new) merged to
  0-100 in parse_debrief.py; respondent name variants normalized there too.
