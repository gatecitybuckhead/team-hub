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
2. `tools/parse_metrics.py` + `tools/parse_debrief.py` read the two xlsx files
   from a downloads location → `data/metrics.json`, `data/debrief.json`.
   NOTE: the Drive MCP connector TRUNCATES both sheets (~146K chars); for full
   history use xlsx downloads. For weekly increments the connector's
   `read_file_content` is fine for the debrief sheet (newest rows first).
3. `data/summaries.json` — month/quarter narratives (LLM-written, appended each
   period). `data/meetings.json` — meeting archive digest.
4. `tools/build.py` → `build/*.html` (plaintext, NEVER commit).
5. `tools/encrypt.py <team password>` → `docs/staff/*.html` (AES-256-GCM,
   PBKDF2 200k; safe for a public repo).
6. Commit + push → GitHub Pages redeploys.

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
