import os

from google import genai
from google.genai import types

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "thinking-land-401107")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
MODEL = os.environ.get("SQL_CHATBOT_MODEL", "gemini-2.5-flash")

_client = genai.Client(vertexai=True, project=PROJECT, location=LOCATION)


def _generate(prompt: str, system_instruction: str | None = None, max_output_tokens: int = 256) -> str:
    response = _client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.0,
            max_output_tokens=max_output_tokens,
            # SQL generation is a short, deterministic transformation task -
            # extended "thinking" adds cost/latency without helping, and (as
            # discovered while testing) its tokens count against
            # max_output_tokens, silently truncating the real answer if the
            # budget is small. Disable it here.
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    if response.candidates and response.candidates[0].finish_reason.name == "MAX_TOKENS" and not response.text:
        raise RuntimeError(
            f"Model response truncated before producing output (finish_reason=MAX_TOKENS, "
            f"max_output_tokens={max_output_tokens})."
        )
    return (response.text or "").strip()


def generate_sql(prompt: str) -> str:
    from prompt import SYSTEM_INSTRUCTION

    text = _generate(prompt, system_instruction=SYSTEM_INSTRUCTION)
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("sql"):
            text = text[3:]
    return text.strip()


def generate_explanation(prompt: str) -> str:
    return _generate(
        prompt,
        system_instruction="You explain query results to a retail analyst in plain English, briefly.",
    )
