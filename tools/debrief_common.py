#!/usr/bin/env python3
"""Shared response-shaping logic for the debrief pipeline.

Imported by tools/parse_debrief.py (full xlsx rebuild) and
tools/extract_debrief.py (weekly increment off the Drive connector dump).
Same reason metrics_common.py exists: two ingest paths must never drift and
produce different records for the same form row.

Column numbers below are 1-BASED (openpyxl convention), because that is how
they were first written and how the form is documented. Callers pass a
`get(col)` accessor so a 0-based source just subtracts one.
"""
import datetime, re

NAMES = {'andrew': 'Andrew Faletti', 'karissa': 'Karissa', 'hannah': 'Hannah Stevens',
         'halima': 'Halima Edge', 'sarah': 'Sarah Shivers', 'angel': 'Angel Colon',
         'hazen': 'Hazen Stevens', 'haze': 'Hazen Stevens', 'alice': 'Alice Yoon',
         'son': 'Son Byrd', 'ben': 'Ben Melancon', 'kennah': 'Kennah Jones',
         'crystal': 'Crystal Nicole', 'gretchen': 'Gretchen'}

# element -> (old_col, new_col) ; ratings normalized to 0-100
ELEMENTS = {
    'Lobby Before':   (5, None), 'Lobby After':   (6, 20),
    'Worship':        (8, None), 'Announcements': (9, 21),
    'Offering':       (10, 22),  'Creative':      (11, 23),
    'Word':           (12, 24),  'Ministry Time': (13, 25),
    'Kids Setup':     (15, None), 'Kids Check-in': (16, 26),
    'Kids Class':     (17, 27),
}
# Col 19 was the kids-incident question on the ORIGINAL form; on the current
# form it's the catch-all "anything else?" field. Verified 2026-07-28: only 8 of
# 90 entries mention kids at all, the rest are production/ops notes. So it's
# tagged 'other' and the dashboard routes it to kids only when kids-related.
COMMENT_COLS = {4: 'overall', 7: 'lobby', 14: 'service', 18: 'kids', 19: 'other', 32: 'message'}
MSG = {'engagement': 28, 'content': 29, 'time_mgt': 30}   # call_to_action = 31 or 33

NULLISH = ('N/A', 'NA', 'NONE', 'N/A.', '-', '--')


def rating(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        x = float(v)
        return round(x / 10 * 100) if x > 4 else round(x / 4 * 100)  # 1-10 era vs rare numeric 4s
    s = str(v).strip()
    if s.startswith('N/A') or not s:
        return None
    m = re.match(r'([1-4])\s*=', s)
    if m:
        return round(int(m.group(1)) / 4 * 100)
    try:
        x = float(s)
        return round(x / 10 * 100) if x > 4 else round(x / 4 * 100)
    except ValueError:
        return None


def ten(v):
    if v is None:
        return None
    try:
        return round(float(str(v).strip()), 1)
    except ValueError:
        return None


def name_canon(v):
    s = str(v or '').strip()
    if not s or s == 'None':
        return 'Unknown'
    tok = re.sub(r'[^a-z]', '', s.lower().split()[0])
    return NAMES.get(tok, s.title())


def sunday_for(d):
    """The service a response belongs to: the Sunday on//before submission.

    Responses land Sunday through Tuesday, so Mon 8/31 and Tue 9/1 both belong
    to Sunday 8/30. Matches parse_debrief.py exactly.
    """
    return d - datetime.timedelta(days=(d.weekday() + 1) % 7)


def record(get, submitted):
    """get(col_1based) -> cell value; submitted -> datetime.date. -> response dict."""
    ratings = {}
    for el, (c1, c2) in ELEMENTS.items():
        v = rating(get(c1))
        if v is None and c2:
            v = rating(get(c2))
        if v is not None:
            ratings[el] = v
    msg = {k: ten(get(c)) for k, c in MSG.items()}
    msg['call_to_action'] = ten(get(31)) or ten(get(33))
    msg = {k: v for k, v in msg.items() if v is not None}
    comments = {}
    for c, tag in COMMENT_COLS.items():
        v = str(get(c) or '').strip()
        if v and v.upper() not in NULLISH:
            comments[tag] = v
    return {'sunday': sunday_for(submitted).isoformat(),
            'submitted': submitted.isoformat(),
            'name': name_canon(get(2)),
            'overall': ten(get(3)),
            'ratings': ratings, 'message': msg, 'comments': comments}


def avg(l):
    return round(sum(l) / len(l), 1) if l else None


def weekly_for(responses):
    """Aggregate a list of same-Sunday responses into one `weekly` entry."""
    n = 0
    overall, elements, message, comments, names = [], {}, {}, [], []
    for r in sorted(responses, key=lambda x: x['name']):
        n += 1
        names.append(r['name'])
        if r['overall']:
            overall.append(r['overall'])
        for k, v in r['ratings'].items():
            elements.setdefault(k, []).append(v)
        for k, v in r['message'].items():
            message.setdefault(k, []).append(v)
        for tag, t in r['comments'].items():
            comments.append({'by': r['name'], 'tag': tag, 'text': t})
    return {'sunday': responses[0]['sunday'], 'n': n, 'names': sorted(set(names)),
            'overall_avg': avg(overall),
            'elements': {e: avg(v) for e, v in elements.items()},
            'message': {m: avg(v) for m, v in message.items()},
            'comments': comments}
