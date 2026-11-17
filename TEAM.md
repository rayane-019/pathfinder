# Who does what

Each person **owns** a part: understand it well enough to explain it to the judges and answer questions about it.

---

## Rayane: the agent loop (the "brain")

**Files:** `pathfinder/agent.py`, `pathfinder/llm.py`, `pathfinder/offline.py`, `main.py`

**What it does:**
1. Sends the conversation + the tool list to the LLM.
2. If the LLM asks for a tool, runs it with `run_tool()` and sends the result back.
3. Repeats until the LLM answers in plain text, or stops after 20 steps.
4. `confirm()` is the only way to unlock `export_calendar`, and only a human can call it.

**Your tasks before the demo:**
- [ ] Get a free Gemini API key, put it in `.env`, run `python main.py` and check the full example works.
- [ ] Read `SYSTEM_PROMPT` in `agent.py`. If the model makes mistakes, improve the prompt.
- [ ] Practise the pitch: problem → why an agent → the loop → live demo.

**Judges may ask you:** *"Why not just a chatbot?"* / *"What stops it from looping forever?"* (MAX_STEPS = 20) / *"What if the API fails?"* (offline mode)

---

## Lana: the data and the tools (the "hands")

**Files:** `data/*.json`, `pathfinder/data.py`, `pathfinder/prereqs.py`, `pathfinder/tools.py`

**What it does:**
- `courses.json` has the real AUB CMPS catalogue: codes, titles, credits, prerequisites.
- Prerequisites are written as a small tree (`any`, `all`, `min_grade`, `standing`), and `prereqs.py` checks it and explains why.
- `tools.py` has the 7 tools and their descriptions (`TOOL_SCHEMAS`), which is how the LLM knows what each tool does.

**Your tasks before the demo:**
- [ ] Check `courses.json` against the AUB catalogue (you or a friend in CS can spot mistakes).
- [ ] If you can, make `sections.json` more realistic using the real Spring schedule on AUBsis.
- [ ] Run `python -m pytest -q` after any change to the data.

**Judges may ask you:** *"How does it know CMPS 214 needs a C+ in CMPS 202?"* / *"Can it invent a course?"* (no: only what's in the data)

---

## Ghina: the validator, calendar and web demo (the "safety + face")

**Files:** `pathfinder/validator.py`, `pathfinder/schedule.py`, `pathfinder/calendar_export.py`, `web/`

**What it does:**
- The validator checks every plan: CRNs exist, prerequisites, seats, time conflicts (labs too), credit limit, the student's own rules.
- `calendar_export.py` writes an `.ics` file that opens in Google Calendar or Outlook.
- The web page shows the chat, the weekly timetable and the live agent log.

**Your tasks before the demo:**
- [ ] Run `python web/app.py` and try all three example buttons in both modes.
- [ ] Record the **backup demo video** (screen recording of the web page, about 1 minute).
- [ ] Import the exported `.ics` into your phone calendar and take a screenshot for the slides.

**Judges may ask you:** *"How do you make sure the plan is correct?"* / *"What if the model ignores the rules?"* (the validator rejects the plan, and the model must fix it)

---

## Together (tonight)
1. Everyone: clone the repo, install, and run the tests.
2. Run the full demo once with the LLM, then once with `--offline`.
3. Export the deck as a PDF and submit it on the form.
4. Rehearse: 3-minute pitch + 2-minute demo.
