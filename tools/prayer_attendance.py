#!/usr/bin/env python3
"""Capture virtual-prayer-call attendance from Zoom into the members data.

Reads the standing prayer-call meeting IDs from data/members/prayer-call-config.json,
pulls each meeting's participant report for the last 7 days, matches display
names to PCO person_ids via data/members/zoom-aliases.json (+ members-latest
name matching), and appends to data/members/prayer-attendance.json (idempotent
by meeting uuid). Unmatched names are kept and surfaced, never dropped.

Zoom retention for the reports API is ~30 days — run weekly, the past is gone.
Uses the zoom-archive S2S credentials (~/.config/zoom-archive/config.json).
NOTE: the S2S app currently LACKS the report scope — add "Report" scopes to
the app at marketplace.zoom.us (Andrew, one-time) or this script exits with
the exact error. Does NOT touch recordings and never deletes anything.

Usage: python3 tools/prayer_attendance.py [--days 7]
"""
import base64
import datetime
import json
import os
import re
import sys
import urllib.parse
import urllib.request

HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEMBERS = os.path.join(HUB, "data", "members")
CONFIG = os.path.join(MEMBERS, "prayer-call-config.json")
ALIASES = os.path.join(MEMBERS, "zoom-aliases.json")
OUT = os.path.join(MEMBERS, "prayer-attendance.json")
ZCFG = os.path.expanduser("~/.config/zoom-archive/config.json")


def zoom_token():
    cfg = json.load(open(ZCFG))["zoom"]
    basic = base64.b64encode(
        f"{cfg['client_id']}:{cfg['client_secret']}".encode()).decode()
    req = urllib.request.Request(
        "https://zoom.us/oauth/token",
        data=urllib.parse.urlencode({"grant_type": "account_credentials",
                                     "account_id": cfg["account_id"]}).encode(),
        headers={"Authorization": "Basic " + basic})
    return json.load(urllib.request.urlopen(req))["access_token"]


def zget(token, path, **params):
    url = f"https://api.zoom.us/v2{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode())


def norm(name):
    n = re.sub(r"[’']s? (iphone|ipad|phone|galaxy.*|android)$", "", name.strip().lower())
    n = re.sub(r"[^a-z ]", "", n)
    return re.sub(r"\s+", " ", n).strip()


def match_person(zoom_name, aliases, members):
    key = norm(zoom_name)
    if key in aliases:
        return aliases[key]  # may be a person_id or null (= ignore device)
    exact = [m for m in members if norm(m["name"] or "") == key]
    if len(exact) == 1:
        return exact[0]["person_id"]
    first = key.split(" ")[0] if key else ""
    firsts = [m for m in members if (m["name"] or "").lower().startswith(first + " ")] if first else []
    if len(firsts) == 1 and len(first) >= 3:
        return firsts[0]["person_id"]
    return None


def main():
    days = 7
    if "--days" in sys.argv:
        days = int(sys.argv[sys.argv.index("--days") + 1])
    if not os.path.exists(CONFIG):
        sys.exit(f"No {CONFIG} — create it with the standing prayer-call meeting id(s): "
                 '{"meeting_ids": ["1234567890"]}')
    cfg = json.load(open(CONFIG))
    aliases = json.load(open(ALIASES)) if os.path.exists(ALIASES) else {}
    members = json.load(open(os.path.join(MEMBERS, "members-latest.json")))["people"]

    data = {"calls": [], "unmatched": []}
    if os.path.exists(OUT):
        data = json.load(open(OUT))
    seen_uuids = {c["uuid"] for c in data["calls"]}

    token = zoom_token()
    cutoff = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    added = 0
    for mid in cfg.get("meeting_ids", []):
        try:
            # every occurrence of the recurring meeting in the window
            insts = zget(token, f"/past_meetings/{mid}/instances").get("meetings", [])
        except urllib.error.HTTPError as e:
            sys.exit(f"Zoom API {e.code} on past_meetings/{mid}/instances — "
                     "if 4700/missing scope, add the Report scopes to the S2S app "
                     "at marketplace.zoom.us (one-time).")
        for inst in insts:
            uuid, start = inst.get("uuid"), (inst.get("start_time") or "")[:10]
            if not uuid or start < cutoff or uuid in seen_uuids:
                continue
            # double-encode uuid per Zoom docs when it contains / or //
            enc = urllib.parse.quote(urllib.parse.quote(uuid, safe=""), safe="")
            rep = zget(token, f"/report/meetings/{enc}/participants", page_size=300)
            parts, blob = {}, rep.get("participants", [])
            for p in blob:
                nm = p.get("name") or "?"
                pid = match_person(nm, aliases, members)
                if pid is None and norm(nm) not in aliases:
                    u = next((x for x in data["unmatched"] if x["zoom_name"] == nm), None)
                    if u:
                        u["dates"] = sorted(set(u["dates"] + [start]))
                    else:
                        data["unmatched"].append({"zoom_name": nm, "dates": [start]})
                mins = round((p.get("duration") or 0) / 60)
                cur = parts.get(nm)
                if not cur or mins > cur["minutes"]:
                    parts[nm] = {"zoom_name": nm, "person_id": pid, "minutes": mins}
            data["calls"].append({"uuid": uuid, "date": start,
                                  "meeting_id": str(mid),
                                  "topic": inst.get("topic") or cfg.get("label", "Prayer call"),
                                  "participants": list(parts.values())})
            seen_uuids.add(uuid)
            added += 1
    data["calls"].sort(key=lambda c: c["date"])
    data["generated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    json.dump(data, open(OUT, "w"))
    print(f"prayer-attendance: +{added} call(s), {len(data['calls'])} total, "
          f"{len(data['unmatched'])} unmatched names")


if __name__ == "__main__":
    main()
