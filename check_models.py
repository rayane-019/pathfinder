from pathfinder.llm import LLMClient

c = LLMClient()
models = ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-flash-latest",
          "gemini-3.1-flash-lite", "gemini-2.5-flash", "gemini-flash-lite-latest"]

for m in models:
    try:
        r = c.client.chat.completions.create(
            model=m, messages=[{"role": "user", "content": "Say hi"}])
        print("WORKS:", m)
    except Exception as e:
        print("FAILS:", m, "->", str(e)[:40])