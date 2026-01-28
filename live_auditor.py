# FILE: live_auditor.py
# ROLE: Post-Publication Quality Assurance with Progressive Strictness.
# MECHANISM: As iterations increase, Temperature decreases -> 0.0 (Absolute Fact/Logic Mode).

import json
from google import genai
from google.genai import types
from config import log
from api_manager import key_manager

def audit_live_article(url, config, iteration=1):
    """
    Visits the live URL and acts as a Google Search Quality Rater.
    Strictness increases with every iteration.
    """
    # Dynamic Temperature: Starts at 0.25, drops to 0.0 by round 3
    # Round 1 (0.25): Good for general checking.
    # Round 2 (0.10): Very strict.
    # Round 3 (0.00): Robotic precision, zero tolerance.
    current_temp = max(0.0, 0.35 - (iteration * 0.12))
    
    # Dynamic Persona based on iteration
    if iteration == 1:
        persona = "You are a Google Search Quality Rater."
        tone = "Be objective and critical."
    elif iteration == 2:
        persona = "You are a Senior Editor-in-Chief known for firing writers who make mistakes."
        tone = "Be HARSH. No compliments. Focus ONLY on flaws, logic gaps, and missing sources."
    else:
        persona = "You are a Logical Fact-Checking Algorithm (Zero Emotion)."
        tone = "EXTREME SCRUTINY. Verify every number, date, and claim against live web search. Detect hallucination."

    log(f"   ⚖️ [Live Auditor] Round {iteration} | Temp: {current_temp:.2f} | Visiting: {url}...")
    
    key = key_manager.get_current_key()
    if not key: return None

    client = genai.Client(api_key=key)
    google_tool = types.Tool(google_search=types.GoogleSearch())

    prompt = f"""
    ROLE: {persona}
    TASK: Audit this LIVE article URL: {url}
    TONE INSTRUCTION: {tone}
    
    GOAL: Ensure this article ranks #1. It must be Flawless.
    
    CHECKLIST FOR NEUTRALITY AND QUALITY:
    1. **Factual Accuracy:** Cross-reference specific model names (e.g. Figure 01 vs 02), specs, and prices with Google Search.
    2. **Unbiased Tone:** Does the article sound like an ad? If yes, flag it. It must be neutral journalism.
    3. **Evidence:** Are there real screenshots described? Are sources linked properly?
    4. **Formatting:** Is the HTML broken?
    
    OUTPUT JSON:
    {{
        "quality_score": 0.0 to 10.0 (Be stingy),
        "verdict": "Pass/Fail",
        "critical_issues": ["List of specific fatal errors"],
        "correction_plan": "Step-by-step technical instructions to fix the HTML text. Exact replacements."
    }}
    """

    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[google_tool], 
                temperature=current_temp 
            )
        )
        
        # --- التعديل الجذري هنا ---
        if not response or not response.text:
            log("      ⚠️ Auditor received an empty response. Skipping this round.")
            return None

        # تنظيف النص بأمان
        raw = response.text.replace("```json", "").replace("```", "").strip()
        
        # استخدام المفسر الذكي لضمان عدم حدوث خطأ في الـ JSON
        from api_manager import master_json_parser
        result = master_json_parser(raw)
        
        if not result:
            log("      ⚠️ Failed to parse Auditor JSON. Skipping.")
            return None
            
        score = float(result.get('quality_score', 0))
        log(f"      📝 Audit Score (R{iteration}): {score}/10 | Verdict: {result.get('verdict')}")
        
        return result

    except Exception as e:
        log(f"      ⚠️ Auditor Error: {e}")
        return None
