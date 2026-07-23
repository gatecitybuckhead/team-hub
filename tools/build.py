#!/usr/bin/env python3
"""Build GCB Team Hub staff dashboards.
Reads data/*.json, computes word frequencies, injects into templates/,
writes plain HTML to build/ (NOT committed). Run encrypt.py afterwards
to produce the published site/staff/*.html.
Usage: python3 build.py
"""
import json, re, collections, datetime, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA, TPL, OUT = ROOT/'data', ROOT/'templates', ROOT/'build'
OUT.mkdir(exist_ok=True)

metrics   = json.load(open(DATA/'metrics.json'))
debrief   = json.load(open(DATA/'debrief.json'))
meetings  = json.load(open(DATA/'meetings.json'))
summaries = json.load(open(DATA/'summaries.json'))
# Per-Sunday written debrief summaries (optional; survives parse_debrief re-runs).
# The dashboard shows the entry for the LATEST week only, else auto-generates.
try:
    narratives = json.load(open(DATA/'debrief_narratives.json')).get('weeks', {})
except FileNotFoundError:
    narratives = {}

# ---------- word frequencies per month (comments + meeting text) ----------
STOP = set('''a an the and or but if then than so of to in on at for with from by as is are was were be been being
this that these those it its it's im i'm we our us you your they their he she his her him them there here what which
who whom how when where why not no yes do does did done doing have has had having will would can could should shall
may might must let lets also just really very much more most some any all both each few other another one two three
first next last new old good great well better best out up down over under again during before after above below
about into through between while because get got getting go going went come came make made making take took say said
think thought feel felt felt like time week today sunday service church team meeting people person thing things way
lot bit kind maybe still even back off now day am pm ok okay n/a na none nothing didnt didn't dont don't cant can't
wasnt wasn't isnt isn't need needs needed want wanted love loved keep continue always never definitely little big
etc'''.split())
NAMES = set('andrew karissa hannah halima sarah angel hazen alice son ben kennah crystal gretchen faletti stevens shivers colon byrd melancon jones yoon edge pearl nicole'.split())

def tokens(text):
    for w in re.findall(r"[a-zA-Z']{3,}", text.lower()):
        w = w.strip("'")
        if len(w) >= 3 and w not in STOP and w not in NAMES:
            yield w

word_months = collections.defaultdict(collections.Counter)
for w in debrief['weekly']:
    mo = w['sunday'][:7]
    for c in w['comments']:
        word_months[mo].update(tokens(c['text']))
for m in meetings:
    mo = m['date'][:7]
    blob = ' '.join([m.get('summary') or ''] + (m.get('decisions') or []) + (m.get('topics') or []))
    word_months[mo].update(tokens(blob))
word_months = {mo: dict(c.most_common(70)) for mo, c in sorted(word_months.items())}

# ---------- meetings slimmed for the debrief page ----------
meet_slim = [{'date': m['date'], 'title': m.get('title',''), 'summary': m.get('summary',''),
              'decisions': m.get('decisions') or [], 'actions': m.get('action_items') or []}
             for m in sorted(meetings, key=lambda x: x['date'])]

built = datetime.date.today().isoformat()

def inject(tpl_name, out_name, payload):
    html = open(TPL/tpl_name).read()
    html = html.replace('/*__DATA__*/null', json.dumps(payload, separators=(',',':')))
    html = html.replace('__BUILT__', built)
    open(OUT/out_name, 'w').write(html)
    print('built', out_name, f'{(OUT/out_name).stat().st_size//1024}KB')

inject('metrics.template.html', 'metrics.html',
       {'metrics': metrics, 'summaries': summaries})
inject('debrief.template.html', 'debrief.html',
       {'weekly': debrief['weekly'], 'meetings': meet_slim,
        'summaries': summaries, 'words': word_months,
        'narratives': narratives})
