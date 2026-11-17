"""Payload for staff/serving.html — the Serving Teams Review (11/17/2026).

Sources (all gitignored under data/):
  members/serving-history.json      weekly serving ledger (PCO Agent serving-backfill.mjs)
  members/members-latest.json       People snapshot (members-snapshot.mjs)
  members/snapshots/2026-08.json    baseline for "who joined / left a team"
  members/serving-review-live.json  live rosters + leaders + open slots + recent
                                    Sundays + membership pathway
                                    (PCO Agent automation/serving-review-pull.mjs)
  serving_review_notes.json         hand-written context: transitions, observations,
                                    housekeeping (Claude + Andrew)

STAFF TIER. No giving of any kind. No per-person decline counts or decline
reasons (donor-audit rule 9/29/2026: the declines list is Mini-only) — declines
appear only as a team-level percentage.
"""
import json, collections, datetime

SERVED = ('C', 'U')          # same "present" convention as members-snapshot.mjs
WINDOW = 13                  # Sundays (~a quarter)
THURSDAY_ROLES = {'Connections', 'Announcements', 'Offering'}   # filled the Thursday before
NOT_PEOPLE = {'Audio Link'}  # remote audio service placeholder, not a volunteer
BASELINE = '2026-08'


def _load(p):
    return json.load(open(p))


