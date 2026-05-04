"""
Utility helpers shared across DSPy agents.
"""

import json
import re


def parse_json_response(text: str, fallback=None):
    """
    Robustly parse JSON from an LLM response.
    
    Handles common issues:
    - Markdown fences (```json ... ```)
    - Leading/trailing whitespace
    - Single-line JSON arrays
    - Trailing commas (non-standard but common in LLM output)
    """
    if not text:
        return fallback if fallback is not None else []
    
    text = text.strip()
    
    # Strip markdown code fences
    if text.startswith("```"):
        # Remove opening fence (with optional language tag)
        text = re.sub(r"^```\w*\n?", "", text)
        # Remove closing fence
        text = re.sub(r"\n?```\s*$", "", text)
        text = text.strip()
    
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # Try removing trailing commas (common LLM error)
    cleaned = re.sub(r",\s*([}\]])", r"\1", text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    
    # Try extracting JSON array from surrounding text
    match = re.search(r"\[[\s\S]*\]", text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    
    # Try extracting JSON object
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    
    # Give up — return the raw text wrapped
    if fallback is not None:
        return fallback
    return [text] if text else []
