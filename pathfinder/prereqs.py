"""Prerequisite checking (owner: Lana).

A prerequisite in courses.json is written as a small tree:
  "CMPS 271"                                -> must have passed CMPS 271
  {"course": "CMPS 202", "min_grade": "C+"} -> must have C+ or better in CMPS 202
  {"any": [ ... ]}                          -> at least one of the items
  {"all": [ ... ]}                          -> every item
  {"standing": "senior"}                    -> class standing (from credits earned)
This file walks that tree and explains, in plain English, why it passes or fails.
"""
from . import data


def grade_ok(grade, min_grade):
    points = data.rules()["grade_points"]
    if grade not in points or min_grade not in points:
        return False
    return points[grade] >= points[min_grade]


def standing_of(student):
    credits = student.get("credits_earned", 0)
    thresholds = data.rules()["standing_thresholds"]
    standing = "freshman"
    for name, minimum in sorted(thresholds.items(), key=lambda kv: kv[1]):
        if credits >= minimum:
            standing = name
    return standing


def _grades(student):
    return {c["code"]: c["grade"] for c in student["completed"]}


def _eval(node, grades, standing, planned):
    """Returns (ok, explanation)."""
    passing = data.rules()["passing_grade"]
    if node is None:
        return True, "no prerequisites"
    if isinstance(node, str):
        if node in grades and grade_ok(grades[node], passing):
            return True, f"passed {node} ({grades[node]})"
        return False, f"needs {node}"
    if "course" in node:
        code, min_grade = node["course"], node.get("min_grade", passing)
        if code in grades and grade_ok(grades[code], min_grade):
            return True, f"{grades[code]} in {code} (needs {min_grade})"
        if code in grades:
            return False, f"needs at least {min_grade} in {code}, but has {grades[code]}"
        return False, f"needs at least {min_grade} in {code}"
    if "standing" in node:
        order = ["freshman", "sophomore", "junior", "senior"]
        need = node["standing"]
        if order.index(standing) >= order.index(need):
            return True, f"{standing} standing"
        return False, f"needs {need} standing (student is {standing})"
    if "any" in node:
        results = [_eval(n, grades, standing, planned) for n in node["any"]]
        for ok, why in results:
            if ok:
                return True, why
        return False, "one of: " + " OR ".join(why for _, why in results)
    if "all" in node:
        results = [_eval(n, grades, standing, planned) for n in node["all"]]
        failed = [why for ok, why in results if not ok]
        if failed:
            return False, "; ".join(failed)
        return True, "; ".join(why for _, why in results)
    return False, f"unknown prerequisite format: {node}"


def check(student, course_code, planned_codes=()):
    """Can this student take this course? Returns a dict the agent can read."""
    course = data.courses().get(course_code)
    if course is None:
        return {"course": course_code, "allowed": False, "reason": "course not found in the AUB data"}
    grades = _grades(student)
    repeat_min = data.rules().get("repeat_if_below", {}).get(course_code)
    if course_code in grades and repeat_min and not grade_ok(grades[course_code], repeat_min):
        return {"course": course_code, "allowed": True,
                "reason": f"repeat: has {grades[course_code]}, AUB requires at least {repeat_min}"}
    if course_code in grades and grade_ok(grades[course_code], data.rules()["passing_grade"]):
        return {"course": course_code, "allowed": False, "reason": f"already completed ({grades[course_code]})"}
    ok, why = _eval(course.get("prereq"), grades, standing_of(student), planned_codes)
    # Corequisites may be taken before OR in the same term.
    for co in course.get("coreq", []):
        if co not in grades and co not in planned_codes:
            ok, why = False, (why + "; " if why else "") + f"must take {co} before or in the same term"
    result = {"course": course_code, "allowed": ok, "reason": why}
    if course.get("note"):
        result["note"] = course["note"]
    return result
