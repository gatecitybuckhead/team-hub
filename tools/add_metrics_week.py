#!/usr/bin/env python3
"""Append ONE week to data/metrics.json from a compact pipe-delimited feed.

Why this exists: the weekly refresh used to read the whole metrics Google Sheet
into the agent's context and hand-write JSON. That was the step that stalled the
2026-07-28 run. Now the agent only has to produce ~55 short lines and this script
does all the key-slugging and file surgery — the big JSON never enters context.

Usage:
    python3 tools/add_metrics_week.py 2026-07-26 \
        --series "Journey Through James" --special "Week #2" < week.txt

stdin format, one line per sheet row IN SHEET ORDER (row order matters: when two
labels slug to the same key, the later row wins, matching parse_metrics.py):

    <label> | <Data Set cell> | <Sunday cell>

Blank cells are just empty. Values may include $ , and % — they get cleaned the
same way the full parser cleans them. Precedence: Sunday cell, else Data Set cell.
Rows where both cells are empty are skipped.

Prints a report of any label that is not already in the catalog (a new metric, or
a typo/label drift that needs an ALIASES entry in tools/metrics_common.py).
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from metrics_common import clean, key_for

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
METRICS = os.path.join(HERE, 'data', 'metrics.json')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('date', help='Sunday date, ISO (YYYY-MM-DD)')
    ap.add_argument('--series', default=None)
    ap.add_argument('--special', default=None)
    ap.add_argument('--generated', default=None, help='defaults to the given date')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()

    m = json.load(open(METRICS))
    catalog = m['catalog']

    values, unknown, seen = {}, [], 0
    for raw in sys.stdin:
        if not raw.strip() or raw.lstrip().startswith('#!'):
            continue
        parts = [p.strip() for p in raw.rstrip('\n').split('|')]
        if len(parts) < 2:
            print('SKIP unparseable line:', raw.strip(), file=sys.stderr); continue
        label = parts[0]
        ds = parts[1] if len(parts) > 1 else ''
        sun = parts[2] if len(parts) > 2 else ''
        if not label:
            continue
        seen += 1
        key = key_for(label)
        if key not in catalog:
            unknown.append((label, key))
        v = clean(sun)
        if v is None:
            v = clean(ds)
        if v is not None:
            values[key] = v

    if not values:
        print('ERROR: no usable values parsed from stdin — refusing to write.', file=sys.stderr)
        return 1

    week = {'date': a.date, 'series': a.series, 'special': a.special, 'values': values}
    dates = [w['date'] for w in m['weeks']]
    action = 'replaced' if a.date in dates else 'appended'
    if a.date in dates:
        m['weeks'][dates.index(a.date)] = week
    else:
        m['weeks'].append(week)
    m['weeks'].sort(key=lambda w: w['date'])
    m['generated'] = a.generated or a.date

    print(f'{action} {a.date}: {seen} rows read, {len(values)} values kept, '
          f'{len(m["weeks"])} weeks total (last: {m["weeks"][-1]["date"]})')
    if unknown:
        print('NOT IN CATALOG (new metric or label drift — check ALIASES):')
        for label, key in unknown:
            print(f'  {label!r} -> {key}')
    if a.dry_run:
        print('dry run — data/metrics.json not written')
        return 0
    json.dump(m, open(METRICS, 'w'), indent=1)
    return 0

if __name__ == '__main__':
    sys.exit(main())
