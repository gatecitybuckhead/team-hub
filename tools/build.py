#!/usr/bin/env python3
"""Build GCB Team Hub staff dashboards.
Reads data/*.json, computes word frequencies, injects into templates/,
writes plain HTML to build/ (NOT committed). Run encrypt.py afterwards
to produce the published site/staff/*.html.
Usage: python3 build.py
"""
import json, re, collections, datetime, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA, TPL, OUT = ROOT/'data', ROOT/'templates', ROOT/'build'
OUT.mkdir(exist_ok=True)
sys.path.insert(0, str(ROOT/'tools'))
import participation

metrics   = json.load(open(DATA/'metrics.json'))
debrief   = json.load(open(DATA/'debrief.json'))
meetings  = json.load(open(DATA/'meetings.json'))
summaries = json.load(open(DATA/'summaries.json'))
# Per-meeting digest parsed from the Tuesday debrief Google Doc: overall_tone,
# big_wins, growth_areas, pros/grows topic headings, respondent counts.
try:
    notes_raw = json.load(open(DATA/'meeting_notes.json'))['meetings']
except FileNotFoundError:
    notes_raw = []
# "% of members giving" pulled from the Planning Center lists (rolling 90 days).
# Append-only; see tools/add_giving_reading.py for why it can't be backfilled.
try:
    giving_part = json.load(open(DATA/'giving_participation.json'))
except FileNotFoundError:
    giving_part = {'readings': []}
# Per-Sunday written debrief summaries (optional; survives parse_debrief re-runs).
# The dashboard shows the entry for the LATEST week only, else auto-generates.
try:
    narratives = json.load(open(DATA/'debrief_narratives.json')).get('weeks', {})
except FileNotFoundError:
    narratives = {}

# ---------- word frequencies per month (comments + meeting text) ----------
STOP = set('''a an the and or but if then than so of to in on at for with from by as is are was were be been being
this that these those it its it's im i'm we our us you your they their he she his her him them there here what which
who whom how when where why not no yes do does did done doing have has had having will would can could should shall
may might must let lets also just really very much more most some any all both each few other another one two three
first next last new old good great well better best out up down over under again during before after above below
about into through between while because get got getting go going went come came make made making take took say said
think thought feel felt felt like time week today sunday service church team meeting people person thing things way
lot bit kind maybe still even back off now day am pm ok okay n/a na none nothing didnt didn't dont don't cant can't
wasnt wasn't isnt isn't need needs needed want wanted love loved keep continue always never definitely little big
etc'''.split())
NAMES = set('andrew karissa hannah halima sarah angel hazen alice son ben kennah crystal gretchen faletti stevens shivers colon byrd melancon jones yoon edge pearl nicole'.split())

def tokens(text):
    for w in re.findall(r"[a-zA-Z']{3,}", text.lower()):
        w = w.strip("'")
        if len(w) >= 3 and w not in STOP and w not in NAMES:
            yield w

word_months = collections.defaultdict(collections.Counter)
for w in debrief['weekly']:
    mo = w['sunday'][:7]
    for c in w['comments']:
        word_months[mo].update(tokens(c['text']))
for m in meetings:
    mo = m['date'][:7]
    blob = ' '.join([m.get('summary') or ''] + (m.get('decisions') or []) + (m.get('topics') or []))
    word_months[mo].update(tokens(blob))
word_months = {mo: dict(c.most_common(70)) for mo, c in sorted(word_months.items())}

# ---------- meetings slimmed for the debrief page ----------
meet_slim = [{'date': m['date'], 'title': m.get('title',''), 'summary': m.get('summary',''),
              'decisions': m.get('decisions') or [], 'actions': m.get('action_items') or []}
             for m in sorted(meetings, key=lambda x: x['date'])]

