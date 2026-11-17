"""One-time helper: updates the CRNs in tests/test_pathfinder.py to the real Spring 2026-27 sections.
Run once with:  py update_test_crns.py   (keeps every other test, including Lana's)."""
from pathlib import Path

path = Path(__file__).parent / "tests" / "test_pathfinder.py"
text = path.read_text(encoding="utf-8")
changes = [
    ('GOOD_PLAN = ["21049", "21070", "21168", "21133", "21140"]',
     'GOOD_PLAN = ["20880", "20886", "20904", "20900+20899", "20893"]'),
    ('bad = ["21049", "21126", "21161", "21063"]  # 215s2+261s1 clash, 271s1 full, 240s1 at 8:00',
     'bad = ["20881", "20893", "20907"]  # 215s2 full + clashes with 244s1 (MW 12:30); 271s4 starts at 9:00'),
    ('report = validator.validate_plan(data.students()[JUNIOR], bad, {"earliest_start": "09:00"})',
     'report = validator.validate_plan(data.students()[JUNIOR], bad, {"earliest_start": "10:00"})'),
    ('assert "Time conflict" in text and "full" in text and "before 09:00" in text',
     'assert "Time conflict" in text and "full" in text and "before 10:00" in text'),
    ('{"crns": ["21049", "21126"], "explanation": "x"}', '{"crns": ["20881", "20893"], "explanation": "x"}'),
]
for old, new in changes:
    if old in text:
        text = text.replace(old, new); print("updated:", new[:60])
    else:
        print("NOT FOUND (check by hand):", old[:60])
path.write_text(text, encoding="utf-8")
