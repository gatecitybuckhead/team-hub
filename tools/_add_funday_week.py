#!/usr/bin/env python3
"""One-off: fold the 2026-08-02 Family Fun Day feedback form into debrief.json.

Sunday 2026-08-02 used a DIFFERENT form (`Family Fun Day 2026 Feedback Form
(Responses)`, Drive id 1H7WbKV5Bn6JBcPkVV3KQSTzF7WLncnBj0PnTz0ttTmA), so
parse_debrief.py's column map does not apply. Per CLAUDE.md this week is folded
in as a `special` week rather than forced into the regular schema.

Scale mapping mirrors parse_debrief.py's 0-100 normalization:
  Yes = 100, Somewhat = 50, No = 0, blank = omitted.
Overall is a 1-5 scale on this form; doubled to the 0-10 scale used elsewhere.
Free text is VERBATIM as typed.
"""
import json, pathlib, datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
P = ROOT / 'data' / 'debrief.json'
SUNDAY, SUBMITTED = '2026-08-02', '2026-08-03'

SCALE = {'Yes': 100, 'Somewhat': 50, 'No': 0}
ELS = ['Event Tone', 'Food Variety', 'Decorations', 'Guest Flow',
       'Game Stations (amount)', 'Game Variety', 'Game Logistics',
       'Volunteer Staffing', 'Service Flow', 'On-Time Execution',
       'Ownership Clarity', 'New Guests Welcomed']

# name, overall(1-5), answers in ELS order (None = blank)
PEOPLE = [
 ('Sarah Shivers', 5, ['Yes','Yes','Yes','Somewhat','Yes','Yes','Yes','Yes','Yes','Yes','Yes','Yes']),
 ('Andrew Faletti', 5, ['Yes','Yes','Yes','Yes','Yes','Yes','Yes','Yes','Somewhat','Yes','Yes','Yes']),
 ('Halima Edge', 4, ['Yes','Yes','Yes','Somewhat','Yes','Somewhat','Yes','Yes','Yes','Somewhat','Yes','Yes']),
 ('Angel Colon', 4, ['Yes','Yes','Yes','Yes','Yes','Somewhat','Somewhat','No','Somewhat','No','Somewhat','Somewhat']),
 ('Son Byrd', 4, ['Yes','Somewhat','Yes','Somewhat','Yes','Yes',None,'Somewhat','Somewhat',None,'Somewhat','Yes']),
]

# tag -> verbatim text, per person. Tags reuse parse_debrief.py's vocabulary so
# the dashboard's existing routing (TAGLABEL / kids regex) keeps working.
TEXT = {
 'Sarah Shivers': [
   ('service', "Halima sis amazing organizing this! It was fun, engaging, and had heartfelt spiritual moments."),
   ('lobby',   "Great job! Decor and food was amazing"),
   ('other',   "Add crafts back in for kids that need low stimulation"),
   ('other',   "I'm curious how the 2 bounce houses went -- I liked that there was one for older kids and one for younger."),
   ('other',   "Reach: between mailers, texts, and social media, it seems that our reach was well-saturated"),
   ('overall', "Halima did a great job organizing and envisioning, Andrew great job with the score leader board, Son, Angel & Meliisa- great job with \"wow\" factor and hospitality as always! Thank you Hannah for being a team player and collecting the scores, persevering through the day."),
 ],
 'Andrew Faletti': [
   ('service', "Seeing a number of families come be with us that don't normally come week to week was really awesome especially the new family that was from the neighborhood. The games and the decor and the food were amazing. We facilitated the time really well with appropriate structure, but also free flowing. Multiple people said the fellowship was really meaningful and the time was fun. It's the most people I think we've had since Easter."),
   ('lobby',   "Only thing that I heard that was slow was the cotton candy machine. Besides that I think the hospitality team knocked the food out of the park."),
   ('other',   "Only feedback I would give would be communication on cleanup was a little lacking. I had a lot to do to pack up everything with production since school starts this week and I was happy to help pack all the games in my car, but it would've been nice to have had that communication ahead of time to be more prepared. Not a big deal but just a point of communication for us as a team to work on in future events is to make sure we talk about cleanup and what all will be needed."),
   ('other',   "Reach: We could have put the family fund day tickets in mailboxes around the neighborhood"),
   ('overall', "I thoroughly enjoyed the day and thought it was a huge win. Felt really proud of our team and the part everybody played in pulling it off. Really grateful we are sticking to our vision to have special events like this that foster connection and fellowship and fun with our church family."),
 ],
 'Halima Edge': [
   ('service', "The energy in the room was that of excitement and joy!! Everyone seemed to have a blast."),
   ('lobby',   "The corner by the first classroom near the food seemed a bit crowded, and it was difficult to tell where the line was. I thought the food variety was great, but wondering if people felt it lacked at least one \"nutritious\" food."),
   ('other',   "I would setup a room for smaller kids like we did last year."),
   ('other',   "All the games really felt like a hit."),
   ('other',   "Reach: I think we covered all the bases. Mailers, widest audience comms, personal invites, etc."),
   ('overall', "This was my favorite Family Fun Day thus far. The \"carnival\" theme really came alive."),
 ],
 'Angel Colon': [
   ('overall', "Maybe next time more hands on deck when it comes to decor, organizing, and clean up afterwards. We need a storage"),
 ],
 'Son Byrd': [
   ('overall', "My biggest challenge was not having enough time for set up. that may the day of experience more stressful with trying to get things prepared and set up in time."),
 ],
}

d = json.load(open(P))
before_r, before_w = len(d['responses']), len(d['weekly'])

# idempotent: drop any prior 8/2 rows
d['responses'] = [r for r in d['responses'] if r['sunday'] != SUNDAY]
d['weekly'] = [w for w in d['weekly'] if w['sunday'] != SUNDAY]

new_resp, agg, comments = [], {e: [] for e in ELS}, []
overalls = []
for name, ov, answers in PEOPLE:
    ratings = {}
    for el, a in zip(ELS, answers):
        if a is None:
            continue
        ratings[el] = SCALE[a]
        agg[el].append(SCALE[a])
    ten = ov * 2.0
    overalls.append(ten)
    cm = {}
    for tag, txt in TEXT.get(name, []):
        cm.setdefault(tag, []).append(txt)
        comments.append({'by': name, 'tag': tag, 'text': txt})
    new_resp.append({'sunday': SUNDAY, 'submitted': SUBMITTED, 'name': name,
                     'overall': ten, 'ratings': ratings, 'message': {},
                     'comments': {k: '\n\n'.join(v) for k, v in cm.items()}})

def avg(l): return round(sum(l) / len(l), 1) if l else None

week = {'sunday': SUNDAY, 'n': len(PEOPLE),
        'names': sorted({p[0] for p in PEOPLE}),
        'overall_avg': avg(overalls),
        'elements': {e: avg(v) for e, v in agg.items() if v},
        'message': {}, 'comments': comments}

d['responses'].extend(new_resp)
d['responses'].sort(key=lambda x: (x['sunday'], x['name']))
d['weekly'].append(week)
d['weekly'].sort(key=lambda x: x['sunday'])
d['generated'] = datetime.date.today().isoformat()
json.dump(d, open(P, 'w'), indent=1)

print(f"responses {before_r} -> {len(d['responses'])}   weeks {before_w} -> {len(d['weekly'])}")
print('latest week:', d['weekly'][-1]['sunday'], 'n=', week['n'], 'overall_avg=', week['overall_avg'])
for e, v in sorted(week['elements'].items(), key=lambda x: -x[1]):
    print(f'  {v:6.1f}  {e}')
