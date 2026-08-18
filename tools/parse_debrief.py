#!/usr/bin/env python3
"""Parse GCB 'Sunday DEBRIEF Form (Responses)' into tidy JSON."""
import json, re, sys, datetime, pathlib
from openpyxl import load_workbook

ROOT = pathlib.Path(__file__).resolve().parent.parent
# Usage: python3 parse_debrief.py <Sunday DEBRIEF Form (Responses).xlsx> [out.json]
SRC = sys.argv[1] if len(sys.argv) > 1 else str(ROOT/'Sunday DEBRIEF Form (Responses).xlsx')
OUT = sys.argv[2] if len(sys.argv) > 2 else str(ROOT/'data'/'debrief.json')

NAMES = {'andrew':'Andrew Faletti','karissa':'Karissa','hannah':'Hannah Stevens',
         'halima':'Halima Edge','sarah':'Sarah Shivers','angel':'Angel Colon',
         'hazen':'Hazen Stevens','haze':'Hazen Stevens','alice':'Alice Yoon',
         'son':'Son Byrd','ben':'Ben Melancon','kennah':'Kennah Jones',
         'crystal':'Crystal Nicole','gretchen':'Gretchen'}

# element -> (old_col, new_col)  ; ratings normalized to 0-100
ELEMENTS = {
    'Lobby Before':   (5, None), 'Lobby After':   (6, 20),
    'Worship':        (8, None), 'Announcements': (9, 21),
    'Offering':       (10, 22),  'Creative':      (11, 23),
    'Word':           (12, 24),  'Ministry Time': (13, 25),
    'Kids Setup':     (15, None),'Kids Check-in': (16, 26),
    'Kids Class':     (17, 27),
}
# Col 19 was the kids-incident question on the ORIGINAL form; on the current form
# it's the catch-all "anything else?" field. Verified 2026-07-28: only 8 of 90
# entries mention kids at all, the rest are production/ops notes. So it's tagged
# 'other' and the dashboard routes it to kids only when the text is kids-related.
COMMENT_COLS = {4:'overall',7:'lobby',14:'service',18:'kids',19:'other',32:'message'}
MSG = {'engagement':28,'content':29,'time_mgt':30}   # call_to_action = 31 or 33

def rating(v):
    if v is None: return None
    if isinstance(v,(int,float)):
        x=float(v)
        return round(x/10*100) if x>4 else round(x/4*100)  # 1-10 era vs rare numeric 4s
    s=str(v).strip()
    if s.startswith('N/A') or not s: return None
    m=re.match(r'([1-4])\s*=',s)
    if m: return round(int(m.group(1))/4*100)
    try:
        x=float(s); return round(x/10*100) if x>4 else round(x/4*100)
    except ValueError: return None

def ten(v):
    if v is None: return None
    try: return round(float(str(v).strip()),1)
    except ValueError: return None

def name_canon(v):
    s=str(v or '').strip()
    if not s or s=='None': return 'Unknown'
    tok=re.sub(r'[^a-z]','',s.lower().split()[0])
    return NAMES.get(tok, s.title())

wb = load_workbook(SRC, data_only=True)
ws = wb['Form Responses 1']
responses=[]
for r in range(2, ws.max_row+1):
    ts = ws.cell(r,1).value
    if not isinstance(ts, datetime.datetime): continue
    d = ts.date()
    sunday = d - datetime.timedelta(days=(d.weekday()+1)%7)
    ratings={}
    for el,(c1,c2) in ELEMENTS.items():
        v = rating(ws.cell(r,c1).value)
        if v is None and c2: v = rating(ws.cell(r,c2).value)
        if v is not None: ratings[el]=v
    msg={k:ten(ws.cell(r,c).value) for k,c in MSG.items()}
    msg['call_to_action'] = ten(ws.cell(r,31).value) or ten(ws.cell(r,33).value)
    msg={k:v for k,v in msg.items() if v is not None}
    comments={}
    for c,tag in COMMENT_COLS.items():
        v=str(ws.cell(r,c).value or '').strip()
        if v and v.upper() not in ('N/A','NA','NONE','N/A.','-'): comments[tag]=v
    responses.append({'sunday':sunday.isoformat(),'submitted':d.isoformat(),
        'name':name_canon(ws.cell(r,2).value),
        'overall':ten(ws.cell(r,3).value),'ratings':ratings,'message':msg,'comments':comments})

responses.sort(key=lambda x:(x['sunday'],x['name']))
# weekly aggregates
weeks={}
for resp in responses:
    w=weeks.setdefault(resp['sunday'],{'sunday':resp['sunday'],'n':0,'overall':[],
        'elements':{},'message':{},'comments':[],'names':[]})
    w['n']+=1; w['names'].append(resp['name'])
    if resp['overall']: w['overall'].append(resp['overall'])
    for k,v in resp['ratings'].items(): w['elements'].setdefault(k,[]).append(v)
    for k,v in resp['message'].items(): w['message'].setdefault(k,[]).append(v)
    for tag,t in resp['comments'].items(): w['comments'].append({'by':resp['name'],'tag':tag,'text':t})
def avg(l): return round(sum(l)/len(l),1) if l else None
weekly=[]
for k in sorted(weeks):
    w=weeks[k]
    weekly.append({'sunday':k,'n':w['n'],'names':sorted(set(w['names'])),
        'overall_avg':avg(w['overall']),
        'elements':{e:avg(v) for e,v in w['elements'].items()},
        'message':{m:avg(v) for m,v in w['message'].items()},
        'comments':w['comments']})
json.dump({'generated':datetime.date.today().isoformat(),
           'responses':responses,'weekly':weekly}, open(OUT,'w'), indent=1)
print('responses:',len(responses),'weeks:',len(weekly))
print('range:',weekly[0]['sunday'],'->',weekly[-1]['sunday'])
print('latest week:',json.dumps(weekly[-1],indent=1)[:600])
