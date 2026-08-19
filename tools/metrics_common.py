#!/usr/bin/env python3
"""Shared cell-cleaning / key-slugging logic for the metrics pipeline.

Imported by both tools/parse_metrics.py (full-history xlsx rebuild) and
tools/add_metrics_week.py (weekly increment). Keeping it here means the two
paths can never drift and produce different keys for the same sheet label.
"""
import re

# The sheet gives every metric TWO cells per week: a "Data Set" column and a
# "Sunday" column. For counts (attendance, leaders…) the Sunday cell supersedes
# the Data Set cell — they measure the same thing at different moments.
#
# Giving dollars are the exception: the GIVE Agent writes Mon–Sat into the Data
# Set cell and Sunday alone into the Sunday cell, so they are DISJOINT and the
# week is their SUM. Collapsing them by precedence silently dropped Sunday —
# the church's biggest giving day — from every "giving last week" figure until
# 2026-08-19. Ingest paths keep both cells for these keys; build.py adds them.
GIVING_KEYS = frozenset({
    'week_s_tithes_offerings_digital',
    'week_s_tithes_offerings_cash',
    'special_gifts',
})

def clean(v):
    """Sheet cell -> number or None. Handles $, commas, %, error strings."""
    if v is None: return None
    if isinstance(v, (int, float)): return round(float(v), 2)
    s = str(v).strip()
    if s in ('', '-', 'x', 'n/a', 'N/A', '#DIV/0!', '#REF!', '#VALUE!', 'TBD', '?'):
        return None
    s2 = s.replace('$', '').replace(',', '').replace('%%', '%')
    m = re.fullmatch(r'(-?\d+(?:\.\d+)?)%', s2)
    if m: return round(float(m.group(1)) / 100, 4)
    try: return round(float(s2), 2)
    except ValueError: return None

def slug(s):
    return re.sub(r'[^a-z0-9]+', '_', s.lower()).strip('_')

# label drift across years -> canonical keys
ALIASES = {
    'total_members': 'total_members_core_congregation',
    'attendance_in_garage': 'attendance_in_sanctuary',
    'vols_in_teams_sun_service': 'total_people_in_sunday_teams',
    # 2026-08 sheet rename: "# Total People in Sunday Teams (- Kids Min)"
    'total_people_in_sunday_teams_kids_min': 'total_people_in_sunday_teams',
}

def canon(key):
    return ALIASES.get(key, key)

def key_for(label):
    return canon(slug(label))
