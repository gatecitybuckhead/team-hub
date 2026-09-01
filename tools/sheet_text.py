#!/usr/bin/env python3
"""Turn a Google Drive MCP connector sheet dump into rows of cells.

WHY THIS EXISTS (2026-09-01): the Team Hub used to read both source Google
Sheets by driving the real Chrome browser through the Claude-in-Chrome
extension. That made the whole Tuesday refresh depend on a browser session
being interactively signed in, and it silently broke on 2026-09-01 when the
extension was not paired — no metrics week, no debrief, no narrative.

The Drive MCP connector reads both sheets with a stored OAuth token, no
browser and no interactive session. It returns the WHOLE spreadsheet (every
tab) as one markdown-ish table, tabs concatenated, newest tab first, with no
tab labels. Verified 2026-09-01: 1028 lines / 145K chars for the metrics
sheet, reaching the current quarter AND the bottom GENERAL attendance block.
The old "the connector truncates before the newest quarter" note was stale.

The dump is saved to a file by the MCP tool (it is too big to return inline),
so nothing here ever enters an agent's context.

Cell text arrives markdown-escaped: `\\#`, `\\!`, `\\&`, `\\--`, `\\|`.
"""
import json, re

_UNESC = re.compile(r'\\([\\`*_{}\[\]()#+\-.!&|~<>])')
_SPLIT = re.compile(r'(?<!\\)\|')


def unescape(s):
    return _UNESC.sub(r'\1', s).strip()


def load_rows(path):
    """Drive dump file -> list of row-cell-lists. Separator rows dropped."""
    with open(path) as fh:
        blob = json.load(fh)
    text = blob['fileContent'] if isinstance(blob, dict) else str(blob)
    rows = []
    for line in text.split('\n'):
        s = line.strip()
        if not s:
            rows.append([])
            continue
        s = s.strip('|')
        cells = [unescape(c) for c in _SPLIT.split(s)]
        # markdown alignment row: every cell is like :-: or ---
        if cells and all(re.fullmatch(r':?-+:?', c or '-') for c in cells):
            rows.append([])
            continue
        rows.append(cells)
    return rows


def cell(row, j):
    return row[j] if j < len(row) else ''
