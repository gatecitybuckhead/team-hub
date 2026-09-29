#!/usr/bin/env python3
"""Append one Sunday's person-level reading of the PCO list
"Members Giving (Last 90 Days)" (id 5145818). LEADERSHIP-tier data.

Like add_giving_reading.py this is APPEND-ONLY and can never be backfilled —
the list answers "as of right now". Re-running for the same Sunday replaces
that reading. Person ids arrive on stdin, one per line (the agent pipes them
from pco_get_list_people), so hundreds of ids never enter the agent's context
as names.

Usage: pco ids | python3 tools/add_giving_membership.py --sunday 2026-08-23
Writes: data/members/giving-90day-membership.json (gitignored)
"""
import datetime
import json
import os
import sys

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HUB, "data", "members", "giving-90day-membership.json")


def main():
    if "--sunday" not in sys.argv:
        sys.exit("usage: ids-on-stdin | add_giving_membership.py --sunday YYYY-MM-DD")
    sunday = sys.argv[sys.argv.index("--sunday") + 1]
    datetime.date.fromisoformat(sunday)  # validate
    ids = sorted({line.strip() for line in sys.stdin if line.strip()})
    if not ids:
        sys.exit("no person ids on stdin — refusing to record an empty reading")

    data = {"_note": "Weekly person-level capture of PCO list 5145818 "
                     "(Members Giving, rolling 90 days). Append-only; a missed "
                     "week is unrecoverable. LEADERSHIP-tier data.",
            "readings": []}
    if os.path.exists(OUT):
        data = json.load(open(OUT))
    data["readings"] = [r for r in data["readings"] if r["sunday"] != sunday]
    data["readings"].append({"sunday": sunday, "count": len(ids),
                             "person_ids": ids,
                             "recorded_at": datetime.datetime.now(
                                 datetime.timezone.utc).isoformat()})
    data["readings"].sort(key=lambda r: r["sunday"])
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(data, open(OUT, "w"), indent=1)
    print(f"recorded {len(ids)} giving-list members for {sunday} "
          f"({len(data['readings'])} readings on file)")


if __name__ == "__main__":
    main()
