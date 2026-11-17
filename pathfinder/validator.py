"""The plan validator (owner: Ghina).

The agent is NOT allowed to show a plan the validator rejects.
Errors = the plan is wrong and must be fixed.
Warnings = the plan is allowed, but the student should know something.
"""
from . import data, prereqs, schedule


def validate_plan(student, crns, constraints=None):
    constraints = constraints or {}
    errors, warnings = [], []
    sections = data.sections()
    rules = data.rules()

    # 1. Every CRN must exist (the model must not invent sections).
    unknown = [c for c in crns if c not in sections]
    if unknown:
        return {"valid": False, "errors": [f"CRN {c} does not exist this term" for c in unknown],
                "warnings": [], "total_credits": 0, "sections": []}

    codes = [sections[c]["course"] for c in crns]

    # 2. No course twice.
    for code in set(codes):
        if codes.count(code) > 1:
            errors.append(f"{code} appears more than once (pick one section)")

    # 3. Prerequisites (corequisites may be in the same plan).
    for code in set(codes):
        result = prereqs.check(student, code, planned_codes=codes)
        if not result["allowed"]:
            errors.append(f"{code}: not allowed. {result['reason']}")

    # 4. Seats.
    for c in crns:
        if sections[c]["seats_open"] <= 0:
            errors.append(f'{sections[c]["course"]} section {sections[c]["section"]} (CRN {c}) is full')

    # 5. Time conflicts (lectures AND labs).
    for o in schedule.find_overlaps(crns):
        errors.append(f'Time conflict on {o["day"]}: {o["course_a"]} and {o["course_b"]} ({o["detail"]})')

    # 6. Credit limit.
    total = sum(data.courses()[code]["credits"] for code in codes)
    if total > rules["max_credits_per_term"]:
        errors.append(f'{total} credits is over the limit of {rules["max_credits_per_term"]}')

    # 7. The student's own constraints.
    if constraints.get("earliest_start"):
        limit = schedule.to_minutes(constraints["earliest_start"])
        for c in crns:
            if schedule.earliest_start(c) < limit:
                errors.append(f'{sections[c]["course"]} (CRN {c}) starts before {constraints["earliest_start"]}')
    for day in constraints.get("avoid_days") or []:
        for c in crns:
            if any(d == day for d, _, _, _ in schedule.meetings_of(c)):
                errors.append(f'{sections[c]["course"]} (CRN {c}) meets on {schedule.DAY_NAMES[day]}, which the student wants free')
    target = constraints.get("target_credits")
    if target and total != target:
        warnings.append(f"Plan has {total} credits, the student asked for {target}")

    # 8. AUB elective rules worth flagging.
    for code in set(codes):
        course = data.courses()[code]
        if course.get("ge_areas") and not code.startswith("CMPS"):
            continue  # GE courses count toward GE, not CMPS electives: no warning needed
        if not course["counts_as_cmps_elective"] and code not in rules["cs_major"]["required_cmps"]:
            warnings.append(f"{code} ({course['title']}) does not count as a CMPS elective for the CS major")

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "total_credits": total,
        "sections": [schedule.describe_section(c) for c in crns],
    }
