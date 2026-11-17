"""PathFinder web demo (owner: Ghina).

  python web/app.py      then open http://127.0.0.1:5000

Shows the chat, the live agent log (every tool call), and the weekly timetable.
"""
import sys
import uuid
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pathfinder import data, tools as T  # noqa: E402
from pathfinder.agent import PathFinderAgent  # noqa: E402
from pathfinder.llm import api_key_present  # noqa: E402
from pathfinder.offline import plan_offline  # noqa: E402

app = Flask(__name__)
CONVERSATIONS = {}  # conversation id -> {"agent" or "session", "mode", "student_id"}


def plan_rows(session):
    """The approved plan as rows for the timetable."""
    if not session.approved_plan:
        return None
    rows = []
    for crn in session.approved_plan["crns"]:
        s = data.sections()[crn]
        for m in s["meetings"]:
            rows.append({"course": s["course"], "title": data.courses()[s["course"]]["title"],
                         "crn": crn, "section": s["section"], "type": m["type"], "days": m["days"],
                         "start": m["start"], "end": m["end"], "room": m["room"]})
    return {"rows": rows, "report": session.approved_plan["report"]}


@app.get("/")
def index():
    return render_template("index.html", term=data.rules()["term"]["name"])


@app.get("/api/info")
def info():
    return jsonify({
        "students": [{"id": s["id"], "name": s["name"]} for s in data.students().values()],
        "llm_available": api_key_present(),
        "term": data.rules()["term"]["name"],
    })


@app.post("/api/plan")
def plan():
    body = request.get_json(force=True)
    message = (body.get("message") or "").strip()
    if not message:
        return jsonify({"error": "Empty message"}), 400
    events = []

    def on_event(kind, payload):
        events.append({"kind": kind, **payload})

    conv_id = body.get("conversation_id")
    conv = CONVERSATIONS.get(conv_id)
    if conv is None:
        conv_id = uuid.uuid4().hex
        mode = body.get("mode", "llm")
        if mode == "llm" and not api_key_present():
            mode = "offline"
        conv = {"mode": mode, "student_id": body.get("student_id", "202300123")}
        CONVERSATIONS[conv_id] = conv

    try:
        if conv["mode"] == "offline":
            session, answer = plan_offline(conv["student_id"], message, on_event)
            conv["session"] = session
        else:
            if "agent" not in conv:
                from pathfinder.llm import LLMClient
                conv["agent"] = PathFinderAgent(conv["student_id"], LLMClient(), on_event=on_event)
            agent = conv["agent"]
            agent.on_event = on_event
            answer = agent.ask(message)
            conv["session"] = agent.session
    except Exception as e:  # show the error in the page instead of crashing
        return jsonify({"conversation_id": conv_id, "answer": f"Error: {e}", "events": events, "plan": None})

    return jsonify({"conversation_id": conv_id, "mode": conv["mode"], "answer": answer,
                    "events": events, "plan": plan_rows(conv["session"])})


@app.post("/api/confirm")
def confirm():
    body = request.get_json(force=True)
    conv = CONVERSATIONS.get(body.get("conversation_id"))
    if not conv or not conv.get("session") or not conv["session"].approved_plan:
        return jsonify({"error": "No approved plan to confirm"}), 400
    events = []

    def on_event(kind, payload):
        events.append({"kind": kind, **payload})

    if conv["mode"] == "offline":
        session = conv["session"]
        session.student_confirmed = True  # the human clicked "Confirm"
        on_event("tool_call", {"name": "export_calendar", "args": {}})
        result = T.run_tool(session, "export_calendar", {})
        on_event("tool_result", {"name": "export_calendar", "result": result})
        answer = "Your plan is saved to your calendar file. Register these CRNs on AUBsis."
    else:
        agent = conv["agent"]
        agent.on_event = on_event
        answer = agent.confirm()
        session = agent.session
    return jsonify({"answer": answer, "events": events,
                    "download": f"/download/{session.student_id}" if session.export_path else None})


@app.get("/download/<student_id>")
def download(student_id):
    for conv in CONVERSATIONS.values():
        s = conv.get("session")
        if s and s.student_id == student_id and s.export_path:
            return send_file(s.export_path, as_attachment=True, download_name="aub-spring-plan.ics")
    return "No calendar yet", 404


if __name__ == "__main__":
    app.run(debug=True, port=5000)
