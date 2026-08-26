"""
llm_utils.py

Centralizes the text-generation call so content_generator.py,
quiz_generator.py, and evaluator.py all go through one place. Currently
backed by Groq (openai/gpt-oss-20b), which has a far more generous free
daily quota than Gemini's currently gives to new API keys.

Note: embeddings for RAG still go through Gemini (rag_utils.py) -- that
quota is separate and wasn't the problem, so no need to change it.
"""

import os

from groq import Groq
from dotenv import load_dotenv

load_dotenv()

GROQ_MODEL = "openai/gpt-oss-20b"

_client = None


def _get_client():
    global _client

    if _client is None:
        api_key = os.environ.get("GROQ_API_KEY")

        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY not set. Get a free key at console.groq.com and add it to .env"
            )

        _client = Groq(api_key=api_key)

    return _client


def generate_text(prompt, temperature=0.2, max_tokens=4096):
    """Send a single prompt, return the model's text response."""
    client = _get_client()

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except Exception as e:
        raise RuntimeError(f"Groq generation failed: {e}") from e

    if not response.choices:
        raise RuntimeError("Groq returned no response choices.")

    return response.choices[0].message.content or ""