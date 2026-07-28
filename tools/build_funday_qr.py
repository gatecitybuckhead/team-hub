#!/usr/bin/env python3
"""Family Fun Day — printable station QR sheets.

Reads the STATIONS block out of docs/funday/funday-config.js (single source
of truth — same list the pages use) and writes ONE printable HTML file with
a page per station: big station name, its QR (-> score.html?st=<slug>), and
one-line volunteer instructions. Also a final page with the leaderboard QR.

Output: build/funday-qr-sheets.html  (build/ is gitignored; this is print-only)
Print: open in a browser -> Cmd+P (each station lands on its own page).

Re-run any time you edit the stations list:  python3 tools/build_funday_qr.py
"""
import json, re, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import qr  # vendored, dependency-free

ROOT = pathlib.Path(__file__).resolve().parent.parent
CFG  = ROOT / 'docs' / 'funday' / 'funday-config.js'
OUT  = ROOT / 'build' / 'funday-qr-sheets.html'
BASE = 'https://gatecitybuckhead.github.io/team-hub/funday'

src = CFG.read_text(encoding='utf-8')
m = re.search(r'/\*STATIONS_START\*/(.*?)/\*STATIONS_END\*/', src, re.S)
if not m:
    sys.exit('Could not find /*STATIONS_START*/ ... /*STATIONS_END*/ in funday-config.js')
stations = json.loads(m.group(1))

def sheet(title, emoji, url, note):
    if len(url.encode()) > 100:
        sys.exit(f'URL too long for vendored qr.py (>100 bytes): {url}\nUse a shorter station slug.')
    svg = qr.qr_svg(url, box=10, border=4)
    return f'''<section class="sheet">
  <div class="ev">GATECITY BUCKHEAD · FAMILY FUN DAY</div>
  <div class="emoji">{emoji}</div>
  <h1>{title}</h1>
  <div class="qr">{svg}</div>
  <p class="note">{note}</p>
  <p class="url">{url}</p>
</section>'''

pages = []
for s in stations:
    url = f"{BASE}/score.html?st={s['slug']}"
    pages.append(sheet(s['name'], s.get('emoji',''), url,
        'VOLUNTEERS: scan with your phone camera → pick the player → tap their points. '
        'Mis-tap? Use Undo in “Recent at this station.”'))

pages.append(sheet('Live Leaderboard', '🏆', f'{BASE}/board.html',
    'Open this on the projector computer (or your phone) to watch the standings live.'))

html = f'''<!DOCTYPE html><html><head><meta charset="utf-8"><title>Fun Day QR Sheets</title>
<link href="https://fonts.googleapis.com/css2?family=Rye&family=Fredoka:wght@500;700&display=swap" rel="stylesheet">
<style>
  body{{font-family:'Fredoka',sans-serif;margin:0;background:#eee}}
  .sheet{{width:8.5in;height:10.9in;margin:12px auto;background:#f9edbe;display:flex;flex-direction:column;
    align-items:center;justify-content:center;gap:.25in;page-break-after:always;
    border:14px solid #c8102e;outline:4px dashed #c8102e;outline-offset:-32px;text-align:center;padding:.5in;box-sizing:border-box}}
  .ev{{font-weight:700;letter-spacing:4px;color:#8a6d1a;font-size:16pt}}
  .emoji{{font-size:60pt;line-height:1}}
  h1{{font-family:'Rye',serif;color:#c8102e;font-size:44pt;margin:0;line-height:1.05}}
  .qr svg{{width:4.2in;height:4.2in;border:6px solid #fff;border-radius:12px;background:#fff}}
  .note{{font-size:14pt;font-weight:500;color:#5a1010;max-width:6.5in;margin:0}}
  .url{{font-size:9pt;color:#8a6d1a;margin:0}}
  @media print{{body{{background:#fff}} .sheet{{margin:0}}}}
</style></head><body>
{''.join(pages)}
</body></html>'''

OUT.parent.mkdir(exist_ok=True)
OUT.write_text(html, encoding='utf-8')
print(f'Wrote {OUT.relative_to(ROOT)}  ({len(stations)} stations + leaderboard page)')
print('Open it and print (Cmd+P) — one page per station.')
