"""Connects to the LLM (owner: Rayane).

We use the OpenAI-compatible "chat completions" format, which many providers support.
Pick a provider in .env:
  PATHFINDER_PROVIDER=gemini   (free key from Google AI Studio)
  PATHFINDER_PROVIDER=openai
  PATHFINDER_PROVIDER=groq
Never write the API key in the code. It stays in .env, which git ignores.

Reliability: at start-up we "ping" the models in order and keep the first one
that answers. If Google says a model is busy (503), we move to the next one.
"""
import os

PROVIDERS = {
    "gemini": {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
               "models": ["gemini-3.1-flash-lite", "gemini-flash-lite-latest", "gemini-3.5-flash-lite",
                          "gemini-3.6-flash", "gemini-3.8-flash"]},
    "openai": {"base_url": None, "models": ["gpt-4o-mini"]},
    "groq": {"base_url": "https://api.groq.com/openai/v1", "models": ["llama-3.3-70b-versatile"]},
}


def _load_env():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass


class LLMClient:
    def __init__(self, verbose=True):
        _load_env()
        from openai import OpenAI

        provider = os.getenv("PATHFINDER_PROVIDER", "gemini").lower()
        preset = PROVIDERS.get(provider, PROVIDERS["gemini"])
        api_key = os.getenv("PATHFINDER_API_KEY")
        if not api_key:
            raise RuntimeError("No API key. Copy .env.example to .env and set PATHFINDER_API_KEY "
                               "(or run with --offline).")
        # max_retries: the SDK waits and tries again by itself on 429/5xx errors.
        self.client = OpenAI(api_key=api_key, max_retries=2, timeout=60,
                             base_url=os.getenv("PATHFINDER_BASE_URL", preset["base_url"]))

        # The model from .env first, then the backups (no duplicates).
        candidates = [m for m in [os.getenv("PATHFINDER_MODEL")] if m] + preset["models"]
        self.model = self._pick_model(list(dict.fromkeys(candidates)), verbose)

    def _pick_model(self, candidates, verbose):
        """Try each model with a tiny message and keep the first one that answers."""
        for model in candidates:
            try:
                self.client.with_options(max_retries=1).chat.completions.create(
                    model=model, messages=[{"role": "user", "content": "Say OK"}])
                if verbose:
                    print(f"  [model: {model}]")
                return model
            except Exception as e:  # busy (503), not found (404), quota (429)...
                if verbose:
                    print(f"  [model {model} unavailable: {str(e)[:40]}... trying the next one]")
        raise RuntimeError("No AI model is available right now.")

    def chat(self, messages, tools):
        """One call to the model. Returns its message (text and/or tool calls)."""
        response = self.client.chat.completions.create(
            model=self.model, messages=messages, tools=tools, temperature=0.2)
        return response.choices[0].message


def api_key_present():
    _load_env()
    return bool(os.getenv("PATHFINDER_API_KEY"))
