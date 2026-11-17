"""Loads PathFinder's data files (owner: Lana).

Everything the agent knows about AUB comes from the JSON files in /data.
The model never invents a course: if it is not in these files, it does not exist.
"""
import json
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _load(name):
    with open(DATA_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def _load_optional(name, key):
    """Loads an extra data file if it exists (the GE files), else an empty list."""
    path = DATA_DIR / name
    return _load(name)[key] if path.exists() else []


@lru_cache(maxsize=None)
def courses():
    """Dict: course code -> course info (CMPS catalogue + GE courses)."""
    all_courses = _load("courses.json")["courses"] + _load_optional("ge_courses.json", "courses")
    result = {c["code"]: dict(c) for c in all_courses}
    # Some CMPS courses also count for GE (for example CMPS 269 counts as Humanities I)
    extra = _load("ge_courses.json").get("extra_ge_areas", {}) if (DATA_DIR / "ge_courses.json").exists() else {}
    for code, areas in extra.items():
        if code in result:
            result[code]["ge_areas"] = areas
    return result


@lru_cache(maxsize=None)
def sections():
    """Dict: CRN -> section info (CMPS + GE sections)."""
    all_sections = _load("sections.json")["sections"] + _load_optional("ge_sections.json", "sections")
    return {s["crn"]: s for s in all_sections}


@lru_cache(maxsize=None)
def ge_rules():
    """The GE areas and how many courses each needs."""
    path = DATA_DIR / "ge_courses.json"
    if not path.exists():
        return {"ge_areas": {}, "english_courses": [], "notes": []}
    raw = _load("ge_courses.json")
    return {k: raw[k] for k in ("ge_areas", "english_courses", "notes", "source")}


@lru_cache(maxsize=None)
def students():
    """Dict: student id -> student record."""
    return {s["id"]: s for s in _load("students.json")["students"]}


@lru_cache(maxsize=None)
def rules():
    return _load("rules.json")


def normalize_code(code):
    """'cmps261' or 'CMPS  261' -> 'CMPS 261'."""
    code = "".join(str(code).upper().split())
    i = 0
    while i < len(code) and code[i].isalpha():  # the leading letters only ("CHLA" in "CHLA212A")
        i += 1
    letters, rest = code[:i], code[i:]
    return f"{letters} {rest}" if letters and rest else code
