"""
llm_utils.py

Centralizes text generation using Groq API with updated active models.
"""

import os
import streamlit as st
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# Active Groq models (ordered by preference)
GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "openai/gpt-oss-20b",
    "qwen/qwen3.6-27b",
]

_client = None


def _get_client():
    global _client

    if _client is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key and hasattr(st, "secrets"):
            api_key = st.secrets.get("GROQ_API_KEY")

        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY not set. Add it to your .env file or Streamlit Secrets."
            )

        _client = Groq(api_key=api_key)

    return _client


def generate_text(prompt, temperature=0.2, max_tokens=4096):
    """Send a prompt to Groq, falling back to supported active models if needed."""
    client = _get_client()
    last_exception = None

    for model_name in GROQ_MODELS:
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if response.choices and response.choices[0].message.content:
                return response.choices[0].message.content.strip()
        except Exception as e:
            last_exception = e
            continue

    raise RuntimeError(
        f"Groq generation failed across all active fallback models: {last_exception}"
    )