#!/usr/bin/env python3
"""Family Fun Day — local admin page (preload roster + wipe test data).

Reads full names from data/funday_roster_names.json (gitignored) and converts
them to public-safe display names: "First L." — the leaderboard is a public,
unencrypted page, so full last names never leave data/. Collisions get just
enough extra letters ("Hannah St." / "Hannah Sa."); identical first+last pairs
(David Rice vs David Joseph Rice) get a middle initial instead.

Output: build/funday-admin.html (gitignored, LOCAL ONLY — never publish).
Open it in a browser on the Mac and use the buttons:
  1. Preload roster  — adds every roster name to Firebase, skipping any name
     already in the players list (safe to re-run after adding registrations).
  2. Wipe all scores — deletes every score for the event (test cleanup).
  3. Wipe all players — deletes every player (then re-preload for a clean slate).

Firebase config + eventPath are regexed out of docs/funday/funday-config.js at
build time (single source of truth, same trick as build_production.py).

Re-run after editing the roster: python3 tools/build_funday_admin.py
"""
import json, re, pathlib, sys, unicodedata

ROOT  = pathlib.Path(__file__).resolve().parent.parent
CFG   = ROOT / 'docs' / 'funday' / 'funday-config.js'
NAMES = ROOT / 'data' / 'funday_roster_names.json'
OUT   = ROOT / 'build' / 'funday-admin.html'

# ---------- pull firebase config + eventPath out of funday-config.js ----------
src = CFG.read_text(encoding='utf-8')
m = re.search(r'firebaseConfig:\s*(\{.*?\})', src, re.S)
if not m or 'null' in m.group(1)[:12]:
    sys.exit('No firebaseConfig found in funday-config.js')
fb_config_js = m.group(1)
m = re.search(r'eventPath:\s*"([^"]+)"', src)
if not m:
    sys.exit('No eventPath found in funday-config.js')
event_path = m.group(1)

# ---------- load names ----------
data = json.loads(NAMES.read_text(encoding='utf-8'))
full_names, seen = [], set()
for group in (k for k in data if not k.startswith('_')):
    for n in data.get(group, []):
        key = re.sub(r'[^a-z ]', '', unicodedata.normalize('NFKD', n).lower()).strip()
        if key and key not in seen:
            seen.add(key)
            full_names.append(n.strip())

# ---------- display names: "First L." with minimal disambiguation ----------
def parts(full):
    nick = re.search(r'[""\"]([^""\"]+)[""\"]', full)
    clean = re.sub(r'[""\"][^""\"]+[""\"]\s*', '', full).strip()
    toks = clean.split()
    first = (nick.group(1) if nick else toks[0])
    last  = toks[-1] if len(toks) > 1 else ''
    mids  = toks[1:-1]
    if last and last[0].islower():
        last = last[0].upper() + last[1:]
    return [first, mids, last]

infos = [parts(n) for n in full_names]

# same first + same last -> middle initial up front (David Rice / David Joseph Rice)
by_fl = {}
for i, (f, m_, l) in enumerate(infos):
    by_fl.setdefault((f.lower(), l.lower()), []).append(i)
for g in by_fl.values():
    if len(g) > 1:
        for i in g:
            if infos[i][1]:
                infos[i][0] = infos[i][0] + ' ' + infos[i][1][0][0].upper() + '.'

plen = [1] * len(infos)
def disp(i):
    f, _, l = infos[i]
    if not l:
        return f
    p = l[:plen[i]]
    return f + ' ' + p + ('.' if len(p) < len(l) else '')

for _ in range(30):  # extend colliding groups one letter at a time
    groups = {}
    for i in range(len(infos)):
        groups.setdefault(disp(i), []).append(i)
    clash = [g for g in groups.values() if len(g) > 1]
    if not clash:
        break
    for g in clash:
        for i in g:
            if plen[i] < len(infos[i][2]):
                plen[i] += 1
else:
    sys.exit('Could not disambiguate display names — check the roster for exact duplicates.')

display = [disp(i) for i in range(len(infos))]
roster_pairs = sorted(zip(display, full_names), key=lambda p: p[0].lower())

# ---------- page ----------
roster_json = json.dumps([d for d, _ in roster_pairs], ensure_ascii=False)
rows = '\n'.join(f'<tr><td>{d}</td><td class="full">{f}</td></tr>' for d, f in roster_pairs)

