"""The agent's tools (owner: Lana).

Each tool is a plain Python function that returns a dict.
TOOL_SCHEMAS describes them to the LLM (name, what it does, its arguments).
The LLM picks a tool, our code runs it, and the result goes back to the LLM.
"""
from . import data, prereqs, schedule, validator, calendar_export


class Session:
    """What the agent knows during one conversation (its short-term memory)."""

    def __init__(self, student_id):
        self.student_id = student_id
        self.approved_plan = None      # set when submit_plan passes the validator
        self.student_confirmed = False  # set ONLY by the human, never by the model
        self.export_path = None


# ---------- 1. get_student_record ----------
def get_student_record(session, **_):
    student = data.students().get(session.student_id)
    if student is None:
        return {"error": f"no student with id {session.student_id}"}
    major = data.rules()["cs_major"]
    done = {c["code"] for c in student["completed"]}
    remaining_required = [c for c in major["required_cmps"] if c not in done]
    elective_credits_done = sum(
        c["credits"] for c in student["completed"]
        if c["code"] in data.courses() and data.courses()[c["code"]]["counts_as_cmps_elective"]
        and c["code"] not in major["required_cmps"])
    alerts, repeat = [], []
    for c in student["completed"]:
        if c["code"] in ("CMPS 201", "CMPS 202") and not prereqs.grade_ok(c["grade"], "C+"):
            alerts.append(f'AUB rule: CS majors need at least C+ in {c["code"]} (student has {c["grade"]}). '
                          f'Most CMPS courses stay locked until it is repeated with C+ or better.')
            repeat.append(c["code"])
    return {
        "id": student["id"],
        "alerts": alerts,
        "name": student["name"],
        "major": student["major"],
        "credits_earned": student["credits_earned"],
        "standing": prereqs.standing_of(student),
        "completed": student["completed"],
        "remaining_required_cmps": remaining_required,
        "repeat_recommended": repeat,
        "cmps_elective_credits_done": elective_credits_done,
        "cmps_elective_credits_needed": major["cmps_elective_credits"],
        "elective_rule": major["elective_rule"],
        "focus_areas": data.rules()["focus_areas"],
        "preferences": student.get("preferences", {}),
        "max_credits_per_term": data.rules()["max_credits_per_term"],
    }


# ---------- 2. search_courses ----------
def search_courses(session, query="", tag=None, focus_area=None, only_electives=False, ge_area=None, limit=15, **_):
    q = query.lower().strip()
    results = []
    for c in data.courses().values():
        text = f'{c["code"]} {c["title"]} {" ".join(c["tags"])}'.lower()
        if q and q not in text and data.normalize_code(q) != c["code"]:
            continue
        if tag and tag.lower() not in c["tags"]:
            continue
        if focus_area and focus_area not in c["focus_areas"]:
            continue
        if only_electives and not c["counts_as_cmps_elective"]:
            continue
        if ge_area and not any(a.startswith(ge_area) for a in c.get("ge_areas", [])):
            continue
        secs = [s for s in data.sections().values() if s["course"] == c["code"]]
        open_seats = sum(max(0, s["seats_open"] or 0) for s in secs)
        results.append({
            "code": c["code"], "title": c["title"], "credits": c["credits"],
            "counts_as_cmps_elective": c["counts_as_cmps_elective"],
            "focus_areas": c["focus_areas"], "ge_areas": c.get("ge_areas", []),
            "offered_this_term": bool(secs), "has_open_seats": open_seats > 0, "note": c.get("note"),
        })
    # Keep answers short (the free AI plan limits how much text we send per minute):
    # courses with open seats first, then offered-but-full, then not offered.
    results.sort(key=lambda r: (not r["has_open_seats"], not r["offered_this_term"]))
    total = len(results)
    results = results[:max(1, min(int(limit or 15), 40))]
    return {"count": total, "showing": len(results), "courses": results,
            "hint": "Only the first results are shown (open seats first). Use a narrower search for more."}


