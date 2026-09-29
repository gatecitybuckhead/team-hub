#!/usr/bin/env python3
"""Encrypt built dashboards with TIERED passwords (AES-256-GCM, PBKDF2).
The published files are safe to host publicly: without the password the payload
is unreadable.

TWO TIERS since 2026-08-18 (replaced per-page passwords):
  staff      — ONE password unlocks every staff dashboard (debrief, metrics,
               members, finance). All staff shells share sessionStorage key
               'gcbstaff', so entering the password on any page unlocks the
               rest of them in that tab.
  leadership — a SECOND password (Andrew + Hazen only) for leadership.html
               (payroll, runway, giving TOTALS). Separate ciphertext, separate
               session key 'gcbleader', no fallback to the staff key — the
               staff password mathematically cannot open it.

Passwords live OUTSIDE every repo in gcb-staff-passwords.json at the AI Ops
root: {"staff": "...", "leadership": "..."}

Only the pages listed in PAGES below are ever encrypted and published — this is
an explicit allowlist, NOT a glob, so stray files in build/ (funday-admin,
QR sheets, ...) can never leak onto the staff site (lesson of 2026-07-28).

HARD RULES since the 9/29/2026 donor audit (the repo is PUBLIC, so every
ciphertext it ever held can be downloaded and guessed offline forever):
  - per-person giving is NEVER encrypted into docs/ — it lives only on the
    Mini (gcb-leadership.html). The plaintext guard below refuses any page
    carrying per-person giving keys, whatever build step produced it.
  - PBKDF2 >= 600,000 iterations; leadership password >= 20 characters.

Usage: python3 encrypt.py            (reads the JSON above)
       python3 encrypt.py <pw>       (legacy: one password for every STAFF page;
                                      refuses to run if a leadership page is built)
"""
import sys, os, json, base64, hashlib, pathlib

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError:
    sys.exit("pip install cryptography --break-system-packages")

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC, DST = ROOT/'build', ROOT/'docs'/'staff'
DST.mkdir(parents=True, exist_ok=True)

# page filename -> (display title, tier). ONLY these are published.
PAGES = {
    'debrief.html':    ('Sunday Debrief', 'staff'),
    'metrics.html':    ('Metrics',        'staff'),
    'members.html':    ('Members',        'staff'),
    'finance.html':    ('Finance',        'staff'),
    'leadership.html': ('Leadership',     'leadership'),
    'budget.html':     ('Budget',         'leadership'),   # Finance Agent budget page (9/28)
}
SKEY = {'staff': 'gcbstaff', 'leadership': 'gcbleader'}

PW_FILE = ROOT.parent.parent / 'gcb-staff-passwords.json'
if len(sys.argv) > 1:
    if (SRC/'leadership.html').exists():
        sys.exit('legacy one-password mode refuses to run while build/leadership.html '
                 'exists — it would put the leadership page behind the staff password. '
                 f'Use {PW_FILE} instead.')
    passwords = {'staff': sys.argv[1]}
elif PW_FILE.exists():
    passwords = json.loads(PW_FILE.read_text())
    tiers_needed = {tier for name, (_, tier) in PAGES.items() if (SRC/name).exists()}
    missing = [t for t in tiers_needed if not passwords.get(t)]
    if missing:
        sys.exit(f'{PW_FILE} is missing a password for tier(s): {", ".join(missing)} '
                 '(expected shape: {"staff": "...", "leadership": "..."})')
else:
    sys.exit(f'no password source: create {PW_FILE} or pass one password as an argument')

ITER = 600_000                   # OWASP 2023 floor for PBKDF2-SHA256
MIN_ITER = 600_000
MIN_PW = {'leadership': 20}      # staff pw stays as-is (8/18); no per-person giving there
if ITER < MIN_ITER:
    sys.exit(f'ITER {ITER} is below the {MIN_ITER} floor — refusing to encrypt.')
for tier, n in MIN_PW.items():
    if tier in passwords and len(passwords[tier]) < n:
        sys.exit(f'the {tier} password is shorter than {n} characters — refusing to '
                 f'encrypt. Rotate it in {PW_FILE}.')

# Second line of defence behind build.py's GIVING GUARD: JSON keys that only
# per-person giving rows carry. Templates reference these names in JS as
# r.last_gift / 'last_gift', never as "last_gift": — so a hit means DATA.
import re
PERSON_GIVING_RE = re.compile(rb'"(total_cents|giver_status|first_gift|last_gift|gift_count|'
                              rb'months_given|household_status|household_last_gift|'
                              rb'household_via|serving_not_giving|giving_not_serving)"\s*:')

