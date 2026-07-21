#!/usr/bin/env python3
"""Parse GCB 'DASHBOARD METRICS - 5 Behaviors' quarterly tabs into tidy JSON."""
import json, re, datetime
from openpyxl import load_workbook

SRC = '/sessions/dazzling-jolly-babbage/mnt/uploads/DASHBOARD METRICS - 5 Behaviors.xlsx'
OUT = '/sessions/dazzling-jolly-babbage/mnt/outputs/metrics.json'

TABS = [('Q1 2025',2025),('Q2 2025',2025),('Q3 2025',2025),('Q4 2025',2025),
        ('Q1 2026',2026),('Q2 2026',2026),('Q3 2026',2026)]

SECTIONS = {'SCORE','BOARD','PRAY','SERVE','GIVE','FORM','REACH','DIGITAL','GENERAL','Quarterly'}

def clean(v):
    if v is None: return None
    if isinstance(v,(int,float)): return round(float(v),2)
    s = str(v).strip()
    if s in ('','-','x','n/a','N/A','#DIV/0!','#REF!','#VALUE!','TBD','?'): return None
    s2 = s.replace('$','').replace(',','').replace('%%','%')
    m = re.fullmatch(r'(-?\d+(?:\.\d+)?)%', s2)
    if m: return round(float(m.group(1))/100,4)
    try: return round(float(s2),2)
    except ValueError: return None

def slug(s):
    return re.sub(r'[^a-z0-9]+','_',s.lower()).strip('_')

# label drift across years -> canonical keys
ALIASES = {
    'total_members': 'total_members_core_congregation',
    'attendance_in_garage': 'attendance_in_sanctuary',
    'vols_in_teams_sun_service': 'total_people_in_sunday_teams',
}
def canon(key):
    return ALIASES.get(key, key)

wb = load_workbook(SRC, data_only=True)
weeks = {}          # date -> {"date":..,"series":..,"special":..,"values":{}}
catalog = {}        # key -> {"label","section","owner"}

for tabname, year in TABS:
    ws = wb[tabname]
    # find header row: col A or B contains 'Data Set/Sunday'
    hdr = None
    for r in range(1,12):
        for c in (1,2):
            if 'Data Set/Sunday' in str(ws.cell(r,c).value or ''): hdr = r
        if hdr: break
    if not hdr:
        print('SKIP', tabname); continue
    series_row = None
    for rr in range(max(1,hdr-2), hdr):
        if 'Series' in str(ws.cell(rr,1).value or ''): series_row = rr
    special_row = hdr+1 if 'Special' in str(ws.cell(hdr+1,1).value or '') else None
    # map columns: sunday columns and their preceding data-set columns
    suncols = {}   # col -> date
    datacols = {}  # sunday col -> dataset col
    lastdata = None
    for c in range(2, ws.max_column+1):
        h = str(ws.cell(hdr,c).value or '').strip()
        if h.startswith('Data Set'):
            lastdata = c
        m = re.match(r'(?:Sunday\s+)?(\d{1,2})/(\d{1,2})\s*$', h)
        if m:
            mo,da = int(m.group(1)), int(m.group(2))
            y = year
            # Q1 tabs can reference a late-Dec Sunday of prior year
            if tabname.startswith('Q1') and mo==12: y = year-1
            try: d = datetime.date(y,mo,da)
            except ValueError: continue
            suncols[c] = d.isoformat()
            datacols[c] = lastdata
            lastdata = None
    # carry-forward series names across merged/blank cells
    for c,dt in sorted(suncols.items()):
        wk = weeks.setdefault(dt, {'date':dt,'series':None,'special':None,'values':{}})
        if series_row:
            sv=None
            for cc in range(c,1,-1):
                x = ws.cell(series_row,cc).value
                if x and str(x).strip(): sv=str(x).strip(); break
            if sv and not wk['series']: wk['series']=sv
        if special_row:
            x = ws.cell(special_row,c).value or (datacols[c] and ws.cell(special_row,datacols[c]).value)
            if x and str(x).strip(): wk['special']=str(x).strip()
    # metrics rows
    section='SCORE'; owner=None
    for r in range(hdr+1, ws.max_row+1):
        a = str(ws.cell(r,1).value or '').strip()
        label = str(ws.cell(r,2).value or '').strip()
        if a:
            base = a.rstrip(':').strip()
            if base in SECTIONS: section = base; owner=None
            m = re.match(r'^\((.+)\)$', base)
            if m: owner = m.group(1).strip()
        if not label or label=='Special Service:': continue
        if not section: continue
        key = canon(slug(label))
        if key not in catalog:
            catalog[key] = {'label':label,'section':section,'owner':owner}
        elif owner and not catalog[key]['owner']:
            catalog[key]['owner']=owner
        for c,dt in suncols.items():
            v = clean(ws.cell(r,c).value)
            if v is None and datacols[c]:
                v = clean(ws.cell(r,datacols[c]).value)
            if v is not None:
                weeks[dt]['values'][key] = v

today = datetime.date.today().isoformat()
kept = {k:v for k,v in weeks.items() if k <= today}   # drop stale template columns dated in the future
out = {'generated': today,
       'catalog': catalog,
       'weeks': [kept[k] for k in sorted(kept)]}
json.dump(out, open(OUT,'w'), indent=1)
ws_with_data = [w for w in out['weeks'] if w['values']]
print('weeks:', len(out['weeks']), 'with data:', len(ws_with_data))
print('range:', out['weeks'][0]['date'], '->', out['weeks'][-1]['date'])
print('metrics:', len(catalog))
