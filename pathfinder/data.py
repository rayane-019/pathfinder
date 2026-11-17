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


@lru_cache(maxsize=None)
def courses():
    """Dict: course code -> course info."""
    return {c["code"]: c for c in _load("courses.json")["courses"]}


@lru_cache(maxsize=None)
def sections():
    """Dict: CRN -> section info."""
    return {s["crn"]: s for s in _load("sections.json")["sections"]}


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
    letters = "".join(ch for ch in code if ch.isalpha())
    rest = code[len(letters):]
    return f"{letters} {rest}" if letters and rest else code