# ---------- GE: check_ge_progress ----------
def ge_progress(student):
    """How many courses the student has done and still needs in each GE area."""
    rules = data.ge_rules()
    done = {c["code"] for c in student["completed"]}
    count = {a: 0 for a in rules["ge_areas"]}
    list_i = {"humanities": 0, "social_sciences": 0}
    counted = []
    for code in done:
        if code in rules["english_courses"]:
            count["english"] += 1; counted.append(f"{code} (English)"); continue
        areas = data.courses().get(code, {}).get("ge_areas", [])
        for a in areas:  # a course counts for its first area that still needs courses
            group = a.rsplit("_", 1)[0] if a[-2:] in ("_1", "_2") else a
            if group in count and count[group] < rules["ge_areas"][group]["needed"]:
                count[group] += 1
                if a.endswith("_1") and group in list_i:
                    list_i[group] += 1
                counted.append(f"{code} ({rules['ge_areas'][group]['name']})")
                break
    areas_out = {}
    for a, info in rules["ge_areas"].items():
        out = {"name": info["name"], "done": count[a], "needed": info["needed"],
               "remaining": max(0, info["needed"] - count[a])}
        if "list_i_needed" in info:
            out["list_i_remaining"] = max(0, info["list_i_needed"] - list_i[a])
        areas_out[a] = out
    return {"areas": areas_out, "counted_courses": counted, "notes": rules["notes"],
            "data_note": "Only courses in our GE list are counted. Check AUBsis for the official audit."}


def check_ge_progress(session, **_):
    return ge_progress(data.students()[session.student_id])


# ---------- 3. check_prerequisites ----------
def check_prerequisites(session, course_codes, planned_codes=None, **_):
    student = data.students()[session.student_id]
    planned = [data.normalize_code(c) for c in (planned_codes or [])]
    return {"results": [prereqs.check(student, data.normalize_code(c), planned) for c in course_codes]}


# ---------- 4. find_sections ----------
def find_sections(session, course_code, **_):
    code = data.normalize_code(course_code)
    if code not in data.courses():
        return {"error": f"{code} is not in the AUB course data"}
    found = []
    for s in data.sections().values():
        if s["course"] == code:
            found.append({
                "crn": s["crn"], "section": s["section"], "seats_open": s["seats_open"],
                "full": s["seats_open"] <= 0, "meetings": s["meetings"],
            })
    if not found:
        return {"course": code, "sections": [], "message": f"{code} is not offered this term"}
    return {"course": code, "term": data.rules()["term"]["name"], "sections": found}


# ---------- 5. check_conflicts ----------
def check_conflicts(session, crns, **_):
    unknown = [c for c in crns if c not in data.sections()]
    if unknown:
        return {"error": f"unknown CRNs: {unknown}"}
    credits = sum(data.courses()[data.sections()[c]["course"]]["credits"] for c in crns)
    overlaps = schedule.find_overlaps(crns)
    return {"total_credits": credits, "max_credits": data.rules()["max_credits_per_term"],
            "time_conflicts": overlaps, "ok": not overlaps}


# ---------- submit_plan: the validator guards every plan ----------
def submit_plan(session, crns, explanation="", earliest_start=None, target_credits=None,
                avoid_days=None, **_):
    student = data.students()[session.student_id]
    constraints = {"earliest_start": earliest_start, "target_credits": target_credits,
                   "avoid_days": avoid_days or []}
    report = validator.validate_plan(student, crns, constraints)
    if report["valid"]:
        session.approved_plan = {"crns": crns, "explanation": explanation,
                                 "constraints": constraints, "report": report}
        report["next_step"] = ("Plan approved by the validator. Show it to the student and wait. "
                               "Do NOT call export_calendar until the student confirms.")
    else:
        report["next_step"] = "Fix every error above, then call submit_plan again."
    return report


