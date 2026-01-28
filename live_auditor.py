# FILE: live_auditor.py
import json
from google import genai
from google.genai import types
from config import log
from api_manager import key_manager, master_json_parser

def audit_live_article(url, target_keyword, iteration=1):
    log(f"   ⚖️ [Live Auditor] Round {iteration} | Visiting: {url}...")
    
    key = key_manager.get_current_key()
    if not key: return None
    client = genai.Client(api_key=key)
    google_tool = types.Tool(google_search=types.GoogleSearch())

    prompt = f"""
    ROLE: Senior Google Search Quality Rater (Strict & Harsh).
    TASK: Visit and Audit this LIVE article: {url}
    TARGET KEYWORD: "{target_keyword}"
    
    CRITICAL INSTRUCTIONS:
    1. Use Google Search tool to access the URL and read its full content.
    2. Check for "Timeline Paradox": Is the info from 2024/2025 while we are in 2026?
    3. Check for "Visual Proof": Are there real images/videos or just text?
    4. Check for "AI Slop": Is the tone generic or expert-level?

    OUTPUT JSON ONLY:
    {{
        "quality_score": 0.0 to 10.0,
        "verdict": "Pass/Fail",
        "critical_flaws": ["List specific logic/factual errors"],
        "remedy_instructions": "Detailed technical guide to fix this article",
        "missing_evidence": ["Specific facts or data to add"]
    }}
    """

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(tools=[google_tool], temperature=0.1)
        )
        
        if not response or not response.text: return None

        result = master_json_parser(response.text)
        if result:
            log(f"      📝 Audit Score: {result.get('quality_score')}/10 | Verdict: {result.get('verdict')}")
            return result
        return None
    except Exception as e:
        log(f"      ❌ Auditor Error: {e}")
        return None
