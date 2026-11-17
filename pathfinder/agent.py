"""The agent loop (owner: Rayane).

  Goal -> Plan -> Act (call a tool) -> Observe (read the result) -> Check -> repeat

The LLM does the thinking and decides which tool to call.
Our code runs the tool and gives the result back.
The loop stops when the model answers without calling a tool, or after MAX_STEPS.
"""
import json

from . import tools as T

MAX_STEPS = 20

SYSTEM_PROMPT = """You are PathFinder, an AI agent that plans a semester for students at the
American University of Beirut (AUB), Department of Computer Science.

How AUB works (use these words):
- Courses have codes like "CMPS 261". Sections have a CRN. Students register on AUBsis.
- Days are written M T W R F. R means Thursday.
- Many CMPS courses need at least a C+ in CMPS 202 (or CMPS 201). The tools check this.
- CMPS 260 and CMPS 269 do NOT count as CMPS electives for CS majors.
- CS majors can claim focus areas: Systems, AI and Data Science, Software Engineering.

Your method:
1. Call get_student_record first.
2. Make a short plan: required courses first, then electives that fit the student's goal and focus area.
3. Use check_prerequisites before choosing a course. Never pick a course the student cannot take.
4. Use find_sections and check_conflicts to build a timetable. Respect every constraint the student gives
   (credits, earliest start time, free days). Skip full sections.
5. Call submit_plan. If the validator returns errors, fix them and submit again.
6. When the plan is approved, show it to the student as a table (course, title, CRN, days, time, room),
   explain each choice in one simple sentence, mention any warnings, and ask: "Do you confirm this plan?"
7. Call export_calendar ONLY after the student says they confirm.

Rules:
- Only use courses and sections returned by the tools. Never invent a course, CRN, time or rule.
- You never register the student. You only plan; the student registers on AUBsis.
- If something is impossible (for example no section fits), say so and offer the closest option.
- Stay on course planning. Politely decline unrelated requests.
- Use short, simple English."""


def _short(obj, limit=400):
    text = json.dumps(obj, ensure_ascii=False)
    return text if len(text) <= limit else text[:limit] + " ..."


def print_event(kind, payload):
    """Default logger: prints each step so the audience can follow the agent."""
    icons = {"tool_call": "->", "tool_result": "<-", "thinking": "..", "final": "==", "error": "!!"}
    if kind == "tool_call":
        print(f"  {icons[kind]} {payload['name']}({_short(payload['args'], 200)})")
    elif kind == "tool_result":
        print(f"  {icons[kind]} {_short(payload['result'])}")
    elif kind == "thinking":
        print(f"  {icons[kind]} {payload['text']}")
    elif kind == "error":
        print(f"  {icons[kind]} {payload['text']}")


class PathFinderAgent:
    def __init__(self, student_id, llm, on_event=print_event, max_steps=MAX_STEPS):
        self.session = T.Session(student_id)
        self.llm = llm
        self.on_event = on_event
        self.max_steps = max_steps
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    def ask(self, user_text):
        """Send one student message and run the loop until the agent answers."""
        self.messages.append({"role": "user", "content": user_text})
        return self._loop()

    def confirm(self):
        """The HUMAN confirms. Only this unlocks export_calendar."""
        if self.session.approved_plan is None:
            return "There is no approved plan to confirm yet."
        self.session.student_confirmed = True
        return self.ask("I confirm this plan. Please export it to my calendar.")

    def _loop(self):
        for step in range(1, self.max_steps + 1):
            message = self.llm.chat(self.messages, T.TOOL_SCHEMAS)
            tool_calls = getattr(message, "tool_calls", None) or []


            # Save the model's turn in the conversation history (its memory).
            # We keep the WHOLE message: Gemini 3 adds a hidden "thought_signature"
            # to each tool call and returns a 400 error if we don't send it back.
            if hasattr(message, "model_dump"):
                entry = message.model_dump(exclude_none=True)
                entry["role"] = "assistant"
                entry.setdefault("content", "")
            else:  # the FakeLLM in the tests
                entry = {"role": "assistant", "content": message.content or ""}
                if tool_calls:
                    entry["tool_calls"] = [{"id": tc.id, "type": "function",
                                            "function": {"name": tc.function.name,
                                                         "arguments": tc.function.arguments}}
                                           for tc in tool_calls]
            self.messages.append(entry)
            if not tool_calls:  # no tool to call: this is the answer to the student
                self.on_event("final", {"text": message.content or "", "step": step})
                return message.content or ""

            if message.content:
                self.on_event("thinking", {"text": message.content})

            # ACT + OBSERVE: run each tool the model asked for.
            for tc in tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args, result = {}, {"error": "arguments were not valid JSON"}
                else:
                    self.on_event("tool_call", {"name": tc.function.name, "args": args})
                    result = T.run_tool(self.session, tc.function.name, args)
                self.on_event("tool_result", {"name": tc.function.name, "result": result})
                self.messages.append({"role": "tool", "tool_call_id": tc.id,
                                      "content": json.dumps(result, ensure_ascii=False)})

        text = (f"I stopped after {self.max_steps} steps without a final plan. "
                "Please try again with fewer constraints.")
        self.on_event("error", {"text": text})
        return text