def payload(DATA):
    M = DATA / 'members'
    ledger = _load(M / 'serving-history.json')
    snap = _load(M / 'members-latest.json')
    base = _load(M / 'snapshots' / f'{BASELINE}.json')
    live = _load(M / 'serving-review-live.json')
    notes = _load(DATA / 'serving_review_notes.json')
    tiers = _load(DATA.parent.parent / 'Planning Center Agent' / 'data' / 'tiers.json')
    staff = set(tiers['staff']) - set(notes.get('no_longer_staff', []))
    leads = set(tiers['area_leads'])

    P = {p['person_id']: p for p in snap['people']}
    B = {p['person_id']: p for p in base['people']}

    # --- serving records: ledger + the recent Sundays pulled live (live wins per date)
    live_dates = {s['date'] for s in live['recent_sundays']}
    recs = []
    for pid, p in ledger['people'].items():
        for r in p['records']:
            if r['date'] not in live_dates:
                recs.append({'pid': pid, 'name': p['name'], 'date': r['date'], 'team': r['team'],
                             'position': r['position'], 'status': r['status']})
    for s in live['recent_sundays']:
        for r in s['rows']:
            recs.append({'pid': r['person_id'], 'name': r['name'], 'date': s['date'], 'team': r['team'],
                         'position': r['position'], 'status': r['status']})
    # Sermons count as serving (Andrew 11/17/2026). Planning Center has no preaching
    # position; the preaching sheet (via serving-review-pull.mjs) is the source.
    pid_by_name = {}
    for p in snap['people']:
        if p.get('status') != 'inactive':
            pid_by_name.setdefault((p['name'] or '').strip().lower(), p['person_id'])
    for x in live.get('preaching', []):
        pid = pid_by_name.get(x['name'].strip().lower())
        if pid:
            recs.append({'pid': pid, 'name': P[pid]['name'], 'date': x['date'], 'team': 'Preaching',
                         'position': 'Preaching', 'status': 'C'})
    recs = [r for r in recs if r['name'] not in NOT_PEOPLE]
    dates = sorted({r['date'] for r in recs})
    W = dates[-WINDOW:]
    inw = [r for r in recs if r['date'] in W]
    srv = [r for r in inw if r['status'] in SERVED]
    names = {r['pid']: r['name'] for r in recs}

    last_served = {}
    for r in recs:
        if r['status'] in SERVED and r['date'] > last_served.get(r['pid'], ''):
            last_served[r['pid']] = r['date']

    def tier(name):
        return 'staff' if name in staff else 'lead' if name in leads else 'vol'

    # --- upcoming open slots (skip Sabbath / no-service plans)
    plans = [p for p in live['plans'] if 'SABBATH' not in (p['title'] or '').upper()][:5]
    team_by_id = {t['id']: t['name'] for t in live['teams']}

    # --- teams
    roster_ids = collections.defaultdict(set)
    teams = []
    for t in live['teams']:
        tn = t['name']
        ros = {}
        for r in t['roster']:
            if r['name'] in NOT_PEOPLE:
                continue
            ros.setdefault(r['person_id'], {'name': r['name'], 'positions': []})['positions'].append(r['position'])
            roster_ids[r['person_id']].add(tn)
        trecs = [r for r in srv if r['team'] == tn]
        act = collections.defaultdict(lambda: {'sundays': set(), 'positions': collections.Counter()})
        for r in trecs:
            act[r['pid']]['sundays'].add(r['date'])
            act[r['pid']]['positions'][r['position']] += 1
        active = sorted(({'name': names[pid], 'sundays': len(a['sundays']),
                          'positions': [k for k, _ in a['positions'].most_common()],
                          'rostered': pid in ros, 'tier': tier(names[pid])}
                         for pid, a in act.items()), key=lambda x: (-x['sundays'], x['name']))
        idle = sorted(({'name': v['name'], 'positions': sorted(set(v['positions'])),
                        'last_served': last_served.get(pid)}
                       for pid, v in ros.items() if pid not in act),
                      key=lambda x: (x['last_served'] or ''), reverse=True)
        per_sunday = [len({r['pid'] for r in trecs if r['date'] == d}) for d in W]
        sched = [r for r in inw if r['team'] == tn]
        declined = sum(1 for r in sched if r['status'] == 'D')
        opens = []
        for p in plans:
            for n in p['needed']:
                if team_by_id.get(n['team_id']) == tn:
                    opens.append({'date': p['date'], 'position': n['position'], 'qty': n['qty'],
                                  'thursday': n['position'] in THURSDAY_ROLES})
        avg = sum(per_sunday) / len(W)
        teams.append({
            'id': t['id'], 'name': tn, 'leaders': [l for l in t['leaders'] if l not in notes.get('former_people', [])],
            'roster': len(ros), 'active': active, 'idle': idle,
            'positions': collections.Counter(p for v in ros.values() for p in v['positions']).most_common(),
            'per_sunday': per_sunday, 'avg_per_sunday': round(avg, 1),
            'depth': round(len(active) / avg, 1) if avg else None,
            'decline_pct': round(declined / len(sched) * 100) if sched else None,
            'open': opens, 'open_slots': sum(o['qty'] for o in opens if not o['thursday']),
            'note': notes.get('team_notes', {}).get(tn),
        })
    order = notes.get('team_order', [])
    teams.sort(key=lambda t: order.index(t['name']) if t['name'] in order else 99)

    # --- heavy servers (any team, distinct Sundays)
    sund = collections.defaultdict(set)
    pteams = collections.defaultdict(set)
    for r in srv:
        sund[r['pid']].add(r['date'])
        pteams[r['pid']].add(r['team'])
    heavy = sorted(({'name': names[pid], 'sundays': len(s), 'teams': sorted(pteams[pid]),
                     'tier': tier(names[pid])}
                    for pid, s in sund.items() if len(s) >= 8), key=lambda x: (-x['sundays'], x['name']))

    # --- people on a team now who weren't in August (computed), with context notes
    tn_notes = notes.get('joined_notes', {})
    joined = []
    for pid, tset in roster_ids.items():
        before = set((B.get(pid) or {}).get('teams') or [])
        new = sorted(tset - before)
        if new:
            nm = (P.get(pid) or {}).get('name') or names.get(pid) or '?'
            joined.append({'name': nm, 'teams': new, 'served': len(sund.get(pid, ())),
                           'note': tn_notes.get(nm)})
    for nm, note in notes.get('joined_extra', {}).items():
        if not any(j['name'] == nm for j in joined):
            joined.append({'name': nm, 'teams': note.get('teams', []), 'served': note.get('served', 0),
                           'note': note.get('note')})
    joined.sort(key=lambda j: (j['served'] > 0, j['name']))

    # --- members (current Members list) not on any Sunday team
    cards = {c['person_id']: c for c in live['membership_cards']}
    skip = set(notes.get('unplugged_skip', []))
    unplugged = []
    for m in live['members_list']:
        pid = m['person_id']
        if roster_ids.get(pid) or m['name'] in skip:
            continue
        p = P.get(pid) or {}
        unplugged.append({'name': m['name'], 'last_served': last_served.get(pid),
                          'served_here': len(sund.get(pid, ())),
                          'step': (cards.get(pid) or {}).get('step'),
                          'since': p.get('created_at'),
                          'note': notes.get('unplugged_notes', {}).get(m['name'])})
    unplugged.sort(key=lambda u: (u['step'] != 'New Members Lunch', u['last_served'] is not None,
                                  u['last_served'] or '', u['name']))

    # --- membership pathway, grouped by step
    steps = collections.defaultdict(list)
    for c in live['membership_cards']:
        steps[c['step']].append({'name': c['name'], 'since': c['created'],
                                 'teams': sorted(roster_ids.get(c['person_id'], []))})
    step_order = notes.get('step_order', [])
    pathway = sorted(({'step': k, 'people': sorted(v, key=lambda x: x['since'], reverse=True)}
                      for k, v in steps.items()),
                     key=lambda s: step_order.index(s['step']) if s['step'] in step_order else 99)

    member_ids = {m['person_id'] for m in live['members_list']}
    members_serving = sum(1 for pid in member_ids if sund.get(pid))
    all_people = {r['pid'] for r in srv}
    per_sun_total = [len({r['pid'] for r in srv if r['date'] == d}) for d in W]

    # call times (UTC in PCO → Eastern; Sunday Services are EST/EDT)
    times = []
    if plans:
        for x in sorted(plans[0]['times'], key=lambda x: x['starts']):
            t = datetime.datetime.fromisoformat(x['starts'].replace('Z', '+00:00'))
            off = -4 if 3 < t.month < 11 or (t.month == 11 and t.day < 2) else -5
            loc = (t + datetime.timedelta(hours=off))
            times.append({'name': x['name'] or 'Service', 'time': loc.strftime('%-I:%M')})

    # --- per-member behaviors (Halima's layout, 11/17 v2) -------------------
    sundays = sorted({c['date'] for c in live['checkins']
                      if datetime.date.fromisoformat(c['date']).weekday() == 6})
    all_sun = []
    d0 = datetime.date.fromisoformat(W[0])
    while d0.isoformat() <= W[-1]:
        all_sun.append(d0.isoformat()); d0 += datetime.timedelta(days=7)
    head = {d: sum(1 for c in live['checkins'] if c['date'] == d) for d in all_sun}
    tracked = [d for d in all_sun if head[d]]
    att = collections.defaultdict(set)
    for c in live['checkins']:
        if c['person_id'] and c['date'] in tracked:
            att[c['person_id']].add(c['date'])
    series = [f['name'] for f in live['formation']]
    forming = collections.defaultdict(list)
    for f in live['formation']:
        for pid in f['person_ids']:
            forming[pid].append(f['name'])
    core, cong = set(live['core_ids']), set(live['congregation_ids'])
    prev_members = {p['person_id'] for p in _load(M / 'snapshots' / '2026-10.json')['people'] if p['is_member']}
    heavy_names = {h['name'] for h in heavy}
    people = []
    for m in live['members_list']:
        pid, nm = m['person_id'], m['name']
        if nm in notes.get('people_skip', []):
            continue
        conf = sorted({r['date'] for r in srv if r['pid'] == pid})
        a = sorted(att.get(pid, ()))
        card = cards.get(pid) or {}
        people.append({
            'id': pid, 'name': nm,
            'seg': 'Core' if pid in core else 'Congregation' if pid in cong else 'Member',
            'is_new': pid not in prev_members or card.get('step') == 'New Members Lunch',
            'tier': tier(nm),
            'att': len(a), 'att_pct': round(len(a) / len(tracked) * 100) if tracked else 0,
            'last_att': a[-1] if a else None,
            'forming': forming.get(pid, []),
            'serve': len(conf), 'last_served': last_served.get(pid),
            'teams': sorted(roster_ids.get(pid, [])),
            'served_teams': sorted({r['team'] for r in srv if r['pid'] == pid}),
            'heavy': nm in heavy_names and tier(nm) == 'vol',
            'pray': live['prayer']['scheduled'].get(pid, []),
            'pray_roster': live['prayer']['roster'].get(pid, []),
            'step': card.get('step'),
            'note': notes.get('person_notes', {}).get(nm),
        })
    # members giving % (aggregate only — the PCO list reading, never per person here)
    gp = live.get('giving_count') if (live.get('giving_count') or {}).get('givers') else None
    try:
        rd = [] if gp else _load(DATA / 'giving_participation.json').get('readings', [])
        if rd:
            r = rd[-1]
            gp = {'date': r.get('sunday'), 'givers': r.get('giving'), 'members': r.get('members'), 'pct': r.get('pct')}
    except FileNotFoundError:
        pass

    return {
        'people': people, 'tracked': tracked, 'all_sundays': all_sun, 'head': head,
        'series': series, 'prayer_types': live['prayer']['types'], 'giving_pct': gp,
        'invite_teams': notes.get('invite_teams', []),
        'built': datetime.date.today().isoformat(),
        'window': {'from': W[0], 'to': W[-1], 'sundays': len(W)},
        'kpis': {
            'members': len(member_ids), 'members_serving': members_serving,
            'members_unplugged': len(unplugged),
            'people_serving': len(all_people),
            'avg_per_sunday': round(sum(per_sun_total) / len(W)),
            'open_slots': sum(t['open_slots'] for t in teams),
            'pathway_now': sum(len(s['people']) for s in pathway if s['step'] == 'New Members Lunch'),
        },
        'upcoming': [{'date': p['date']} for p in plans],
        'call_times': times,
        'teams': teams, 'heavy': heavy, 'joined': joined, 'unplugged': unplugged,
        'pathway': pathway,
        'left': notes['left'], 'coming': notes.get('coming', []),
        'observations': notes['observations'], 'housekeeping': notes['housekeeping'],
        'questions': notes.get('questions', []),
    }


