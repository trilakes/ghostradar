import os
import json
from openai import OpenAI
from pydantic import BaseModel

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# ── Pydantic schema for structured output ─────────────────

class HiddenSignal(BaseModel):
    title: str
    detail: str

class Replies(BaseModel):
    soft_confident: str
    playful: str
    direct: str

class ScanResult(BaseModel):
    interest_score: int
    red_flag_risk: int
    emotional_distance: int
    ghost_probability: int
    reply_window: str
    confidence: str
    hidden_signals_count: int
    hidden_signals: list[HiddenSignal]
    archetype: str
    summary: str
    replies: Replies


SYSTEM_PROMPT = """You are GhostRadar, an AI that analyzes text messages for social/romantic signals.

RULES:
- Return JSON matching the exact schema provided.
- Use probabilistic language only: "likely", "suggests", "indicates", "pattern resembles".
- NEVER claim certainty. NEVER diagnose mental health conditions. NEVER use words like "narcissist" or "toxic".
- Instead of labels, say "pattern resembles avoidant communication" etc.
- Be dramatic and engaging but responsible.
- Scores are 0-100 integers.
- hidden_signals_count should be 1-5 signals detected.
- archetype must be one of: "Hot/Cold", "Avoidant-Leaning", "Anxious-Leaning", "Direct Communicator", "Unclear Pattern"
- confidence must be one of: "Low", "Medium", "High"
- reply_window should be a range like "Likely 1-3 hours" or "Likely 6-12 hours" or "Likely 1-2 days"
- summary should be 1-2 dramatic sentences using probabilistic language.
- Each reply option should be a suggested response message (1-2 sentences)."""


def analyze_message(message_text: str, direction: str = "they") -> dict:
    """Call OpenAI Responses API with structured output to analyze a message."""
    direction_label = "sent by someone to the user" if direction == "they" else "sent by the user to someone"

    user_prompt = f"""Analyze this message that was {direction_label}:

\"\"\"{message_text}\"\"\"

Provide dramatic but probabilistic signal analysis. Be engaging and slightly suspenseful in the summary.
Detect hidden communication patterns, estimate ghost probability, and generate reply suggestions."""

    response = client.responses.parse(
        model="gpt-4o-mini",
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        text_format=ScanResult,
    )

    result = response.output_parsed
    if result is None:
        raise ValueError("AI refused to analyze this message.")

    return result.model_dump()
