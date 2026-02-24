"""HTML renderer for health briefs.

Deterministic node (no LLM call) -- loads a Jinja2 template,
fills it with analysis data, and saves the result to disk.
"""
import json
import os
import re
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup

from config import OUTPUT_DIR
from logger import get_logger

log = get_logger("renderer")

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"

# Patterns for auto-highlighting keywords in rendered text.
# Order matters: earlier patterns match first.
_HIGHLIGHT_PATTERNS = [
    # Dollar amounts: $243,750 or $69,977
    (r'\$[\d,]+(?:\.\d{1,2})?(?:[KMB])?', 'strong'),
    # Percentages: 65%, 27M+
    (r'\d+(?:\.\d+)?[%]', 'strong'),
    # Quantities with units: 27M+ records, 565 job runs, 3 tickets
    (r'\d[\d,.]*[KMB]\+?\s*(?:records|rows|runs|users|items)', 'strong'),
    # Date references: September 2026, 2022 Q1, Q1-Q4
    (r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}', 'strong'),
    (r'\d{4}\s+Q[1-4]', 'strong'),
    # Time periods: 6-9 months, ~12 months, 12 months
    (r'~?\d+(?:-\d+)?\s*months?', 'strong'),
]

# Compile once
_HIGHLIGHT_RE = [(re.compile(p), tag) for p, tag in _HIGHLIGHT_PATTERNS]


def _highlight_keywords(text: str) -> Markup:
    """Wrap dollar amounts, percentages, dates, and time periods in <strong> tags.

    Returns Markup so Jinja2 does not double-escape the HTML.
    """
    # HTML-escape the source text first to prevent XSS
    import html as _html
    escaped = _html.escape(text)

    for pattern, tag in _HIGHLIGHT_RE:
        escaped = pattern.sub(lambda m: f'<{tag}>{m.group(0)}</{tag}>', escaped)

    return Markup(escaped)


def _extract_title(user_prompt: str) -> str:
    """Extract a clean title from the user prompt.

    For --account prompts, returns the account name.
    For open-ended prompts, returns a truncated version.
    """
    # Match "account 'Name'" pattern from --account shortcut
    match = re.search(r"account\s+'([^']+)'", user_prompt)
    if match:
        return match.group(1)
    # Truncate long prompts
    if len(user_prompt) > 80:
        return user_prompt[:77] + "..."
    return user_prompt


def _clean_filename(text: str) -> str:
    """Create a safe filename from text."""
    clean = re.sub(r"[^a-z0-9]+", "_", text.lower())
    return clean[:40].strip("_")


def render_node(state: dict) -> dict:
    """Render analysis JSON to an HTML brief."""
    analysis_str = state.get("analysis", "{}")
    user_prompt = state.get("user_prompt", "Unknown")

    try:
        analysis = json.loads(analysis_str)
    except json.JSONDecodeError:
        analysis = {
            "health_label": "Unknown",
            "health_score": 0,
            "reasoning": "Analysis could not be parsed. Raw output below.",
            "raw_output": analysis_str,
            "signals": [],
            "recommendations": [],
            "risks": [],
            "opportunities": [],
        }

    title = _extract_title(user_prompt)

    # Auto-highlight keywords in text fields
    if analysis.get("reasoning"):
        analysis["reasoning"] = _highlight_keywords(analysis["reasoning"])
    for key in ("recommendations", "risks", "opportunities"):
        if analysis.get(key):
            analysis[key] = [_highlight_keywords(item) for item in analysis[key]]

    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    template = env.get_template("brief.html")

    html = template.render(
        analysis=analysis,
        title=title,
        user_prompt=user_prompt,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S IST"),
    )

    # Save to output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    name_part = _clean_filename(title)
    filepath = f"{OUTPUT_DIR}/{ts}_{name_part}_health_brief.html"

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)

    log.info(f"Brief saved to {filepath}", extra={"node": "renderer"})
    return {"brief_path": filepath}
