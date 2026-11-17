"""Connects to the LLM (owner: Rayane).

We use the OpenAI-compatible "chat completions" format, which many providers support.
Pick a provider in .env:
  PATHFINDER_PROVIDER=gemini   (free key from Google AI Studio)
  PATHFINDER_PROVIDER=openai
  PATHFINDER_PROVIDER=groq
Never write the API key in the code. It stays in .env, which git ignores.
"""
import os

PROVIDERS = {
    "gemini": {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai/", "model": "gemini-2.5-flash"},
    "openai": {"base_url": None, "model": "gpt-4o-mini"},
    "groq": {"base_url": "https://api.groq.com/openai/v1", "model": "llama-3.3-70b-versatile"},
}


class LLMClient:
    def __init__(self):
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass
        from openai import OpenAI

        provider = os.getenv("PATHFINDER_PROVIDER", "gemini").lower()
        preset = PROVIDERS.get(provider, PROVIDERS["gemini"])
        api_key = os.getenv("PATHFINDER_API_KEY")
        if not api_key:
            raise RuntimeError("No API key. Copy .env.example to .env and set PATHFINDER_API_KEY "
                               "(or run with --offline).")
        self.model = os.getenv("PATHFINDER_MODEL", preset["model"])
        self.client = OpenAI(api_key=api_key, base_url=os.getenv("PATHFINDER_BASE_URL", preset["base_url"]))

    def chat(self, messages, tools):
        """One call to the model. Returns its message (text and/or tool calls)."""
        response = self.client.chat.completions.create(
            model=self.model, messages=messages, tools=tools, temperature=0.2)
        return response.choices[0].message


def api_key_present():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    return bool(os.getenv("PATHFINDER_API_KEY"))