# ---------- meeting-notes digest keyed by the Sunday being debriefed ----------
# The doc is keyed by meeting date (Mon/Tue); the dashboard is keyed by Sunday.
notes_by_sunday = {}
for n in sorted(notes_raw, key=lambda x: x['meeting_date']):
    notes_by_sunday[n['sunday']] = {
        'meeting_date': n['meeting_date'], 'era': n.get('era'),
        'respondents': n.get('respondents'), 'special': n.get('special'),
        'overall_tone': n.get('overall_tone'),
        'big_wins': n.get('big_wins') or [], 'growth_areas': n.get('growth_areas') or [],
        'pros_topics': n.get('pros_topics') or [], 'grows_topics': n.get('grows_topics') or [],
        'attendance': n.get('attendance'), 'visitors': n.get('visitors'),
        'giving': n.get('giving'), 'has_report': n.get('has_report', False),
    }

# ---------- debrief-form participation / accountability ----------
part = participation.build(debrief)

built = datetime.date.today().isoformat()
# Full timestamp (with UTC offset) for the refresh pill's "Numbers as of ..."
# stamp. Separate from `built` on purpose: `built` is printed as visible text on
# six pages and stays a plain date.
built_at = datetime.datetime.now().astimezone().isoformat(timespec='seconds')
# Shared refresh pill (fixed bottom-right "Numbers as of X · Refresh"). One
# source file, injected into every page — see templates/refresh-pill.html.
REFRESH_HTML = (TPL/'refresh-pill.html').read_text()

def check_js(out_name):
    """Fail the build on a JavaScript syntax error in the generated page.

    One stray apostrophe (`'didn't decline'`) killed the whole inline script on
    members.html and shipped to the live site for a day — every chart and table
    silently blank, with nothing in the build output to notice. Encryption hides
    the payload afterwards, so this is the last point where it can be caught.
    Skips quietly if node isn't installed; never let the guard itself block a build.
    """
    import os, shutil, subprocess, tempfile
    if not shutil.which('node'):
        return
    html = (OUT/out_name).read_text(errors='ignore')
    scripts = re.findall(r'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>', html, re.S)
    if not scripts:
        return
    with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False) as f:
        f.write('\n;\n'.join(scripts))
        tmp = f.name
    r = subprocess.run(['node', '--check', tmp], capture_output=True, text=True)
    os.unlink(tmp)
    if r.returncode:
        raise SystemExit(f'JS SYNTAX ERROR in {out_name} — refusing to build.\n'
                         f'{r.stderr.strip()[:600]}\n'
                         f'(most often an unescaped apostrophe inside a single-quoted string)')


def inject(tpl_name, out_name, payload):
    html = open(TPL/tpl_name).read()
    html = html.replace('/*__DATA__*/null', json.dumps(payload, separators=(',',':')))
    html = html.replace('<!--__REFRESH__-->', REFRESH_HTML)
    html = html.replace('__BUILT_AT__', built_at)
    html = html.replace('__BUILT__', built)
    open(OUT/out_name, 'w').write(html)
    check_js(out_name)
    print('built', out_name, f'{(OUT/out_name).stat().st_size//1024}KB')

inject('metrics.template.html', 'metrics.html',
       {'metrics': metrics, 'summaries': summaries, 'giving_participation': giving_part})
inject('debrief.template.html', 'debrief.html',
       {'weekly': debrief['weekly'], 'meetings': meet_slim,
        'summaries': summaries, 'words': word_months,
        'narratives': narratives, 'notes': notes_by_sunday,
        'participation': part})

