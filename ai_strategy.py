# FILE: ai_strategy.py
# ROLE: The strategic brain for query optimization and keyword extraction.
# DESCRIPTION: This module centralizes the logic for converting long, SEO-focused
#              titles into effective search queries.
#              UPDATED: Now supports a "Graduated Search Plan" (Specific -> Contextual -> Broad).

import re
from typing import Optional, List

# Project imports
from config import log, EEAT_GUIDELINES
from api_manager import generate_step_strict

def _get_core_keywords_from_ai(long_title: str) -> Optional[str]:
    """
    Legacy function: Uses AI to extract a single core keyword (Broad).
    Used by News Fetcher.
    """
    try:
        prompt = f"""
        ROLE: Search Engine Specialist.
        TASK: Extract the primary entity (Product Name or Technology) from this title.
        ---
        mandatory requirement: 
        ---
        1. use a grounding with Google search 
        2. use URL context 
        TITLE: {long_title}
        OUTPUT JSON: {{ "core_keywords": "Search Phrase" }}
        """
        result = generate_step_strict("gemini-2.5-flash", prompt, "Core Keyword Extraction", ["core_keywords"])
        return result.get('core_keywords')
    except:
        return None

def _get_core_keywords_heuristic(long_title: str) -> str:
    """Fallback heuristic extractor."""
    parts = re.split(r':|\||-', long_title)
    return " ".join(parts[0].strip().split()[:5])

def generate_smart_query(long_keyword: str) -> str:
    """
    Returns a single best-guess query (Backward compatibility for News Fetcher).
    """
    smart = _get_core_keywords_from_ai(long_keyword)
    return smart if smart else _get_core_keywords_heuristic(long_keyword)

def generate_multi_perspective_queries(target_keyword: str) -> List[str]:
    """
    Generates 5 distinct search queries to capture different perspectives:
    Official, Academic/Technical, Community/User Experience, Competitor/Comparison, and Future/Trend.
    """
    log(f"   🧠 [AI Strategy] Generating Multi-Perspective Research Plan for: {target_keyword}")
    
    prompt = f"""
    ROLE: Senior Research Architect.
    TASK: Design a 5-point search strategy to gather 360-degree information about: "{target_keyword}"
    
    GOAL: Ensure the final article has "Information Gain" (unique value) and is NOT just a rewrite of top results.
    
    REQUIRED PERSPECTIVES:
    1. **Official & Technical Documentation:** Find the primary source (Whitepapers, API docs, Official blogs).
    2. **Expert Critiques & Deep Dives:** Find independent technical reviews or architectural analyses.
    3. **Community Friction & Real-World Usage:** Find Reddit/StackOverflow discussions about bugs, limitations, or "gotchas".
    4. **Market Context & Alternatives:** Find how it compares to the #1 competitor and what users are switching from.
    5. **Future Impact & Predictions:** Find expert opinions on how this technology will evolve in 12-24 months.

    E-E-A-T GUIDELINES: {EEAT_GUIDELINES}

    OUTPUT JSON ONLY:
    {{
        "research_queries": [
            "Official/Technical Query",
            "Expert Critique Query",
            "Community Discussion Query",
            "Market Comparison Query",
            "Future Trend Query"
        ]
    }}
    """
    
    try:
        result = generate_step_strict(
            "gemini-2.5-flash", 
            prompt, 
            "Multi-Perspective Research", 
            ["research_queries"],
            system_instruction=EEAT_GUIDELINES
        )
        return result.get("research_queries", [target_keyword])
    except Exception as e:
        log(f"      ⚠️ Multi-perspective query generation failed: {e}")
        return [target_keyword, f"{target_keyword} review", f"{target_keyword} vs"]

# ==============================================================================
# NEW: GRADUATED SEARCH PLANNER
# ==============================================================================

def generate_graduated_search_plan(long_title: str) -> List[str]:
    """
    Generates a list of 3 queries ranging from Specific to Broad.
    This allows the Reddit Manager to 'drill down' or 'zoom out' as needed.
    """
    log("   🤖 [AI Strategy] Designing a graduated search plan (Specific -> Broad)...")
    
    try:
        prompt = f"""
        ROLE: Expert Reddit Researcher.
        TASK: Create 3 distinct search queries to find discussions about the following article title on Reddit.
        
        ARTICLE TITLE: {long_title}
            ---
            mandatory requirement: 
            ---
            1. use a grounding with Google search 
            2. use URL context 
        REQUIREMENTS:
        1. **Query 1 (Specific):** Focus on the specific version, update, or feature mentioned. (e.g., "Stable Video Diffusion 1.1" or "GPT-4o voice mode").
        2. **Query 2 (Contextual):** Focus on the problem or comparison. (e.g., "SVD vs Runway" or "GPT-4o latency").
        3. **Query 3 (Broad):** The main product/technology name only. (e.g., "Stable Video Diffusion" or "GPT-4o").
        
        OUTPUT JSON ONLY:
        {{
            "queries": [
                "Specific Query",
                "Contextual Query",
                "Broad Query"
            ]
        }}
        """
        
        result = generate_step_strict("gemini-2.5-flash", prompt, "Search Plan Gen", ["queries"])
        queries = result.get('queries', [])
        
        # Validation: Ensure we have a list of strings
        if isinstance(queries, list) and len(queries) > 0:
            clean_queries = [q for q in queries if q and isinstance(q, str)]
            log(f"      📋 Plan created: {clean_queries}")
            return clean_queries
            
    except Exception as e:
        log(f"      ⚠️ Search plan generation failed: {e}")

    # Fallback if AI fails: [Original Title, First Half of Title, Broad Heuristic]
    heuristic = _get_core_keywords_heuristic(long_title)
    fallback_plan = [
        long_title,                     # Very Specific
        long_title.split(':')[0],       # Contextual
        heuristic                       # Broad
    ]
    return fallback_plan