def add_person_giving(payload, DATA):
    """MINI COPY ONLY (gcb-people.html). Adds yes/no-by-month giving per member:
    2 = gave on their own record, 1 = their household gave (spouse's joint record),
    0 = nothing recorded. Never amounts. NEVER call this for the Team Hub page."""
    M = DATA / 'members'
    gv = _load(M / 'giving-by-person.json')
    snap = _load(M / 'members-latest.json')
    hh = snap.get('households') or {}
    hh_of = {}
    for hid, h in hh.items():
        for pid in h.get('people', []):
            hh_of.setdefault(pid, hid)
    mine = {pid: set(g.get('months_given') or []) for pid, g in gv['people'].items() if pid != 'anonymous'}
    by_hh = collections.defaultdict(set)
    for pid, ms in mine.items():
        if hh_of.get(pid):
            by_hh[hh_of[pid]] |= ms
    today = datetime.date.today()
    months = []
    y, m = today.year, today.month
    for _ in range(12):
        months.append(f'{y}-{m:02d}')
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    months.reverse()
    for p in payload['people']:
        own, fam = mine.get(p['id'], set()), by_hh.get(hh_of.get(p['id']), set())
        p['give'] = [2 if k in own else 1 if k in fam else 0 for k in months]
    payload['months'] = months
    payload['where'] = 'mini'
    return payload


def to_artifact(html):
    """Team copy → claude.ai artifact page (11/17/2026, Andrew: 'like Halima's').
    The publish skeleton supplies doctype/html/head/body + charset/viewport, so strip
    ours; keep <title>, fonts, style, script. Light-only by choice (Halima's look):
    body background and every color are set explicitly. No refresh pill (its fetch
    to Team Hub is blocked in the artifact frame)."""
    import re
    html = re.sub(r'<!DOCTYPE html>\s*<html[^>]*>\s*<head>\s*', '', html, flags=re.I)
    html = re.sub(r'<meta charset="utf-8">\s*<meta name="viewport"[^>]*>\s*<meta name="robots"[^>]*>\s*', '', html)
    html = html.replace('<title>GCB People &amp; Teams</title>',
                        '<title>GateCity People &amp; Teams</title>\n<meta name="claude:viewport-fit-sides" content="cover">', 1)
    html = re.sub(r'</head>\s*<body>', '', html, count=1)
    html = re.sub(r'</body>\s*</html>\s*$', '', html)
    return html