# ---------- finance pages (data from Finance Agent's build_teamhub_finance.py) ----------
# Giving dollars/participation are injected HERE from metrics.json so the
# numbers can't drift from the Metrics page. Weekly $ = digital + cash +
# special (the combined sheet column died in Mar 2025 — don't use it).
def giving_series():
    weeks = []
    for w in metrics['weeks']:
        v = w['values']
        # A giving week = the sheet's Data Set cell (Mon–Sat) PLUS its Sunday
        # cell. Weeks ingested before 2026-08-19 kept only one of the two, so
        # they carry no 'giving_cols' and stay partial (window='partial') until
        # the history is restated from Planning Center.
        cols = w.get('giving_cols') or {}
        def amount(key):
            c = cols.get(key)
            if c and (c.get('ds') is not None or c.get('sun') is not None):
                return round((c.get('ds') or 0) + (c.get('sun') or 0), 2)
            return v.get(key)
        digital, cash, special = (amount('week_s_tithes_offerings_digital'),
                                  amount('week_s_tithes_offerings_cash'),
                                  amount('special_gifts'))
        total = None
        if any(x is not None for x in (digital, cash, special)):
            total = round(sum(x or 0 for x in (digital, cash, special)), 2)
        weeks.append({'sunday': w['date'], 'digital': digital, 'cash': cash,
                      'special': special, 'total': total,
                      'window': 'full' if cols else 'partial'})
    ytd = next(({'amount': w['values']['ytd_total'], 'as_of': w['date']}
                for w in reversed(metrics['weeks'])
                if w['values'].get('ytd_total') is not None), None)
    return {'weeks': weeks, 'ytd': ytd}

# Canary: leadership-tier terms must never reach a STAFF payload. The finance
# builder has its own guard; this one also covers future members payloads.
STAFF_CANARY = ('payroll', 'runway', 'debit_total', 'giver_status', 'last_gift')
def assert_staff_safe(payload, name):
    # The payment-request board's status text may legitimately say "gusto"/
    # "payroll" (staff already see it on the Apps Script board) — check the
    # payload with the board REMOVED so a leak elsewhere can't hide behind it.
    scrubbed = json.loads(json.dumps(payload))
    if isinstance(scrubbed.get('finance'), dict):
        scrubbed['finance'].pop('board', None)
    blob = json.dumps(scrubbed).lower()
    hits = [t for t in STAFF_CANARY if t in blob]
    if hits:
        raise SystemExit(f'CANARY: staff payload {name} contains {hits} — build aborted.')

try:
    finance = json.load(open(DATA/'finance.json'))
    fin_payload = {'finance': finance, 'giving': giving_series(),
                   'giving_participation': giving_part}
    assert_staff_safe(fin_payload, 'finance.html')
    inject('finance.template.html', 'finance.html', fin_payload)
except FileNotFoundError:
    print('skip finance.html (no data/finance.json — run Finance Agent'
          ' build_teamhub_finance.py)')

# ---------- members page (staff) + leadership giving ----------
# Sources under data/members/ are written by Planning Center Agent scripts
# (serving-backfill.mjs, members-snapshot.mjs, giving-backfill.mjs).
# STAFF members payload: NO GIVING KEYS AT ALL (canary enforces).
def month_seq(start, end):
    ms, (y, m) = [], (int(start[:4]), int(start[5:7]))
    while f'{y:04d}-{m:02d}' <= end[:7]:
        ms.append(f'{y:04d}-{m:02d}')
        y, m = (y + (m == 12), m % 12 + 1)
    return ms