# ---------- 6. export_calendar ----------
def export_calendar(session, **_):
    if session.approved_plan is None:
        return {"error": "No validated plan yet. Call submit_plan first."}
    if not session.student_confirmed:
        return {"error": "The student has not confirmed the plan. Ask them first."}
    path = calendar_export.write_ics(session.approved_plan["crns"], session.student_id)
    session.export_path = path
    return {"ok": True, "file": path}


TOOLS = {
    "get_student_record": get_student_record,
    "search_courses": search_courses,
    "check_prerequisites": check_prerequisites,
    "find_sections": find_sections,
    "check_conflicts": check_conflicts,
    "check_ge_progress": check_ge_progress,
    "submit_plan": submit_plan,
    "export_calendar": export_calendar,
}


def run_tool(session, name, args):
    """Runs one tool safely: a crash becomes an error message, not a dead agent."""
    if name not in TOOLS:
        return {"error": f"unknown tool {name}"}
    try:
        return TOOLS[name](session, **(args or {}))
    except Exception as e:  # reliability: report the error back to the model
        return {"error": f"{type(e).__name__}: {e}"}


def _fn(name, description, properties, required=()):
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": properties, "required": list(required)}}}


TOOL_SCHEMAS = [
    _fn("get_student_record",
        "Load the student's AUB record: completed courses with grades, credits, standing, "
        "remaining required CMPS courses, elective credits, focus areas and credit limit. Call this first.", {}),
    _fn("search_courses",
        "Search AUB courses (CMPS + General Education) by text, tag (e.g. 'ai', 'systems', 'software', 'data', "
        "'ge', 'social_inequalities', 'human_values', 'history_of_ideas') or focus area ('systems', 'ai_data', 'software').",
        {"query": {"type": "string", "description": "Text or course code, e.g. 'machine learning' or 'CMPS 261'"},
         "tag": {"type": "string"},
         "focus_area": {"type": "string", "enum": ["systems", "ai_data", "software"]},
         "only_electives": {"type": "boolean", "description": "Only courses that count as CMPS electives"},
         "ge_area": {"type": "string", "enum": ["english", "arabic", "humanities", "humanities_1", "social_sciences",
                                                "social_sciences_1", "natural_sciences", "quantitative"],
                     "description": "Only General Education (GE) courses in this area"}}),
    _fn("check_ge_progress",
        "Show the student's General Education (GE) progress: for each area (English, Arabic, Humanities, "
        "Social Sciences, Natural Sciences, Quantitative Thought), how many courses are done and still needed.", {}),
    _fn("check_prerequisites",
        "Check whether the student may take each course, with the exact reason (AUB grade rules like C+ included).",
        {"course_codes": {"type": "array", "items": {"type": "string"}},
         "planned_codes": {"type": "array", "items": {"type": "string"},
                           "description": "Other courses in the draft plan (for corequisites)"}},
        ["course_codes"]),
    _fn("find_sections",
        "List the sections of one course this term with CRN, days (M T W R F, R = Thursday), times, rooms and open seats.",
        {"course_code": {"type": "string"}}, ["course_code"]),
    _fn("check_conflicts",
        "Check a draft list of CRNs for time overlaps (lectures and labs) and total credits.",
        {"crns": {"type": "array", "items": {"type": "string"}}}, ["crns"]),
    _fn("submit_plan",
        "Submit the final plan to the validator. It checks prerequisites, seats, conflicts, credit limit and "
        "the student's constraints. If it returns errors, fix them and submit again.",
        {"crns": {"type": "array", "items": {"type": "string"}},
         "explanation": {"type": "string", "description": "Why each course was chosen, in simple words"},
         "earliest_start": {"type": "string", "description": "e.g. '09:00' if the student wants no class before 9 AM"},
         "target_credits": {"type": "integer"},
         "avoid_days": {"type": "array", "items": {"type": "string", "enum": ["M", "T", "W", "R", "F"]}}},
        ["crns", "explanation"]),
    _fn("export_calendar",
        "Write the approved plan to a .ics calendar file. Only works after the student confirms the plan.", {}),
]
