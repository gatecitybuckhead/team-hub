#!/usr/bin/env python3
"""Encrypt built dashboards with a shared team password (AES-256-GCM, PBKDF2).
The published file is safe to host publicly: without the password the payload
is unreadable. Usage: python3 encrypt.py <password>
Reads build/*.html -> writes site/staff/*.html
"""
import sys, os, json, base64, hashlib, pathlib

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError:
    sys.exit("pip install cryptography --break-system-packages")

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC, DST = ROOT/'build', ROOT/'docs'/'staff'
DST.mkdir(parents=True, exist_ok=True)

if len(sys.argv) < 2: sys.exit('usage: encrypt.py <team password>')
password = sys.argv[1]
ITER = 200_000

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
.err{{color:#e06767;font-size:13px;height:18px;margin-top:9px}}</style></head>
<body><div class="box"><h1>GateCity Buckhead — <b>{title}</b></h1>
<p>Team access only. Enter the shared team password.</p>
<input id="pw" type="password" placeholder="Team password" autofocus>
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
  try{{const html=await unlock(pw);sessionStorage.setItem('gcbpw',pw);
    document.open();document.write(html);document.close();}}
  catch(e){{document.getElementById('err').textContent='Wrong password — try again.';}}}}
document.getElementById('go').onclick=go;
document.getElementById('pw').addEventListener('keydown',e=>{{if(e.key==='Enter')go()}});
const saved=sessionStorage.getItem('gcbpw');
if(saved)unlock(saved).then(h=>{{document.open();document.write(h);document.close()}}).catch(()=>{{}});
</script></body></html>'''

for f in sorted(SRC.glob('*.html')):
    plain = f.read_bytes()
    salt, iv = os.urandom(16), os.urandom(12)
    key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, ITER, 32)
    ct = AESGCM(key).encrypt(iv, plain, None)
    title = 'Metrics' if 'metrics' in f.name else 'Sunday Debrief'
    out = SHELL.format(title=title, salt=base64.b64encode(salt).decode(),
                       iv=base64.b64encode(iv).decode(), ct=base64.b64encode(ct).decode(), iter=ITER)
    (DST/f.name).write_text(out)
    print('encrypted ->', f'docs/staff/{f.name}', f'{(DST/f.name).stat().st_size//1024}KB')