def members_payload():
    snap = json.load(open(DATA/'members/members-latest.json'))
    ledger = json.load(open(DATA/'members/serving-history.json'))
    today = datetime.date.today().isoformat()
    months = month_seq('2025-02', today)
    try:
        prayer = json.load(open(DATA/'members/prayer-attendance.json'))
    except FileNotFoundError:
        prayer = None

    # page set: members, anyone who served in 18 months, or current team rosters.
    # (NOT the raw membership label — PCO stamps one on nearly every contact,
    # which ballooned the page to 1,700 rows on the first build.)
    ppl = [p for p in snap['people']
           if p['is_member'] or p['serves_18mo'] > 0 or p['teams']]
    ppl.sort(key=lambda p: (p.get('name') or '').lower())

    # heatmap: distinct confirmed Sundays per month; None (= n/a) before a
    # person's first record of ANY status — participation.py's rule.
    for p in ppl:
        recs = (ledger['people'].get(p['person_id']) or {}).get('records', [])
        by_month = {}
        for r in recs:
            if r['status'] in ('C', 'U'):  # present = scheduled, didn't decline
                by_month.setdefault(r['date'][:7], set()).add(r['date'])
        first = recs[0]['date'][:7] if recs else None
        p['heat'] = [None if (first is None or ym < first)
                     else len(by_month.get(ym, ()))
                     for ym in months]

    # prayer-call counts per person (90 days), if capture has begun
    if prayer:
        cutoff = (datetime.date.today() - datetime.timedelta(days=90)).isoformat()
        counts = {}
        for call in prayer.get('calls', []):
            if call['date'] >= cutoff:
                for part in call.get('participants', []):
                    if part.get('person_id'):
                        counts[part['person_id']] = counts.get(part['person_id'], 0) + 1
        for p in ppl:
            p['prayer_90d'] = counts.get(p['person_id'], 0)

    # --- recent load + streaks (rest signal) --------------------------------
    # last 6 ledger Sundays; how many each person served, and their current
    # consecutive-Sunday streak. 5+ of 6 = carrying a lot; a long streak with
    # no week off is the "needs rest" pastoral flag Andrew asked for.
    all_sundays = sorted({pl['date'] for pl in ledger['plans'].values()}, reverse=True)
    last6 = set(all_sundays[:6])
    for p in ppl:
        recs = (ledger['people'].get(p['person_id']) or {}).get('records', [])
        confirmed = {r['date'] for r in recs if r['status'] in ('C', 'U')}
        p['recent6'] = len(last6 & confirmed)
        streak = 0
        for d in all_sundays:
            if d in confirmed:
                streak += 1
            else:
                break
        p['streak'] = streak

    # --- teams section -------------------------------------------------------
    def _days_since(iso):
        return (datetime.date.today() - datetime.date.fromisoformat(iso)).days
    teams_map = {}
    for p in ppl:
        for t in p['teams']:
            tm = teams_map.setdefault(t, {'team': t, 'roster': 0, 'active_60d': 0,
                                          'dormant': 0, 'members': 0, 'people': []})
            tm['roster'] += 1
            tm['members'] += 1 if p['is_member'] else 0
            if p['last_served'] and _days_since(p['last_served']) <= 60:
                tm['active_60d'] += 1
            elif not p['last_served'] or _days_since(p['last_served']) > 91:
                tm['dormant'] += 1   # no confirmed serve in ~13 Sundays
            tm['people'].append(p['name'])
    teams = sorted(teams_map.values(), key=lambda t: -t['roster'])
    for t in teams:
        t['people'].sort(key=str.lower)

    # --- giving participation windows (AGGREGATE ONLY — staff-safe) ----------
    # Computed from real donation history (PCO Giving backfill), so unlike the
    # rolling 90-day list these CAN be charted backwards. Denominator = the
    # CURRENT Members (All) list applied to past months (membership history
    # isn't versioned in PCO) — a steady-denominator approximation, flagged in
    # the UI. Only counts/percentages leave this function; no per-person data.
    giving_windows = None
    try:
        gv = json.load(open(DATA/'members/giving-by-person.json'))
        member_ids = {p['person_id'] for p in snap['people'] if p['is_member']}
        n_members = len(member_ids)
        member_months = [set(g['months_given']) for pid, g in gv['people'].items()
                         if pid in member_ids]
        def _mshift(ym, back):
            y, m = int(ym[:4]), int(ym[5:7])
            m -= back
            while m <= 0:
                y, m = y - 1, m + 12
            return f'{y:04d}-{m:02d}'
        giving_windows = {'members': n_members, 'windows': {}}
        for w in (1, 3, 6, 12):
            series = []
            for ym in months:
                span = {_mshift(ym, b) for b in range(w)}
                gave = sum(1 for mm in member_months if mm & span)
                series.append({'month': ym, 'gave': gave,
                               'pct': round(gave / n_members * 100, 1) if n_members else None})
            giving_windows['windows'][str(w)] = series
    except FileNotFoundError:
        pass

    # --- gone quiet: regular servers whose serving stopped 30-97 days ago ---
    # The drift window where a check-in call still lands easily. "Regular" =
    # 6+ distinct Sundays served in 18 months. Excludes shared accounts.
    NONPERSONS = {'audio link'}
    # Staff see each other weekly — they don't need a drift call. Tier list is
    # the shared source of truth in Planning Center Agent/data/tiers.json.
    try:
        _tiers = json.load(open(ROOT.parent/'Planning Center Agent/data/tiers.json'))
        STAFF_NAMES = {n.lower() for n in _tiers.get('staff', [])}
    except FileNotFoundError:
        STAFF_NAMES = set()
    gone_quiet = []
    for p in ppl:
        if (p['name'] or '').lower() in NONPERSONS or (p['name'] or '').lower() in STAFF_NAMES:
            continue
        if p['last_served'] and p['serves_18mo'] >= 6:
            d = _days_since(p['last_served'])
            if 30 <= d <= 97:
                gone_quiet.append({'name': p['name'], 'person_id': p['person_id'],
                                   'last_served': p['last_served'], 'days': d,
                                   'serves_18mo': p['serves_18mo'],
                                   'teams': p['teams']})
    gone_quiet.sort(key=lambda g: -g['days'])

    # --- new servers: FIRST CONFIRMED serve within the last 60 days ---------
    new_servers = []
    for p in ppl:
        if (p['name'] or '').lower() in NONPERSONS:
            continue
        recs = (ledger['people'].get(p['person_id']) or {}).get('records', [])
        confirmed = sorted(r['date'] for r in recs if r['status'] in ('C', 'U'))
        p['new_server'] = bool(confirmed and _days_since(confirmed[0]) <= 60)
        if p['new_server']:
            new_servers.append({'name': p['name'], 'person_id': p['person_id'],
                                'first': confirmed[0], 'serves': len(set(confirmed)),
                                'teams': p['teams']})
    new_servers.sort(key=lambda n: n['first'])

    served60 = sum(1 for p in ppl if p['last_served'] and
                   (datetime.date.today() - datetime.date.fromisoformat(p['last_served'])).days <= 60)
    weekly = {}
    for person in ledger['people'].values():
        for r in person['records']:
            if r['status'] in ('C', 'U'):
                weekly.setdefault(r['date'], set()).add(id(person))
    serve_trend = [{'month': ym,
                    'volunteers': max((len(v) for d, v in weekly.items()
                                       if d[:7] == ym), default=0)}
                   for ym in months]
    return {'generated': snap['generated_at'][:10], 'months': months,
            'overview': {'members': snap['members_list_count'],
                         'served_60d': served60,
                         'on_teams': sum(1 for p in ppl if p['teams']),
                         'served_18mo': sum(1 for p in ppl if p['serves_18mo'] > 0)},
            'serve_trend': serve_trend,
            'people': ppl,
            'teams': teams,
            'giving_windows': giving_windows,
            'gone_quiet': gone_quiet,
            'new_servers': new_servers,
            # shared accounts, not humans — excluded from rest/high-load flags
            'nonpersons': ['Audio Link'],
            'prayer_started': bool(prayer),
            'giving_participation': giving_part}

