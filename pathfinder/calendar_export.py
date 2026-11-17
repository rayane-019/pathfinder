"""Exports a plan to an .ics calendar file (owner: Ghina).

.ics works with Google Calendar, Outlook and Apple Calendar.
Each meeting becomes a weekly repeating event for the whole term.
"""
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import data

EXPORT_DIR = Path(__file__).resolve().parent.parent / "exports"
ICS_DAYS = {"M": "MO", "T": "TU", "W": "WE", "R": "TH", "F": "FR", "S": "SA"}
WEEKDAY = {"M": 0, "T": 1, "W": 2, "R": 3, "F": 4, "S": 5}


def _first_date(term_start, day_letter):
    """First date on or after the term start that falls on this weekday."""
    delta = (WEEKDAY[day_letter] - term_start.weekday()) % 7
    return term_start + timedelta(days=delta)


def build_ics(crns):
    term = data.rules()["term"]
    tz = term["timezone"]
    start = date.fromisoformat(term["first_day"])
    until = date.fromisoformat(term["last_day"]).strftime("%Y%m%d") + "T235959Z"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//PathFinder//AUB Course Planner//EN",
             "CALSCALE:GREGORIAN", f"X-WR-CALNAME:AUB {term['name']}"]
    for crn in crns:
        s = data.sections()[crn]
        title = data.courses()[s["course"]]["title"]
        for i, m in enumerate(s["meetings"]):
            first_day = min((_first_date(start, d) for d in m["days"]))
            day_codes = ",".join(ICS_DAYS[d] for d in m["days"])
            dt = first_day.strftime("%Y%m%d")
            lines += [
                "BEGIN:VEVENT",
                f"UID:{crn}-{i}-{dt}@pathfinder",
                f"DTSTAMP:{stamp}",
                f"SUMMARY:{s['course']} {m['type'].title()} - {title}",
                f"LOCATION:{m['room']}",
                f"DESCRIPTION:Section {s['section']}, CRN {crn}",
                f"DTSTART;TZID={tz}:{dt}T{m['start'].replace(':', '')}00",
                f"DTEND;TZID={tz}:{dt}T{m['end'].replace(':', '')}00",
                f"RRULE:FREQ=WEEKLY;BYDAY={day_codes};UNTIL={until}",
                "END:VEVENT",
            ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def write_ics(crns, student_id):
    EXPORT_DIR.mkdir(exist_ok=True)
    path = EXPORT_DIR / f"aub-plan-{student_id}.ics"
    path.write_text(build_ics(crns), encoding="utf-8")
    return str(path)
