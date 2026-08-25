#!/usr/bin/env python3
"""Build the GCB Team Hub Production page (password-gated + QR).

Pipeline:
  1. Read data/production.json  (roster, service timeline, page_url).
  2. Read the pre-service checklist from its single source of truth,
     data['checklist_source'] (the Sunday Checklist Dashboard's checklist.json),
     so the LAN check-off dashboard and this page never drift.
  3. Generate an offline QR of page_url (tools/qr.py, dependency-free).
  4. Inject everything into templates/production.template.html (plaintext).
  5. Encrypt the plaintext with the PRODUCTION password (AES-256-GCM, PBKDF2)
     and wrap it in a password gate that also shows the QR. Write
     docs/production.html (safe to host publicly — no password in the file).

Usage:  python3 tools/build_production.py "<production password>"
The password is NOT stored here; pass it in. See root SECRETS-INVENTORY.md.
"""
import sys, os, re, json, base64, hashlib, datetime, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import qr  # vendored, dependency-free QR generator

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError:
    sys.exit("pip install cryptography --break-system-packages")

if len(sys.argv) < 2:
    sys.exit('usage: build_production.py "<production password>"')
password = sys.argv[1]
ITER = 200_000

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / 'data' / 'production.json'
TPL  = ROOT / 'templates' / 'production.template.html'
OUT  = ROOT / 'docs' / 'production.html'

payload = json.load(open(DATA, encoding='utf-8'))
built = payload.get('built') or datetime.date.today().isoformat()

# ---- checklist from its single source of truth ----
# Keep {id,text} per item so the page's tap-to-check state is stable across
# text edits, and carry the `teardown` flag so teardown renders as its own list.
src = (ROOT / payload['checklist_source']).resolve()
raw = json.load(open(src, encoding='utf-8'))
payload['checklist'] = {
    'title': raw.get('title', ''),
    'sections': [
        {'name': s['name'],
         'critical': bool(s.get('critical')),
         'teardown': bool(s.get('teardown')),
         'items': [{'id': it['id'], 'text': it['text']} for it in s.get('items', [])]}
        for s in raw.get('sections', [])
    ],
}

# ---- Firebase web config: single source is docs/funday/funday-config.js ----
# Regexed out at build time (same trick build_funday_qr.py uses for stations)
# so the config is never duplicated. If it's null/missing, the page falls back
# to device-only checklist mode.
FBCFG_SRC = ROOT / 'docs' / 'funday' / 'funday-config.js'
fb_config = None
try:
    m = re.search(r'firebaseConfig:\s*\{(.*?)\}', FBCFG_SRC.read_text(encoding='utf-8'), re.S)
    if m:
        fields = dict(re.findall(r'(\w+)\s*:\s*"([^"]*)"', m.group(1)))
        if fields.get('apiKey') and fields.get('databaseURL'):
            fb_config = fields
except FileNotFoundError:
    pass
if fb_config is None:
    print('WARNING: no Firebase config found in', FBCFG_SRC.name, '— building device-only checklist')

# ---- QR of the public page URL ----
qr_svg = qr.qr_svg(payload.get('page_url', ''), box=6, border=3) if payload.get('page_url') else ''

# ---- build plaintext dashboard ----
html = open(TPL, encoding='utf-8').read()
html = html.replace('/*__DATA__*/null', json.dumps(payload, separators=(',', ':')))
html = html.replace('/*__FBCONFIG__*/null',
                    json.dumps(fb_config, separators=(',', ':')) if fb_config else 'null')
html = html.replace('<!--__QR__-->', qr_svg)
html = html.replace('<!--__REFRESH__-->', (ROOT/'templates'/'refresh-pill.html').read_text())
html = html.replace('__BUILT_AT__',
                    datetime.datetime.now().astimezone().isoformat(timespec='seconds'))
html = html.replace('__BUILT__', built)

# ---- encrypt ----
salt, iv = os.urandom(16), os.urandom(12)
key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, ITER, 32)
ct = AESGCM(key).encrypt(iv, html.encode('utf-8'), None)

GATE = '''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>GCB Production</title>
<style>body{{background:#0f1117;color:#e8eaf2;font:16px -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
display:flex;align-items:center;justify-content:center;min-height:96vh;margin:0}}
.box{{background:#181b24;border:1px solid #272c3a;border-radius:14px;padding:30px;max-width:340px;width:90%;text-align:center}}
h1{{font-size:19px;margin:0 0 4px}} h1 b{{color:#e0b34c}} p{{color:#8a90a5;font-size:13.5px;margin:6px 0 16px}}
.qrbox{{background:#fff;border-radius:10px;padding:9px;display:inline-block;margin:4px 0 14px}}
.qrbox svg{{display:block;width:170px;height:170px}}
input{{width:100%;box-sizing:border-box;background:#0f1117;border:1px solid #272c3a;color:#e8eaf2;border-radius:9px;padding:11px 13px;font-size:16px}}
button{{width:100%;margin-top:12px;background:#e0b34c;border:0;color:#161616;font-weight:700;border-radius:9px;padding:11px;font-size:15px;cursor:pointer}}
.err{{color:#e06767;font-size:13px;height:18px;margin-top:9px}}</style></head>
<body><div class="box"><h1>GateCity Buckhead — <b>Production</b></h1>
<div class="qrbox">{qr}</div>
<p>Scan to open on your phone, then enter the production team password.</p>
<input id="pw" type="password" placeholder="Production password" autofocus>
<button id="go">Open dashboard</button><div class="err" id="err"></div></div>
<script>
const SALT="{salt}",IV="{iv}",CT="{ct}",ITER={iter};
const b64=s=>Uint8Array.from(atob(s),c=>c.charCodeAt(0));
async function unlock(pw){{
  const km=await crypto.subtle.importKey('raw',new TextEncoder().encode(pw),'PBKDF2',false,['deriveKey']);
  const key=await crypto.subtle.deriveKey({{name:'PBKDF2',salt:b64(SALT),iterations:ITER,hash:'SHA-256'}},km,{{name:'AES-GCM',length:256}},false,['decrypt']);
  const pt=await crypto.subtle.decrypt({{name:'AES-GCM',iv:b64(IV)}},key,b64(CT));
  return new TextDecoder().decode(pt);}}
async function go(){{
  const pw=document.getElementById('pw').value;
  try{{const html=await unlock(pw);sessionStorage.setItem('gcbprod',pw);
    document.open();document.write(html);document.close();}}
  catch(e){{document.getElementById('err').textContent='Wrong password — try again.';}}}}
document.getElementById('go').onclick=go;
document.getElementById('pw').addEventListener('keydown',e=>{{if(e.key==='Enter')go()}});
const saved=sessionStorage.getItem('gcbprod');
if(saved)unlock(saved).then(h=>{{document.open();document.write(h);document.close()}}).catch(()=>{{}});
</script></body></html>'''

out = GATE.format(qr=qr_svg, salt=base64.b64encode(salt).decode(),
                  iv=base64.b64encode(iv).decode(), ct=base64.b64encode(ct).decode(), iter=ITER)
OUT.write_text(out, encoding='utf-8')
print('built', OUT.relative_to(ROOT), f'{OUT.stat().st_size // 1024}KB (encrypted, gated + QR)')
