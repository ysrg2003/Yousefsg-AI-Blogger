# FILE: ai_strategy.py
# ROLE: The strategic brain for query optimization and keyword extraction.
# DESCRIPTION: This module centralizes the logic for converting long, SEO-focused
#              titles into short, effective search queries suitable for platforms
#              like Google News and Reddit.

import re
from typing import Optional

# Project imports
from config import log
from api_manager import generate_step_strict

def _get_core_keywords_from_ai(long_title: str) -> Optional[str]:
    """
    Uses a fast AI model to extract the essential search terms from a long title.
    """
    log("   🤖 [AI Strategy] Using AI to extract core keywords...")
    try:
        prompt = f"""
        ROLE: Search Engine Specialist.
        TASK: From the following long article title, extract only the core product name or technology (2-4 words) that people would actually search for on Reddit or Google News.
        
        RULES:
        - IGNORE descriptive words like "guide", "explained", "review", "how to", "your first steps".
        - FOCUS on the primary, named entity (e.g., "Stable Video Diffusion", "Claude 3.5 Sonnet", "Llama 3").
        
        ARTICLE TITLE: "{long_title}"
        
        OUTPUT JSON ONLY:
        {{
            "core_keywords": "the short, searchable phrase"
        }}
        """
        result = generate_step_strict("gemini-2.5-flash", prompt, "Core Keyword Extraction", ["core_keywords"])
        return result.get('core_keywords')
    except Exception as e:
        log(f"      ⚠️ AI keyword extraction failed: {e}")
        return None

def _get_core_keywords_heuristic(long_title: str) -> str:
    """
    A simple, rule-based fallback to extract keywords if the AI fails.
    It splits the title by common delimiters and takes the most relevant part.
    """
    log("    B [AI Strategy] AI failed, using heuristic keyword extraction...")
    # Split by the most common title delimiters
    parts = re.split(r':|\||-', long_title)
    # The most important part is almost always the first one
    core_part = parts[0].strip()
    # As a safeguard, limit to the first 5 words
    return " ".join(core_part.split()[:5])

def generate_smart_query(long_keyword: str) -> str:
    """
    The main orchestrator function.
    Tries the AI method first, then falls back to a simple heuristic.
    Returns the best possible short query for searching.
    """
    # Tier 1: AI Keyword Extraction
    smart_query = _get_core_keywords_from_ai(long_keyword)

    # Tier 2: Heuristic Fallback
    if not smart_query:
        smart_query = _get_core_keywords_heuristic(long_keyword)
        
    log(f"   ✨ Generated Smart Query: '{smart_query}'")
    return smart_query
