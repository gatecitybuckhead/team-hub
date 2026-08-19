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

BOTH cells matter for giving dollars (metrics_common.GIVING_KEYS): the Data Set
cell is Mon–Sat and the Sunday cell is Sunday, so they're summed rather than
collapsed. Those rows are also written to week['giving_cols'] so build.py can
add them — always pass the third field for giving rows, even when it's blank.

Prints a report of any label that is not already in the catalog (a new metric, or
a typo/label drift that needs an ALIASES entry in tools/metrics_common.py).
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from metrics_common import clean, key_for, GIVING_KEYS

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
METRICS = os.path.join(HERE, 'data', 'metrics.json')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('date', help='Sunday date, ISO (YYYY-MM-DD)')
    ap.add_argument('--series', default=None)
    ap.add_argument('--special', default=None)
    ap.add_argument('--generated', default=None, help='defaults to the given date')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--force', action='store_true',
                    help='override the stale-column guard (see below)')
    a = ap.parse_args()

    m = json.load(open(METRICS))
    catalog = m['catalog']

    values, giving_cols, unknown, seen = {}, {}, [], 0
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
        ds_v, sun_v = clean(ds), clean(sun)
        if key in GIVING_KEYS and (ds_v is not None or sun_v is not None):
            # keep both cells — the week is Mon–Sat + Sunday (see GIVING_KEYS)
            giving_cols[key] = {'ds': ds_v, 'sun': sun_v}
        v = sun_v if sun_v is not None else ds_v
        if v is not None:
            values[key] = v

    if not values:
        print('ERROR: no usable values parsed from stdin — refusing to write.', file=sys.stderr)
        return 1

    # ---- stale-column guard -------------------------------------------------
    # The quarterly tabs are built by COPYING the previous quarter, so every
    # not-yet-entered column still holds last quarter's numbers. Ingesting one
    # silently imports the wrong week. The reliable tell is that YTD $ Total
    # DROPS: it only ever rises within a year. Caught a real near-miss on
    # 2026-08-04, where the Q3 tab's 8/2 column was a byte-for-byte copy of
    # Q2's 5/3 column and would have knocked YTD giving back ~$107K.
    new_ytd = values.get('ytd_total')
    prior = [w for w in m['weeks'] if w['date'] < a.date
             and w['values'].get('ytd_total') is not None]
    if new_ytd is not None and prior:
        last = prior[-1]
        if float(new_ytd) < float(last['values']['ytd_total']):
            print(f'REFUSING: YTD $ Total goes DOWN — {last["date"]} '
                  f'{last["values"]["ytd_total"]:,.0f} -> {a.date} {float(new_ytd):,.0f}.\n'
                  '  This column is almost certainly stale prior-quarter template data\n'
                  '  copied forward, not real numbers for this week. Check the sheet.\n'
                  '  Use --force only if you have confirmed the drop is genuine.',
                  file=sys.stderr)
            if not a.force:
                return 1

    week = {'date': a.date, 'series': a.series, 'special': a.special, 'values': values}
    if giving_cols:
        week['giving_cols'] = giving_cols
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
