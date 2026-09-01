#!/usr/bin/env python3
"""Drive sheet dump -> new debrief responses appended to data/debrief.json. No browser.

Usage:
    python3 tools/extract_debrief.py --file <drive-dump.json> --dry-run
    python3 tools/extract_debrief.py --file <drive-dump.json> --sunday 2026-08-30

Replaces the Claude-in-Chrome scrape + a hand-written _add_debrief_week_*.py
script per week. Reads the saved Drive connector dump, shapes rows with
debrief_common (same code parse_debrief.py uses), and does replace-or-append
BY SUNDAY on data/debrief.json -- so re-running for the same Sunday is safe and
idempotent, and the hand-added 2026-08-02 Family Fun Day week (which came from a
different form) is never touched. NEVER run parse_debrief.py as a full rebuild:
that wipes Family Fun Day.

SHEET LAYOUT (confirmed 2026-09-01): 33 columns, one header row whose first
cell is 'Timestamp', ~470 response rows. Column 1 (1-based) is the timestamp
'M/D/YYYY H:MM:SS', column 2 is Name, column 3 is the overall 1-10. ROW ORDER
IS MIXED -- the top block is newest-first but recent responses are appended
ascending at the BOTTOM, so every row is scanned rather than assuming order.
The sheet also holds 2025 rows, so filtering is by FULL DATE, never month/day.

A response belongs to the Sunday on or before its submission date, so Mon 8/31
and Tue 9/1 submissions both count toward Sunday 8/30.
"""
import argparse, datetime, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sheet_text import load_rows, cell
from debrief_common import record, weekly_for

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEBRIEF = os.path.join(HERE, 'data', 'debrief.json')
TS = re.compile(r'^(\d{1,2})/(\d{1,2})/(\d{4})\b')


def parse_rows(path):
    rows = load_rows(path)
    hdr = next((i for i, r in enumerate(rows) if r and cell(r, 0).strip() == 'Timestamp'), None)
    if hdr is None:
        raise SystemExit('FATAL: no header row with a "Timestamp" first cell — wrong sheet?')
    out = []
    for r in rows[hdr + 1:]:
        if not r:
            continue
        m = TS.match(cell(r, 0))
        if not m:
            continue
        mo, da, yr = (int(x) for x in m.groups())
        try:
            d = datetime.date(yr, mo, da)
        except ValueError:
            continue
        get = lambda c1: (r[c1 - 1] if c1 - 1 < len(r) else '') or None
        out.append(record(get, d))
    return hdr, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--file', required=True, help='saved Drive connector dump (JSON)')
    ap.add_argument('--sunday', action='append', default=None,
                    help='limit to this Sunday (repeatable); default = every Sunday not yet stored')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--force-shrink', action='store_true',
                    help='allow a rewrite that LOWERS a stored response count')
    a = ap.parse_args()
    err = lambda *m: print(*m, file=sys.stderr)

    hdr, parsed = parse_rows(a.file)
    err('dump: header at row %d, %d response rows parsed' % (hdr, len(parsed)))

    d = json.load(open(DEBRIEF))
    have = {w['sunday']: w['n'] for w in d['weekly']}
    err('stored: %d responses, %d weeks (newest %s)'
        % (len(d['responses']), len(d['weekly']), d['weekly'][-1]['sunday']))

    by_sunday = {}
    for r in parsed:
        by_sunday.setdefault(r['sunday'], []).append(r)

    targets = a.sunday if a.sunday else sorted(s for s in by_sunday if s not in have)
    if not targets:
        err('nothing new — every Sunday in the sheet is already stored.')
        return 0

    changed = []
    for s in targets:
        fresh = by_sunday.get(s, [])
        if not fresh:
            err('  %s: NO rows in the sheet — skipped' % s)
            continue
        old_n = have.get(s)
        if old_n is not None and len(fresh) < old_n and not a.force_shrink:
            err('  %s: REFUSING — sheet has %d responses, stored has %d. '
                'A shrink means a bad read. Use --force-shrink only if real.'
                % (s, len(fresh), old_n))
            continue
        names = ', '.join(sorted(r['name'] for r in fresh))
        wk = weekly_for(fresh)
        err('  %s: %d responses (was %s), overall avg %s — %s'
            % (s, len(fresh), old_n if old_n is not None else 'new', wk['overall_avg'], names))
        changed.append((s, fresh, wk))

    if not changed:
        err('nothing written.')
        return 1

    if a.dry_run:
        err('dry run — data/debrief.json not written')
        return 0

    touched = {s for s, _, _ in changed}
    d['responses'] = [r for r in d['responses'] if r['sunday'] not in touched]
    for _, fresh, _ in changed:
        d['responses'] += fresh
    d['responses'].sort(key=lambda x: (x['sunday'], x['name']))
    d['weekly'] = [w for w in d['weekly'] if w['sunday'] not in touched]
    d['weekly'] += [wk for _, _, wk in changed]
    d['weekly'].sort(key=lambda w: w['sunday'])
    d['generated'] = datetime.date.today().isoformat()
    json.dump(d, open(DEBRIEF, 'w'), indent=1)
    err('WROTE %d responses, %d weeks (newest %s)'
        % (len(d['responses']), len(d['weekly']), d['weekly'][-1]['sunday']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
