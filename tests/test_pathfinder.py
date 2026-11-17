"""Run with:  python -m pytest -q"""
import json
from types import SimpleNamespace as NS

from pathfinder import data, prereqs, tools as T, validator
from pathfinder.agent import PathFinderAgent
from pathfinder.offline import plan_offline, parse_request

JUNIOR, SOPHOMORE = "202300123", "202400456"
GOOD_PLAN = ["20880", "20886", "20904", "20900+20899", "20893"]


# ---------- Lana: data and prerequisites ----------
def test_c_plus_rule_blocks_sophomore():
    r = prereqs.check(data.students()[SOPHOMORE], "CMPS 214")
    assert not r["allowed"] and "C+" in r["reason"]


def test_junior_can_take_machine_learning():
    assert prereqs.check(data.students()[JUNIOR], "CMPS 261")["allowed"]


def test_senior_standing_needed_for_security():
    r = prereqs.check(data.students()[JUNIOR], "CMPS 243")
    assert not r["allowed"] and "senior" in r["reason"]


def test_corequisite_in_same_plan():
    s = data.students()[JUNIOR]
    assert not prereqs.check(s, "CMPS 254")["allowed"]
    assert prereqs.check(s, "CMPS 254", planned_codes=["CMPS 251"])["allowed"]


def test_search_ai_electives_excludes_269():
    codes = [c["code"] for c in T.search_courses(T.Session(JUNIOR), tag="ai", only_electives=True)["courses"]]
    assert "CMPS 261" in codes and "CMPS 269" not in codes and "CMPS 260" not in codes


def test_cs_major_cannot_take_ai_for_everyone():
    r = prereqs.check(data.students()[JUNIOR], "CMPS 260")
    assert not r["allowed"] and "not open to Computer Science" in r["reason"]


def test_capstone_needs_senior_standing_and_consent():
    r = prereqs.check(data.students()[JUNIOR], "CMPS 299")
    assert not r["allowed"] and "senior" in r["reason"] and "consent" in r["reason"]


# ---------- Ghina: validator and calendar ----------
def test_validator_accepts_good_plan():
    report = validator.validate_plan(data.students()[JUNIOR], GOOD_PLAN, {"earliest_start": "09:00"})
    assert report["valid"], report["errors"]
    assert report["total_credits"] == 15


def test_validator_catches_conflict_full_and_early():
    bad = ["20881", "20893", "20907"]  # 215s2 full + clashes with 244s1 (MW 12:30); 271s4 starts at 9:00
    report = validator.validate_plan(data.students()[JUNIOR], bad, {"earliest_start": "10:00"})
    text = " ".join(report["errors"])
    assert not report["valid"]
    assert "Time conflict" in text and "full" in text and "before 10:00" in text


def test_validator_rejects_invented_crn():
    assert not validator.validate_plan(data.students()[JUNIOR], ["99999"])["valid"]


def test_export_needs_human_confirmation():
    session = T.Session(JUNIOR)
    T.submit_plan(session, GOOD_PLAN, "test")
    assert "error" in T.export_calendar(session)
    session.student_confirmed = True
    path = T.export_calendar(session)["file"]
    assert open(path).read().startswith("BEGIN:VCALENDAR")


# ---------- Rayane: agent loop and offline mode ----------
def test_parse_request():
    p = parse_request("15 credits, no classes before 9 AM, and one AI-related elective")
    assert p == {"target_credits": 15, "earliest_start": "09:00", "tag": "ai", "avoid_days": []}


def test_offline_plan_is_valid():
    session, answer = plan_offline(JUNIOR, "15 credits, no classes before 9 AM, one AI elective", lambda *a: None)
    assert session.approved_plan and "CMPS 261" in answer


class FakeLLM:
    """Pretends to be the model: replays a fixed list of answers."""

    def __init__(self, script):
        self.script = list(script)

    def chat(self, messages, tools):
        return self.script.pop(0)


def _call(name, args, i):
    return NS(id=f"call_{i}", function=NS(name=name, arguments=json.dumps(args)))


def test_agent_loop_fixes_validator_errors():
    script = [
        NS(content="Loading the record.", tool_calls=[_call("get_student_record", {}, 1)]),
        NS(content=None, tool_calls=[_call("submit_plan", {"crns": ["20881", "20893"], "explanation": "x"}, 2)]),
        NS(content="Conflict, switching section.", tool_calls=[_call("submit_plan", {"crns": GOOD_PLAN, "explanation": "x"}, 3)]),
        NS(content="Here is your plan. Do you confirm this plan?", tool_calls=None),
    ]
    events = []
    agent = PathFinderAgent(JUNIOR, FakeLLM(script), on_event=lambda k, p: events.append((k, p)))
    answer = agent.ask("plan my spring")
    assert "confirm" in answer
    results = [p["result"] for k, p in events if k == "tool_result" and p["name"] == "submit_plan"]
    assert results[0]["valid"] is False and results[1]["valid"] is True
    assert agent.session.approved_plan is not None
