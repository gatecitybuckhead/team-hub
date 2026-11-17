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

    return {
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
