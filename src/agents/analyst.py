"""Analyst agent -- single LLM call for health analysis.

Merges the old analyze_health and generate_recommendations nodes into
one structured LLM call that produces a JSON health assessment.
"""
import json

from config import get_llm
from logger import get_logger, track

log = get_logger("analyst")

SYSTEM_PROMPT = """You are a customer success analyst. Analyze the provided customer data and produce a structured JSON response.

Your response MUST be valid JSON with this exact structure:
{
    "health_score": <number 0-100>,
    "health_label": "Green" | "Yellow" | "Red",
    "reasoning": "Brief explanation of the health assessment",
    "signals": [
        {"name": "Signal Name", "value": "value", "impact": "positive" | "negative" | "neutral"}
    ],
    "recommendations": [
        "Recommendation 1",
        "Recommendation 2"
    ],
    "risks": [
        "Risk 1"
    ],
    "opportunities": [
        "Opportunity 1"
    ]
}

Rules:
- health_score 0-39 = Red, 40-69 = Yellow, 70-100 = Green
- Provide 3-5 signals, 3-5 recommendations, 1-3 risks, 1-3 opportunities
- Base your analysis ONLY on the data provided
- Return ONLY valid JSON, no markdown formatting or extra text"""


def analyze_node(state: dict) -> dict:
    """Analyze gathered data and produce structured health assessment."""
    gathered = state.get("gathered_data", "")

    if not gathered:
        return {"analysis": json.dumps({"error": "No data to analyze"})}

    log.info("Analyzing gathered data", extra={"node": "analyst"})

    llm = get_llm(temperature=0)
    track("llm_calls")

    response = llm.invoke([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Analyze this customer data:\n\n{gathered}"},
    ])

    # Strip markdown code blocks if the LLM wrapped the JSON
    content = response.content.strip()
    if content.startswith("```"):
        # Remove opening ```json or ```
        first_newline = content.index("\n")
        content = content[first_newline + 1:]
    if content.endswith("```"):
        content = content[:-3].strip()

    return {"analysis": content}