html = f'''<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fun Day ADMIN — local only</title>
<style>
  body{{font-family:-apple-system,sans-serif;max-width:720px;margin:24px auto;padding:0 16px;color:#222}}
  h1{{color:#c8102e}} .warn{{background:#fff3cd;border:1px solid #e0c060;border-radius:8px;padding:10px 14px;font-size:14px}}
  button{{font-size:16px;font-weight:700;padding:12px 18px;border-radius:10px;border:none;cursor:pointer;margin:6px 8px 6px 0}}
  #preload{{background:#1d7a1d;color:#fff}} #wipeScores,#wipePlayers{{background:#c8102e;color:#fff}}
  #log{{white-space:pre-wrap;background:#f5f5f5;border-radius:8px;padding:12px;font-family:monospace;font-size:13px;min-height:80px}}
  table{{border-collapse:collapse;font-size:13px;margin-top:8px}} td{{border:1px solid #ddd;padding:3px 10px}}
  .full{{color:#888}} #conn{{font-weight:700}}
  details{{margin:14px 0}}
</style></head><body>
<h1>🎪 Fun Day Admin</h1>
<p class="warn">LOCAL FILE — do not publish or share. Event: <b>{event_path}</b> · <span id="conn">connecting…</span></p>
<p>
  <button id="preload">1 · Preload roster ({len(roster_pairs)} names)</button>
  <button id="wipeScores">Wipe ALL scores</button>
  <button id="wipePlayers">Wipe ALL players</button>
</p>
<div id="log">Ready.</div>
<details><summary>Roster preview ({len(roster_pairs)} — display name → full name, full names stay local)</summary>
<table>{rows}</table></details>
<script src="https://www.gstatic.com/firebasejs/10.12.2/firebase-app-compat.js"></script>
<script src="https://www.gstatic.com/firebasejs/10.12.2/firebase-database-compat.js"></script>
<script>
var ROSTER={roster_json};
firebase.initializeApp({fb_config_js});
var db=firebase.database(), base=db.ref("{event_path}");
db.ref(".info/connected").on("value",function(sn){{
  document.getElementById("conn").textContent=sn.val()?"✅ connected":"❌ offline";
}});
var logEl=document.getElementById("log");
function log(s){{ logEl.textContent+="\\n"+s; }}
function norm(s){{ return String(s).toLowerCase().replace(/[^a-z ]/g,"").replace(/\\s+/g," ").trim(); }}

document.getElementById("preload").onclick=function(){{
  base.child("players").once("value").then(function(sn){{
    var existing={{}}, cur=sn.val()||{{}};
    Object.keys(cur).forEach(function(pid){{ existing[norm(cur[pid].name||"")]=true; }});
    var add=ROSTER.filter(function(n){{ return !existing[norm(n)]; }});
    if(!add.length){{ log("Nothing to add — all "+ROSTER.length+" roster names already loaded."); return; }}
    if(!confirm("Add "+add.length+" players ("+(ROSTER.length-add.length)+" already there)?")) return;
    var done=0;
    add.forEach(function(n){{
      base.child("players").push({{name:n,ts:Date.now()}}).then(function(){{
        if(++done===add.length) log("✅ Preloaded "+done+" players ("+Object.keys(cur).length+" were already there).");
      }});
    }});
  }});
}};
function wipe(node,label){{
  base.child(node).once("value").then(function(sn){{
    var keys=Object.keys(sn.val()||{{}});
    if(!keys.length){{ log("No "+label+" to delete."); return; }}
    if(!confirm("Delete ALL "+keys.length+" "+label+" for {event_path}? This cannot be undone.")) return;
    var done=0;
    keys.forEach(function(k){{
      base.child(node).child(k).remove().then(function(){{
        if(++done===keys.length) log("🗑 Deleted "+done+" "+label+".");
      }});
    }});
  }});
}}
document.getElementById("wipeScores").onclick=function(){{ wipe("scores","scores"); }};
document.getElementById("wipePlayers").onclick=function(){{ wipe("players","players"); }};
</script></body></html>'''

OUT.parent.mkdir(exist_ok=True)
OUT.write_text(html, encoding='utf-8')
print(f'Wrote {OUT.relative_to(ROOT)}  ({len(roster_pairs)} roster names)')
disambiguated = [(d, f) for d, f in roster_pairs if not re.fullmatch(r'\S+ \w\.', d)]
if disambiguated:
    print('Disambiguated (needed extra letters/initials):')
    for d, f in disambiguated:
        print(f'  {d:<18} <- {f}')
