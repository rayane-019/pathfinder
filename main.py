"""PathFinder command-line demo (owner: Rayane).

  py main.py                      # LLM agent (needs .env with an API key)
  py main.py --offline            # backup mode, no API key needed
  py main.py --student 202400456  # the sophomore with a C in CMPS 202
"""
import argparse

from pathfinder import data
from pathfinder.agent import PathFinderAgent, print_event
from pathfinder import tools as T

EXAMPLE = "I'm a CS junior. Plan my spring with 15 credits, no classes before 9 AM, and one AI-related elective."


def run_offline(student_id, request):
    """Backup planner: same tools, same validator, no AI and no internet."""
    from pathfinder.offline import plan_offline
    session, answer = plan_offline(student_id, request, print_event)
    print("\n" + answer)
    if session.approved_plan and input("\n(y/n) > ").strip().lower().startswith("y"):
        session.student_confirmed = True
        print_event("tool_call", {"name": "export_calendar", "args": {}})
        result = T.run_tool(session, "export_calendar", {})
        print_event("tool_result", {"name": "export_calendar", "result": result})
        print(f"\nSaved your calendar: {result.get('file')}")


def main():
    parser = argparse.ArgumentParser(description="PathFinder: an AI agent that plans your AUB semester")
    parser.add_argument("--student", default="202300123", help="student id from data/students.json")
    parser.add_argument("--offline", action="store_true", help="run without an LLM (backup demo)")
    parser.add_argument("--request", help="the student's request (default: the example from the pitch)")
    args = parser.parse_args()

    student = data.students().get(args.student)
    if not student:
        print("Unknown student id. Options:", ", ".join(data.students()))
        return
    print(f"\nPathFinder | {data.rules()['term']['name']} | {student['name']}\n")
    request = args.request or input("What do you want? (Enter = example)\n> ").strip() or EXAMPLE
    print(f"\nStudent: {request}\n\nAgent log:")

    if args.offline:
        run_offline(args.student, request)
        return

    # Reliability: if no AI model answers, switch to the offline planner instead of crashing.
    try:
        from pathfinder.llm import LLMClient
        agent = PathFinderAgent(args.student, LLMClient())
        answer = agent.ask(request)
    except Exception as e:
        print(f"\n  !! The AI is unavailable ({str(e)[:60]}).")
        print("  !! Switching to offline backup mode (same tools, same validator).\n")
        run_offline(args.student, request)
        return

    print("\n" + answer)
    while True:
        reply = input("\nYou (y = confirm, q = quit, or type a change) > ").strip()
        if reply.lower() in ("q", "quit", "exit", ""):
            break
        try:
            if reply.lower() in ("y", "yes"):
                print("\n" + agent.confirm())
                if agent.session.export_path:
                    print(f"\nSaved your calendar: {agent.session.export_path}")
                break
            print("\n" + agent.ask(reply))
        except Exception as e:
            print(f"\n  !! The AI stopped answering ({str(e)[:60]}). Please try again.")


if __name__ == "__main__":
    main()
