"""GE tests (General Education). Run with:  py -m pytest -q"""
from pathfinder import data, tools as T
from pathfinder.offline import plan_offline

JUNIOR = "202300123"


def test_ge_courses_loaded():
    assert "PHIL 210" in data.courses() and data.courses()["PHIL 210"]["ge_areas"] == ["humanities_1"]


def test_ge_progress_for_junior():
    areas = T.check_ge_progress(T.Session(JUNIOR))["areas"]
    assert areas["english"]["remaining"] == 0          # ENGL 203 + ENGL 204
    assert areas["social_sciences"]["remaining"] == 0  # ECON 211 + SOAN 201
    assert areas["natural_sciences"]["remaining"] == 2


def test_search_ge_area():
    codes = [c["code"] for c in T.search_courses(T.Session(JUNIOR), ge_area="quantitative")["courses"]]
    assert {"MATH 203", "MATH 204", "STAT 201", "SOAN 211", "CMPS 260"} <= set(codes)


def test_ge_prerequisite_engl_203():
    s = data.students()[JUNIOR]
    assert T.check_prerequisites(T.Session(JUNIOR), ["CHLA 212A"])["results"][0]["allowed"]  # has ENGL 203


def test_offline_plan_with_ge():
    session, answer = plan_offline(JUNIOR, "15 credits, no classes before 9 AM, one AI elective and one GE course",
                                   lambda *a: None)
    codes = {data.sections()[c]["course"] for c in session.approved_plan["crns"]}
    assert any(data.courses()[c].get("ge_areas") for c in codes)


def test_social_inequalities_tag():
    codes = [c["code"] for c in T.search_courses(T.Session(JUNIOR), tag="social_inequalities", limit=40)["courses"]]
    assert "SOAN 201" in codes and "ECON 237" in codes


def test_real_ge_section_times():
    s = data.sections()["23098"]  # SOAN 211, Analysis of Social Data
    assert s["course"] == "SOAN 211" and s["meetings"][0]["days"] == "TR" and s["meetings"][0]["start"] == "09:30"