def leadership_giving():
    gv = json.load(open(DATA/'members/giving-by-person.json'))
    snap = json.load(open(DATA/'members/members-latest.json'))
    by_id = {p['person_id']: p for p in snap['people']}
    rows = []
    for pid, g in gv['people'].items():
        m = by_id.get(pid, {})
        rows.append({'person_id': pid, 'name': g['name'] or m.get('name'),
                     'is_member': m.get('is_member', False),
                     'giver_status': g['giver_status'],
                     'first_gift': g['first_gift'], 'last_gift': g['last_gift'],
                     'gift_count': g['gift_count'],
                     'months_given': g['months_given'],
                     'total_cents': g['total_cents']})
    rows.sort(key=lambda r: r['last_gift'], reverse=True)
    never = [{'person_id': p['person_id'], 'name': p['name']}
             for p in snap['people']
             if p['is_member'] and p['person_id'] not in gv['people']]
    st = {}
    for r in rows:
        st[r['giver_status']] = st.get(r['giver_status'], 0) + 1
    return {'generated': gv['generated_at'][:10], 'since': gv['since'],
            'summary': {**st, 'never_members': len(never),
                        'total_givers': len(rows)},
            'people': rows, 'never': sorted(never, key=lambda n: (n['name'] or '').lower())}