SHELL = '''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>GCB Team Hub — {title}</title>
<style>body{{background:#0f1117;color:#e8eaf2;font:16px -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
display:flex;align-items:center;justify-content:center;min-height:96vh;margin:0}}
.box{{background:#181b24;border:1px solid #272c3a;border-radius:14px;padding:36px;max-width:360px;width:90%;text-align:center}}
h1{{font-size:19px;margin:0 0 4px}} h1 b{{color:#e0b34c}} p{{color:#8a90a5;font-size:13.5px;margin:6px 0 18px}}
input{{width:100%;box-sizing:border-box;background:#0f1117;border:1px solid #272c3a;color:#e8eaf2;border-radius:9px;padding:11px 13px;font-size:16px}}
button{{width:100%;margin-top:12px;background:#e0b34c;border:0;color:#161616;font-weight:700;border-radius:9px;padding:11px;font-size:15px;cursor:pointer}}
.err{{color:#e06767;font-size:13px;height:18px;margin-top:9px}}
#user{{margin-bottom:8px;color:#8a90a5}}</style></head>
<body><div class="box"><h1>GateCity Buckhead — <b>{title}</b></h1>
<p>{gate_copy}</p>
<form id="lf" autocomplete="on">
<input id="user" name="username" type="text" autocomplete="username" value="{user}">
<input id="pw" name="password" type="password" placeholder="{pw_label}" autocomplete="current-password" autofocus>
<button id="go" type="submit">Open dashboard</button>
</form><div class="err" id="err"></div></div>
<script>
const SALT="{salt}",IV="{iv}",CT="{ct}",ITER={iter},SKEY="{skey}";
const b64=s=>Uint8Array.from(atob(s),c=>c.charCodeAt(0));
async function unlock(pw){{
  const km=await crypto.subtle.importKey('raw',new TextEncoder().encode(pw),'PBKDF2',false,['deriveKey']);
  const key=await crypto.subtle.deriveKey({{name:'PBKDF2',salt:b64(SALT),iterations:ITER,hash:'SHA-256'}},km,{{name:'AES-GCM',length:256}},false,['decrypt']);
  const pt=await crypto.subtle.decrypt({{name:'AES-GCM',iv:b64(IV)}},key,b64(CT));
  return new TextDecoder().decode(pt);}}
async function go(){{
  const pw=document.getElementById('pw').value;
  try{{const html=await unlock(pw);sessionStorage.setItem(SKEY,pw);
    document.open();document.write(html);document.close();}}
  catch(e){{document.getElementById('err').textContent='Wrong password — try again.';}}}}
document.getElementById('lf').addEventListener('submit',e=>{{e.preventDefault();go();}});
const saved=sessionStorage.getItem(SKEY);
if(saved)unlock(saved).then(h=>{{document.open();document.write(h);document.close()}}).catch(()=>{{}});
</script></body></html>'''

GATE_COPY = {
    'staff': 'Team access only. Sign in as <b>staff</b> with the team password '
             '— one password opens every staff dashboard.',
    'leadership': 'Leadership access only. Sign in as <b>leadership</b> with the '
                  'leadership password.',
}
PW_LABEL = {'staff': 'team password', 'leadership': 'leadership password'}

for name, (title, tier) in PAGES.items():
    f = SRC/name
    if not f.exists():
        print(f'skip (no build): build/{name}')
        continue
    plain = f.read_bytes()
    hits = sorted({m.decode() for m in PERSON_GIVING_RE.findall(plain)})
    if hits:
        sys.exit(f'GIVING GUARD: build/{name} carries per-person giving {hits} — refusing '
                 'to encrypt it into the public repo. Names belong on the Mini only.')
    salt, iv = os.urandom(16), os.urandom(12)
    key = hashlib.pbkdf2_hmac('sha256', passwords[tier].encode(), salt, ITER, 32)
    ct = AESGCM(key).encrypt(iv, plain, None)
    out = SHELL.format(title=title, user=tier if tier == 'leadership' else 'staff',
                       gate_copy=GATE_COPY[tier], pw_label=PW_LABEL[tier],
                       salt=base64.b64encode(salt).decode(),
                       iv=base64.b64encode(iv).decode(), ct=base64.b64encode(ct).decode(),
                       iter=ITER, skey=SKEY[tier])
    (DST/name).write_text(out)
    print('encrypted ->', f'docs/staff/{name}', f'{(DST/name).stat().st_size//1024}KB', f'[{tier}]')
