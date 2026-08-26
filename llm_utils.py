"""
llm_utils.py

Centralizes the text-generation call so content_generator.py,
quiz_generator.py, and evaluator.py all go through one place using Groq.
Includes fallback models in case specific endpoints change on Groq.
"""

import os
import streamlit as st
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# Ordered list of Groq models to try (starts with fastest/most popular)
GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "llama3-70b-8192",
    "mixtral-8x7b-32768",
]

_client = None


def _get_client():
    global _client

    if _client is None:
        # Check environment variables first, then Streamlit secrets
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key and hasattr(st, "secrets"):
            api_key = st.secrets.get("GROQ_API_KEY")

        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY not set. Get a free key at console.groq.com and add it to .env or Streamlit Secrets."
            )

        _client = Groq(api_key=api_key)

    return _client


def generate_text(prompt, temperature=0.2, max_tokens=4096):
    """Send a prompt to Groq, trying available models with fallback logic."""
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
            # Catch 404/model_not_found errors and fallback to next model
            last_exception = e
            continue

    raise RuntimeError(f"Groq generation failed across all fallback models: {last_exception}")