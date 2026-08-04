#!/usr/bin/env python3
"""Weekly refresh writes for the 2026-08-04 run: new meeting + period summaries.

Kept as a file (not an inline one-liner) so the edits are auditable and the big
JSONs never enter the agent's context.

1. meetings.json  <- 2026-07-30 GC Buckhead Tactical Meeting (Zoom summary.md)
2. summaries.json <- July 2026 finalized (month ended), 2026-08 "(so far)" added,
                     Q3 2026 partial refreshed.

Stats basis (matches how the existing avg_attendance / avg_overall_rating were
derived): avg_attendance = mean of `total_attendance` over the period's recorded
Sundays; avg_overall_rating = mean of debrief `overall_avg`; giving_total = sum of
`week_s_tithes_offerings_digital` + `week_s_tithes_offerings_cash`.
NOTE: pre-2026-07 giving_total values in this file were computed from the OLD
metrics parse (the combined "Week's $ Tithes/Offerings" column, now split into
digital/cash), so they are NOT on the same basis as July's. Flagged for Andrew.
"""
import json, pathlib, statistics

ROOT = pathlib.Path(__file__).resolve().parent.parent
D = ROOT / 'data'

# ---------------------------------------------------------------- 1. meetings
MEET = {
    "date": "2026-07-30",
    "title": "GC Buckhead Tactical Meeting",
    "source": "zoom-archive",
    "summary": (
        "Final Family Fun Day planning session (66 min, 9 on the call). The team locked "
        "the game plan around a QR-code leaderboard at four stations, cut the water gun "
        "fight on safety and mess grounds, and confirmed an indoor grill plus a two-unit "
        "bounce house / obstacle course package for $500. Signage, food contingency, "
        "slides, bingo supplies and the Bucky costume all got named owners and deadlines, "
        "with setup set for Saturday 1:30pm and a Sunday 9:00am arrival / 9:30 run-through. "
        "Closed with a look ahead to in-person Formation nights starting August 12 and a "
        "spiritual reflection on family outreach."
    ),
    "decisions": [
        "Reject the water gun fight (safety and mess)",
        "No basketball hoop needed — home possession is sufficient",
        "QR-code leaderboard at 4 stations (cornhole, ring toss, balloon darts, skeeball)",
        "Simplify scoring to first/second/third place per game; Hannah to manage",
        "Food contingency decision point set at 11:30–12:00; Son to lead the food run (Melissa backup)",
        "Bounce house + obstacle course: two units for $500; vendor to be contacted",
        "Indoor grill setup preferred over outdoor",
        "Signage: two black A-frame signs (24x36 insert) at the front entrance; bathroom signage to the side of the lobby",
        "Setup Saturday 1:30pm; Sunday arrival 9:00am; run-through 9:30am",
        "Bingo: 100 cards plus cheapest pencils/pens",
        "Formation nights resume in person August 12; citywide prayer meeting paused; staff meeting stays in person",
    ],
    "action_items": [
        "Andrew — build and present the QR-code leaderboard (4 stations); preload it in ProPresenter from the registration list; send final QR codes to Hannah; retrieve the portable speaker; confirm Saturday 1:30 setup with Avery",
        "Halima — clarify the meeting recording/summary process; add Family Fun Day comms to the email plan; set the food contingency decision point; retrieve and groom the Bucky costume",
        "Hazen — push Family Fun Day prep and Sunday readiness; confirm the Bucky costume location; remind Cindy no chairs are needed; buy two hot dog cookers; recruit for the hot dog station",
        "Son — contact the bounce house vendor ($500 two-unit deal, donation/write-off option); confirm 9–10am Sunday setup and indoor feasibility; food setup plan with the hot dog station by end of day tomorrow",
        "Hannah — run game scoring (first/second/third); tabulate backpack drive results and send a summary",
        "Sarah — personal texts to backpack contributors inviting them to Family Fun Day; volunteer as Bucky if available",
        "Kennah — order 100 bingo cards and cheapest pencils/pens; create the welcome, man-gun and Psalm 128 slides and send to Andrew; send the final game list to Andrew",
        "Angel — create the Family Fun Day playlist",
    ],
    "topics": [
        "family fun day", "qr code leaderboard", "game scoring", "volunteer coordination",
        "signage", "food setup", "safety", "outreach", "bucky costume",
        "hot dog station", "event logistics", "formation nights",
    ],
}

meetings = json.load(open(D / 'meetings.json'))
if any(m['date'] == MEET['date'] and m['title'] == MEET['title'] for m in meetings):
    print('meetings.json: 2026-07-30 already present — skipped')
else:
    meetings.append(MEET)
    meetings.sort(key=lambda m: (m['date'], m['title']))
    json.dump(meetings, open(D / 'meetings.json', 'w'), indent=1)
    print(f'meetings.json: appended 2026-07-30 ({len(meetings)} total)')

