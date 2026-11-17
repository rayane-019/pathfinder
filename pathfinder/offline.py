"""Offline mode (owner: Rayane): a backup planner that needs no API key.

It uses the SAME tools and the SAME validator as the LLM agent, with simple
rules instead of a model. Use it if the Wi-Fi or the API fails during the demo.
"""
import re

from . import data, schedule
from . import tools as T


def parse_request(text):
    """Very small parser for requests like '15 credits, no classes before 9 AM, one AI elective'."""
    t = text.lower()
    prefs = {"target_credits": 15, "earliest_start": None, "tag": None, "avoid_days": []}
    m = re.search(r"(\d{1,2})\s*credits?", t)
    if m:
        prefs["target_credits"] = int(m.group(1))
    m = re.search(r"before\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", t)
    if m:
        hour = int(m.group(1)) + (12 if m.group(3) == "pm" and int(m.group(1)) < 12 else 0)
        prefs["earliest_start"] = f"{hour:02d}:{m.group(2) or '00'}"
    for word, tag in [("machine learning", "ai"), ("ai", "ai"), ("data", "data"), ("security", "security"),
                      ("web", "web"), ("mobile", "mobile"), ("game", "games"), ("systems", "systems")]:
        if re.search(rf"\b{word}\b", t):
            prefs["tag"] = tag
            break
    for word, letter in [("friday", "F"), ("monday", "M"), ("wednesday", "W")]:
        if re.search(rf"no (classes on |class on )?{word}s?", t) or f"{word}s off" in t or f"{word} off" in t:
            prefs["avoid_days"].append(letter)
    return prefs


def _section_ok(sec, prefs):
    """(ok, reason) for one section against seats and the student's time rules."""
    if sec["full"]:
        return False, "is full"
    crn = sec["crn"]
    if prefs["earliest_start"] and schedule.earliest_start(crn) < schedule.to_minutes(prefs["earliest_start"]):
        return False, f"starts before {prefs['earliest_start']}"
    days = {d for d, _, _, _ in schedule.meetings_of(crn)}
    if days & set(prefs["avoid_days"]):
        return False, "meets on a day the student wants free"
    return True, ""


