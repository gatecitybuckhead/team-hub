#!/usr/bin/env python3
"""Drive sheet dump -> the pipe feed that add_metrics_week.py eats. No browser.

Usage:
    python3 tools/extract_metrics_week.py --file <drive-dump.json> --sunday 2026-08-30
    python3 tools/extract_metrics_week.py --file <dump> --list-blocks

Emits on STDOUT, one line per labelled sheet row IN SHEET ORDER:

    <metric label verbatim> | <Data Set cell> | <Sunday cell>

so it pipes straight into add_metrics_week.py. Everything else -- the chosen
block, Series, Special Service, row counts, the stale-column tell -- goes to
STDERR so it stays out of the pipe.

SHEET LAYOUT (metrics sheet, confirmed 2026-09-01):
  Each quarter tab is transposed. A header row has 'Data Set/Sunday Service:'
  in column 0. Column 0 = behavior category, column 1 = the metric label.
  Each week is a COLUMN PAIR: 'Data Set <range>' then 'Sunday <M/D>'.
  The row above the header is 'Series:' (a MERGED cell -- the value sits at
  the first column of its span, so read leftward). The row below is
  'Special Service:'.

  READ TO THE BOTTOM: there are TWO attendance rows -- a usually-blank
  '# Total Attendance' near the top and the LIVE '# TOTAL ATTENDANCE' in the
  bottom GENERAL block with '# Attendance (in Sanctuary)', '# Members (in
  Sanctuary)', '# Vols in Kids', '# of Kids'. Both slug to the same key and
  the LATER row wins, so emitting every labelled row in order is correct.
  Stopping early is the 2026-08-25 "attendance is blank" failure.
"""
import argparse, datetime, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sheet_text import load_rows, cell

HEADER_C0 = 'Data Set/Sunday Service:'


def find_headers(rows):
    return [i for i, r in enumerate(rows) if r and cell(r, 0).startswith(HEADER_C0)]


def block_end(rows, headers, h):
    later = [x for x in headers if x > h]
    return later[0] if later else len(rows)


def sunday_col(rows, h, target):
    """Column index whose header cell is 'Sunday <M/D>' for the target date."""
    pat = re.compile(r'^Sunday\s+%d/%d\b' % (target.month, target.day))
    return [j for j, v in enumerate(rows[h]) if pat.match(v or '')]


def dataset_col(rows, h, scol):
    """Nearest 'Data Set ...' column to the LEFT of the Sunday column."""
    for j in range(scol - 1, 0, -1):
        v = cell(rows[h], j)
        if v.startswith('Data Set'):
            return j
        if v.startswith('Sunday'):
            break          # ran into the previous week -- no pair
    return None


def merged_left(rows, i, col):
    """Value of a merged cell covering `col` on row i: first non-empty at/left."""
    if i < 0 or i >= len(rows):
        return ''
    for j in range(col, -1, -1):
        v = cell(rows[i], j)
        if v:
            return v
    return ''


def label_row(rows, i, h):
    """Row above the header whose col0 == label, e.g. 'Series:'."""
    return rows[i] if 0 <= i < len(rows) else []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--file', required=True, help='saved Drive connector dump (JSON)')
    ap.add_argument('--sunday', help='target Sunday, ISO')
    ap.add_argument('--list-blocks', action='store_true')
    ap.add_argument('--block', type=int, default=None,
                    help='header line number, to disambiguate a duplicate M/D')
    a = ap.parse_args()

    rows = load_rows(a.file)
    headers = find_headers(rows)
    err = lambda *m: print(*m, file=sys.stderr)
    err('dump: %d rows, %d quarter tabs (header rows at %s)'
        % (len(rows), len(headers), headers))

    if a.list_blocks or not a.sunday:
        for h in headers:
            weeks = [v for v in rows[h] if v.startswith('Sunday')]
            err('  header L%-5d %2d Sunday cols: %s .. %s'
                % (h, len(weeks), weeks[0] if weeks else '-', weeks[-1] if weeks else '-'))
        if a.list_blocks:
            return 0
        ap.error('--sunday is required unless --list-blocks')

    target = datetime.date.fromisoformat(a.sunday)
    if target.weekday() != 6:
        err('WARNING: %s is a %s, not a Sunday' % (target, target.strftime('%A')))

    hits = []
    for h in headers:
        for scol in sunday_col(rows, h, target):
            hits.append((h, scol))
    if not hits:
        err('FATAL: no header row has a "Sunday %d/%d" column. Nothing written.'
            % (target.month, target.day))
        return 2
    if len(hits) > 1:
        err('WARNING: %d blocks carry Sunday %d/%d: %s'
            % (len(hits), target.month, target.day, [h for h, _ in hits]))
        err('         Tabs come back newest-first, so the FIRST is normally right.')
        err('         Override with --block <header line> if not.')
    if a.block is not None:
        hits = [x for x in hits if x[0] == a.block] or hits
    h, scol = hits[0]
    dcol = dataset_col(rows, h, scol)
    end = block_end(rows, headers, h)

    series = merged_left(rows, h - 1, scol) if cell(label_row(rows, h - 1, h), 0).startswith('Series') else ''
    special = ''
    if h + 1 < len(rows) and cell(rows[h + 1], 0).startswith('Special Service'):
        special = cell(rows[h + 1], scol)

    err('chosen block: header L%d, Sunday col %d (%r), Data Set col %s (%r), block ends L%d'
        % (h, scol, cell(rows[h], scol), dcol,
           cell(rows[h], dcol) if dcol else '', end))
    err('Series:  %r' % series)
    err('Special: %r' % special)

    emitted = filled = 0
    out = []
    for i in range(h + 1, end):
        r = rows[i]
        if not r:
            continue
        lbl = cell(r, 1)
        if not lbl or lbl.startswith('Data Set') or lbl == ':-:':
            continue
        ds = cell(r, dcol) if dcol is not None else ''
        sun = cell(r, scol)
        out.append('%s | %s | %s' % (lbl, ds, sun))
        emitted += 1
        if ds or sun:
            filled += 1
    print('\n'.join(out))

    err('emitted %d labelled rows, %d with a value in this week' % (emitted, filled))
    if not filled:
        err('WARNING: every cell blank for this week -- sheet likely not filled in yet.')

    # stale-column tell: YTD $ Total must not DROP going forward
    ytd = [i for i in range(h + 1, end) if cell(rows[i], 1).startswith('YTD $ Total')]
    if ytd and dcol:
        r = rows[ytd[0]]
        prev = [cell(r, j) for j in range(dcol - 1, 0, -1) if cell(r, j)]
        err('YTD $ Total: this pair %r / %r, previous non-empty %r'
            % (cell(r, dcol), cell(r, scol), prev[0] if prev else None))
        err('  (a DROP going forward means this column holds prior-year template data)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