# --------------------------------------------------------------- 2. summaries
metrics = json.load(open(D / 'metrics.json'))
debrief = json.load(open(D / 'debrief.json'))

def in_period(date, pref):
    return date.startswith(pref)

def stats_for(dates_pref, quarter_months=None):
    """dates_pref = 'YYYY-MM' or, with quarter_months, a list of 'YYYY-MM'."""
    prefs = quarter_months or [dates_pref]
    wk = [w for w in metrics['weeks'] if any(in_period(w['date'], p) for p in prefs)]
    att = [w['values']['total_attendance'] for w in wk if w['values'].get('total_attendance') is not None]
    give = 0.0
    for w in wk:
        for k in ('week_s_tithes_offerings_digital', 'week_s_tithes_offerings_cash',
                  'week_s_tithes_offerings'):
            v = w['values'].get(k)
            if v is not None:
                give += float(v)
    db = [w['overall_avg'] for w in debrief['weekly']
          if any(in_period(w['sunday'], p) for p in prefs) and w['overall_avg'] is not None]
    nmd = sum(int(w['values'].get('new_member_decisions') or 0) for w in wk)
    return {
        'avg_attendance': round(statistics.mean(att)) if att else None,
        'giving_total': round(give) if give else None,
        'avg_overall_rating': round(statistics.mean(db), 1) if db else None,
        'new_member_decisions': nmd,
    }

JULY_TEXT = (
    "July closed as a strong month of teaching with a thinning summer room. Detox wrapped "
    "with weeks 3 and 4 and Journey Through James opened to the best feedback of the month "
    "— 9.2, 9.3 and 9.0 across the last three Sundays, with the Word rated a perfect 100 "
    "on 7/19 and worship a clean 100 on 7/26. The new ME-1 personal monitors and AudioLink "
    "have the singers happier than they have been all year, and the 10:10 pre-service meeting "
    "started on time. The counterweight is attendance: 7/26 came in at 44 in the sanctuary, "
    "the lowest figure on record, and total attendance averaged 70 across four Sundays. "
    "Off-stage the month was spent building — Family Matters planned out to five weeks "
    "with guest speakers, a Team A/B first-impressions structure in place, and three tactical "
    "meetings devoted almost entirely to landing Family Fun Day on August 2."
)

AUG_TEXT = (
    "(So far) August opened with Family Fun Day on 8/2, and the team's own verdict was the "
    "best one yet — 5 debriefs averaging 8.8/10, with tone, decorations and the number of "
    "game stations all scoring a perfect 100. Andrew's read is the headline: several families "
    "who don't normally come week to week showed up, including a new family from the "
    "neighborhood, and it was the most people in the room since Easter. The growth edge was "
    "entirely logistical and three people named the same thing — not enough hands or time "
    "for setup and cleanup, with on-time execution the lowest-rated element at 62.5. "
    "The metrics sheet has not been filled in for 8/2 yet, so no attendance or giving figures "
    "are available for the month."
)

Q3_TEXT = (
    "(So far) Five Sundays in, Q3 is a quarter of strong teaching and a summer-thin room. "
    "Detox finished and Journey Through James opened to three straight Sundays at 9.0 or "
    "better, with the Word and worship both hitting 100; the ME-1 monitor system has sound "
    "trending up week over week. Attendance is the open question — total attendance is "
    "averaging 70 and 7/26 set a record low of 44 in the sanctuary. The quarter's first big "
    "swing, Family Fun Day on August 2, landed well: highest turnout since Easter, a new "
    "neighborhood family, and a clear team ask for more setup and cleanup help at future "
    "events. Family Matters is planned out to five weeks with guest speakers and Formation "
    "nights resume in person on August 12."
)

summaries = json.load(open(D / 'summaries.json'))

def upsert(kind, period, label, text, stats):
    lst = summaries[kind]
    entry = {'period': period, 'label': label, 'text': text, 'stats': stats}
    for i, e in enumerate(lst):
        if e['period'] == period:
            lst[i] = entry
            print(f'summaries.{kind}: updated {period} {stats}')
            return
    lst.append(entry)
    lst.sort(key=lambda e: e['period'])
    print(f'summaries.{kind}: added {period} {stats}')

upsert('monthly', '2026-07', 'July 2026', JULY_TEXT, stats_for('2026-07'))
upsert('monthly', '2026-08', 'August 2026', AUG_TEXT, stats_for('2026-08'))
upsert('quarterly', '2026-Q3', 'Q3 2026', Q3_TEXT,
       stats_for(None, ['2026-07', '2026-08', '2026-09']))

json.dump(summaries, open(D / 'summaries.json', 'w'), indent=1)
print('summaries.json written:',
      len(summaries['monthly']), 'monthly,', len(summaries['quarterly']), 'quarterly')