def plan_offline(student_id, request, on_event):
    session = T.Session(student_id)

    def call(name, **args):
        on_event("tool_call", {"name": name, "args": args})
        result = T.run_tool(session, name, args)
        on_event("tool_result", {"name": name, "result": result})
        return result

    def think(text):
        on_event("thinking", {"text": text})

    prefs = parse_request(request)
    think(f"Goal understood: {prefs['target_credits']} credits"
          + (f", nothing before {prefs['earliest_start']}" if prefs["earliest_start"] else "")
          + (f", one '{prefs['tag']}' elective" if prefs["tag"] else "") + ".")

    record = call("get_student_record")
    if "error" in record:
        return session, record["error"]

    # PLAN: required courses first, then electives that match the goal and focus area.
    required = record.get("repeat_recommended", []) + record["remaining_required_cmps"]
    focus = record["preferences"].get("focus_area")
    electives = []
    if prefs["tag"]:
        electives += [c["code"] for c in call("search_courses", tag=prefs["tag"], only_electives=True)["courses"]
                      if c["offered_this_term"]]
    if focus:
        electives += [c["code"] for c in call("search_courses", focus_area=focus)["courses"] if c["offered_this_term"]]
    electives += [c["code"] for c in data.courses().values() if c["counts_as_cmps_elective"]]
    candidates = list(dict.fromkeys(required + electives))
    think(f"Plan: required first ({', '.join(required) or 'none left'}), then electives.")

    checks = call("check_prerequisites", course_codes=candidates)["results"]
    allowed = [r["course"] for r in checks if r["allowed"]]
    blocked = [f"{r['course']} ({r['reason']})" for r in checks if not r["allowed"] and "already" not in r["reason"]]
    if blocked:
        think("Not allowed yet: " + "; ".join(blocked[:4]) + ("; ..." if len(blocked) > 4 else ""))

    for alert in record.get("alerts", []):
        think(alert)

    # ACT: get the usable sections of each allowed course (a few at a time).
    offered = [c for c in allowed if any(s["course"] == c for s in data.sections().values())]
    usable, fetched = {}, set()

    def fetch(code):
        fetched.add(code)
        result = call("find_sections", course_code=code)
        good = []
        for sec in result.get("sections", []):
            ok, why = _section_ok(sec, prefs)
            if ok:
                good.append(sec["crn"])
            else:
                think(f"Skip {code} section {sec['section']} (CRN {sec['crn']}): {why}.")
        if good:
            usable[code] = good

    def course_sets(start, chosen, credits):
        if credits == prefs["target_credits"]:
            if not prefs["tag"] or tag_codes & set(chosen):
                yield list(chosen)
            return
        for i in range(start, len(order)):
            c = order[i]
            cr = data.courses()[c]["credits"]
            if credits + cr <= prefs["target_credits"]:
                yield from course_sets(i + 1, chosen + [c], credits + cr)

    def assign(codes, picked):
        if len(picked) == len(codes):
            return picked
        for crn in usable[codes[len(picked)]]:
            if not schedule.find_overlaps(picked + [crn]):
                found = assign(codes, picked + [crn])
                if found:
                    return found
        return None

    plan, order, tag_codes = None, [], set()
    n_required = len([c for c in offered if c in required])
    for limit in (n_required + 3, n_required + 6, len(offered)):
        for code in offered[:limit]:
            if code not in fetched:
                fetch(code)
        order = [c for c in offered[:limit] if c in usable]
        tag_codes = {c for c in order if prefs["tag"] and prefs["tag"] in data.courses()[c]["tags"]}
        for codes in course_sets(0, [], 0):
            draft = [usable[c][0] for c in codes]       # first draft: first usable section of each
            result = call("check_conflicts", crns=draft)
            if result["ok"]:
                plan = draft
                break
            shown = set()
            for o in result["time_conflicts"]:
                pair = (o["course_a"], o["course_b"])
                if pair not in shown:
                    shown.add(pair)
                    think(f"Conflict: {o['course_a']} and {o['course_b']} ({o['day']} {o['detail']}). Trying other sections.")
            plan = assign(codes, [])
            if plan:
                call("check_conflicts", crns=plan)
                break
            think("No conflict-free timetable with these courses. Trying another combination.")
        if plan or limit >= len(offered):
            break

    if not plan:
        return session, "I could not find a timetable that fits all your constraints. Try fewer credits or a later start time."

    explanation = "Required courses first, then electives that match the goal and focus area."
    report = call("submit_plan", crns=plan, explanation=explanation, earliest_start=prefs["earliest_start"],
                  target_credits=prefs["target_credits"], avoid_days=prefs["avoid_days"])
    if not report["valid"]:
        return session, "The validator rejected the plan: " + "; ".join(report["errors"])
    return session, format_plan(plan, report)


def format_plan(crns, report):
    lines = ["Here is your plan for " + data.rules()["term"]["name"] + ":", "",
             "| Course | Title | CRN | Days | Time | Room |", "|---|---|---|---|---|---|"]
    for crn in crns:
        s = data.sections()[crn]
        title = data.courses()[s["course"]]["title"]
        for m in s["meetings"]:
            label = s["course"] + (" (lab)" if m["type"] == "lab" else "")
            lines.append(f"| {label} | {title} | {crn} | {m['days']} | {m['start']}-{m['end']} | {m['room']} |")
    lines.append("")
    lines.append(f"Total: {report['total_credits']} credits. Checked by the validator: no conflicts, all prerequisites met.")
    for w in report["warnings"]:
        lines.append(f"Note: {w}")
    lines.append("")
    lines.append("Do you confirm this plan?")
    return "\n".join(lines)