OFF_TEAM_RE = re.compile(
    r"not (on|part of|in).*(team|ministry)|no longer|stepped (down|back|away)|off the team", re.I)

def leadership_insights():
    """Serving x giving quadrant + decline-reason patterns. LEADERSHIP ONLY —
    touches per-person giving and verbatim decline reasons (people say
    personal things in declines; those never reach the staff pages)."""
    gv = json.load(open(DATA/'members/giving-by-person.json'))
    snap = json.load(open(DATA/'members/members-latest.json'))
    ledger = json.load(open(DATA/'members/serving-history.json'))
    today = datetime.date.today()
    days = lambda iso: (today - datetime.date.fromisoformat(iso)).days
    NONPERSONS = {'audio link'}

    people = [p for p in snap['people'] if (p['name'] or '').lower() not in NONPERSONS]
    by_id = {p['person_id']: p for p in people}
    last_gift = {pid: g['last_gift'] for pid, g in gv['people'].items()}

    serving_not_giving, giving_not_serving = [], []
    for p in people:
        active_server = p['last_served'] and days(p['last_served']) <= 60
        lg = last_gift.get(p['person_id'])
        if active_server and (lg is None or days(lg) > 180):
            serving_not_giving.append({'name': p['name'], 'is_member': p['is_member'],
                                       'teams': p['teams'], 'last_served': p['last_served'],
                                       'last_gift': lg})
        if lg is not None and days(lg) <= 90 and \
           (not p['last_served'] or days(p['last_served']) > 183):
            giving_not_serving.append({'name': p['name'], 'is_member': p['is_member'],
                                       'last_gift': lg, 'last_served': p['last_served'],
                                       'on_teams': bool(p['teams'])})
    serving_not_giving.sort(key=lambda r: (r['last_gift'] or ''), reverse=False)
    giving_not_serving.sort(key=lambda r: r['last_gift'], reverse=True)

    # decline patterns from the serving ledger (status D + reason text)
    cutoff13 = (today - datetime.timedelta(weeks=13)).isoformat()
    decliners = []
    for pid, person in ledger['people'].items():
        if (person['name'] or '').lower() in NONPERSONS:
            continue
        ds = [r for r in person['records'] if r['status'] == 'D']
        if not ds:
            continue
        reasons = [{'date': r['date'], 'team': r['team'],
                    'reason': (r['decline_reason'] or '').strip()}
                   for r in ds if (r['decline_reason'] or '').strip()]
        off_team = any(OFF_TEAM_RE.search(x['reason']) for x in reasons)
        recent = sum(1 for r in ds if r['date'] >= cutoff13)
        if len(ds) >= 3 or off_team:
            decliners.append({'name': person['name'],
                              'person_id': pid,
                              'is_member': by_id.get(pid, {}).get('is_member', False),
                              'declines_18mo': len(ds), 'declines_13wk': recent,
                              'off_team_language': off_team,
                              'recent_reasons': reasons[-3:]})
    decliners.sort(key=lambda d: (-int(d['off_team_language']), -d['declines_13wk'],
                                  -d['declines_18mo']))
    return {'serving_not_giving': serving_not_giving,
            'giving_not_serving': giving_not_serving,
            'decliners': decliners}

try:
    mp = members_payload()
    assert_staff_safe(mp, 'members.html')
    inject('members.template.html', 'members.html', mp)
except FileNotFoundError as e:
    print(f'skip members.html ({e.filename or e})')

try:
    leadership = json.load(open(DATA/'finance_leadership.json'))
    try:
        leadership['giving_people'] = leadership_giving()
        leadership['insights'] = leadership_insights()
    except FileNotFoundError:
        pass  # placeholder card renders until giving data exists
    inject('leadership.template.html', 'leadership.html', leadership)
except FileNotFoundError:
    print('skip leadership.html (no data/finance_leadership.json)')
