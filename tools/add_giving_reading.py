#!/usr/bin/env python3
"""Append one "% of members giving" reading from Planning Center.

WHY THIS EXISTS AS A SCRIPT THAT TAKES NUMBERS
Planning Center is only reachable through the MCP connector, which the agent can
call but a plain script cannot (no PCO credentials live in this repo — see
SECRETS-INVENTORY.md). So the agent reads the two list counts and pipes them in
here, exactly like tools/add_metrics_week.py does for the metrics sheet. The
data file is the durable part; the agent is just the transport.

WHY IT ONLY EVER APPENDS
The PCO lists are a ROLLING 90-DAY WINDOW. They answer "how many members have
given in the last 90 days, as of right now" and carry no history — you cannot
ask them what the figure was in March. So each weekly run captures one reading
and the series is built up over time. Never backfill these; a reading taken
today is not evidence about any earlier Sunday.

Weekly usage (agent pulls the counts, then):
    python3 tools/add_giving_reading.py --giving 54 --members 91 \
        [--sunday 2026-07-26] [--refreshed 2026-07-28T06:17:24Z]

Re-running for the same Sunday overwrites that reading rather than duplicating.
"""
import argparse, datetime, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'giving_participation.json'

# The PCO People lists this metric is defined against. If these are ever
# re-pointed, change them HERE and note it in CLAUDE.md — the readings already
# recorded were measured against the old definition.
LISTS = {
    'numerator':   {'id': '5145818', 'name': 'Members Giving (Last 90 Days)'},
    'denominator': {'id': '4019918', 'name': 'Members (All)'},
}
WINDOW = 'rolling 90 days'


def last_sunday(d=None):
    d = d or datetime.date.today()
    return (d - datetime.timedelta(days=(d.weekday() + 1) % 7)).isoformat()


def load():
    if OUT.exists():
        return json.load(open(OUT))
    return {'source': 'Planning Center People lists', 'lists': LISTS,
            'window': WINDOW, 'readings': []}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--giving', type=int, required=True,
                    help="people_count of '%s'" % LISTS['numerator']['name'])
    ap.add_argument('--members', type=int, required=True,
                    help="people_count of '%s'" % LISTS['denominator']['name'])
    ap.add_argument('--sunday', help='Sunday this reading is filed under (default: most recent)')
    ap.add_argument('--refreshed', help="PCO list refreshed_at timestamp, for provenance")
    a = ap.parse_args()

    if a.members <= 0:
        sys.exit('members must be > 0')
    if a.giving > a.members:
        sys.exit(f'giving ({a.giving}) > members ({a.members}) — check which list is which')

    sunday = a.sunday or last_sunday()
    data = load()
    data['lists'], data['window'] = LISTS, WINDOW
    reading = {
        'sunday': sunday,
        'pulled': datetime.date.today().isoformat(),
        'giving': a.giving,
        'members': a.members,
        'pct': round(100 * a.giving / a.members, 1),
        'list_refreshed': a.refreshed,
    }
    rs = [r for r in data['readings'] if r['sunday'] != sunday]
    replaced = len(rs) != len(data['readings'])
    rs.append(reading)
    data['readings'] = sorted(rs, key=lambda r: r['sunday'])
    OUT.parent.mkdir(exist_ok=True)
    json.dump(data, open(OUT, 'w'), indent=1)

    print(f"{'replaced' if replaced else 'added'} reading for Sunday {sunday}: "
          f"{reading['giving']}/{reading['members']} = {reading['pct']}%")
    print(f"{len(data['readings'])} reading(s) on file "
          f"({data['readings'][0]['sunday']} → {data['readings'][-1]['sunday']})")


if __name__ == '__main__':
    main()
