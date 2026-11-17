"""Time and schedule helpers (owner: Ghina).

AUB writes days as letters: M T W R F (R = Thursday).
"""
from . import data

DAY_NAMES = {"M": "Monday", "T": "Tuesday", "W": "Wednesday", "R": "Thursday", "F": "Friday", "S": "Saturday"}


def to_minutes(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def meetings_of(crn):
    """Every (day, start_min, end_min, meeting) for one section."""
    section = data.sections()[crn]
    out = []
    for m in section["meetings"]:
        for day in m["days"]:
            out.append((day, to_minutes(m["start"]), to_minutes(m["end"]), m))
    return out


def describe_section(crn):
    s = data.sections()[crn]
    course = data.courses().get(s["course"], {})
    times = ", ".join(f'{m["type"]} {m["days"]} {m["start"]}-{m["end"]} ({m["room"]})' for m in s["meetings"])
    return f'{s["course"]} sec {s["section"]} (CRN {crn}) {course.get("title", "")}: {times}'


def find_overlaps(crns):
    """All pairs of sections that meet at the same time on the same day."""
    overlaps = []
    crns = list(crns)
    for i in range(len(crns)):
        for j in range(i + 1, len(crns)):
            a, b = crns[i], crns[j]
            for day_a, start_a, end_a, ma in meetings_of(a):
                for day_b, start_b, end_b, mb in meetings_of(b):
                    if day_a == day_b and start_a < end_b and start_b < end_a:
                        overlaps.append({
                            "crn_a": a, "crn_b": b,
                            "course_a": data.sections()[a]["course"],
                            "course_b": data.sections()[b]["course"],
                            "day": DAY_NAMES[day_a],
                            "detail": f'{ma["type"]} {ma["start"]}-{ma["end"]} overlaps {mb["type"]} {mb["start"]}-{mb["end"]}',
                        })
    return overlaps


def earliest_start(crn):
    return min(start for _, start, _, _ in meetings_of(crn))


def latest_end(crn):
    return max(end for _, _, end, _ in meetings_of(crn))
