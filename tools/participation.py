#!/usr/bin/env python3
"""Debrief-form participation / accountability tracker.

Builds a week-by-week grid of who submitted the Sunday Debrief form, from
data/debrief.json (which already carries `name` + `sunday` per response, so the
whole year backfills for free).

ROSTER is the fixed current core team, per Andrew (2026-07-28). Because it's a
fixed roster applied to a full year of history, weeks *before* a person's first
recorded response are rendered "n/a" rather than "missed" — we don't know when
each person joined the rhythm, and marking them absent for weeks they weren't
on the team would be wrong. Rates are computed over graded weeks only.
Someone with zero responses on record is flagged explicitly rather than
silently scored 0%.

Imported by build.py; also runnable standalone to print a text report.
"""
import json, pathlib, datetime, collections

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Fixed current core team — display name -> short label for the grid
ROSTER = [
    ("Hazen Stevens",  "Hazen"),
    ("Hannah Stevens", "Hannah"),
    ("Son Byrd",       "Son"),
    ("Halima Edge",    "Halima"),
    ("Sarah Shivers",  "Sarah"),
    ("Andrew Faletti", "Andrew"),
    ("Crystal Nicole", "Crystal"),
    ("Angel Colon",    "Angel"),
    ("Karissa",        "Karissa"),
    ("Gretchen",       "Gretchen"),
    ("Kennah Jones",   "Kennah"),
]

# Name variants seen in the raw form exports -> canonical roster name.
# parse_debrief.py normalizes most of these; these are the survivors.
ALIASES = {
    "faletti": "Andrew Faletti",
    "andrew": "Andrew Faletti",
    "crystal": "Crystal Nicole",
    "hazen": "Hazen Stevens",
    "hannah": "Hannah Stevens",
    "son": "Son Byrd",
    "halima": "Halima Edge",
    "sarah": "Sarah Shivers",
    "sarah pearl": "Sarah Shivers",
    "angel": "Angel Colon",
    "kennah": "Kennah Jones",
    "gretchen": "Gretchen",
}

# People who show up in the form history but are not on the current core team.
# Tracked separately so their responses still count toward respondent totals
# without cluttering the accountability grid.
NON_CORE_NOTE = "past/occasional contributors"


def canon(name):
    n = (name or "").strip()
    if not n:
        return None
    for full, _ in ROSTER:
        if n == full:
            return full
    low = n.lower()
    if low in ALIASES:
        return ALIASES[low]
    # last-ditch: match on first token against roster first names
    first = low.split()[0]
    for full, short in ROSTER:
        if first == short.lower():
            return full
    return n  # unknown -> passed through as non-core


def build(debrief):
    """Return the participation payload injected into the dashboard."""
    weekly = sorted(debrief["weekly"], key=lambda w: w["sunday"])
    core = [f for f, _ in ROSTER]
    core_set = set(core)
    short = dict(ROSTER)

    # sunday -> set of canonical submitter names
    by_week = {}
    for w in weekly:
        by_week[w["sunday"]] = {c for c in (canon(n) for n in w.get("names") or []) if c}

    sundays = [w["sunday"] for w in weekly]

    # first recorded response per core member (start of their graded window)
    first = {}
    for s in sundays:
        for n in by_week[s]:
            if n in core_set and n not in first:
                first[n] = s

    # ---- per-week rows ----
    weeks = []
    for w in weekly:
        subs = by_week[w["sunday"]]
        expected = [n for n in core if n in first and first[n] <= w["sunday"]]
        weeks.append({
            "sunday": w["sunday"],
            "submitted": sorted(n for n in subs if n in core_set),
            "missed": sorted(n for n in expected if n not in subs),
            "other": sorted(n for n in subs if n not in core_set),
            "n": w.get("n", len(subs)),
            "expected": len(expected),
        })

    # ---- per-person rollups ----
    people = []
    for full in core:
        f = first.get(full)
        graded = [w for w in weeks if f and w["sunday"] >= f]
        hits = [w for w in graded if full in w["submitted"]]
        # current streak (consecutive most-recent graded weeks submitted)
        streak = 0
        for w in reversed(graded):
            if full in w["submitted"]:
                streak += 1
            else:
                break
        # longest streak, and longest gap
        best = cur = gap = worst_gap = 0
        for w in graded:
            if full in w["submitted"]:
                cur += 1
                best = max(best, cur)
                gap = 0
            else:
                cur = 0
                gap += 1
                worst_gap = max(worst_gap, gap)
        last12 = graded[-12:]
        people.append({
            "name": full,
            "short": short[full],
            "first": f,
            "last": hits[-1]["sunday"] if hits else None,
            "submitted": len(hits),
            "graded": len(graded),
            "rate": round(100 * len(hits) / len(graded)) if graded else None,
            "rate12": round(100 * sum(1 for w in last12 if full in w["submitted"]) / len(last12)) if last12 else None,
            "streak": streak,
            "best_streak": best,
            "longest_gap": worst_gap,
            "no_record": f is None,
        })

    # sort: on-record people by 12-week rate desc, then no-record at the bottom
    people.sort(key=lambda p: (p["no_record"], -(p["rate12"] or 0), -(p["rate"] or 0)))

    non_core = collections.Counter()
    for w in weeks:
        non_core.update(w["other"])

    return {
        "roster": [f for f, _ in ROSTER],
        "people": people,
        "weeks": weeks,
        "non_core": [{"name": n, "count": c} for n, c in non_core.most_common()],
        "non_core_note": NON_CORE_NOTE,
        "first_sunday": sundays[0] if sundays else None,
        "last_sunday": sundays[-1] if sundays else None,
        "form_url": "https://forms.gle/GStKrGK4PLmn1U6M9",
    }


if __name__ == "__main__":
    d = json.load(open(ROOT / "data" / "debrief.json"))
    p = build(d)
    print(f"{len(p['weeks'])} Sundays  {p['first_sunday']} -> {p['last_sunday']}\n")
    print(f"{'name':16}{'12wk':>6}{'all':>6}{'sub/graded':>12}{'streak':>8}{'best':>6}{'gap':>5}  last")
    for r in p["people"]:
        if r["no_record"]:
            print(f"{r['short']:16}{'—':>6}{'—':>6}{'no responses on record':>12}")
            continue
        ratio = "{}/{}".format(r["submitted"], r["graded"])
        print(f"{r['short']:16}{str(r['rate12'])+'%':>6}{str(r['rate'])+'%':>6}"
              f"{ratio:>12}{r['streak']:>8}{r['best_streak']:>6}"
              f"{r['longest_gap']:>5}  {r['last']}")
    if p["non_core"]:
        print("\nnon-core respondents:", ", ".join(f"{x['name']} ({x['count']})" for x in p["non_core"]))
