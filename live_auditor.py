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
    
    # تعريف أداة البحث
    google_tool = types.Tool(google_search=types.GoogleSearch())

    prompt = f"""
    ROLE: Senior Google Search Quality Rater.
    TASK: Visit and Audit this LIVE article: {url}
    TARGET KEYWORD: "{target_keyword}"
    
    INSTRUCTIONS:
    1. Use the Google Search tool to access and read the content of the URL provided.
    2. Evaluate the article based on Google's E-E-A-T standards.
    3. Identify any factual errors, broken formatting, or missing technical details.
    4. Check if the video and images are integrated correctly.

    OUTPUT FORMAT (Return ONLY a JSON object):
    {{
        "quality_score": 0.0 to 10.0,
        "verdict": "Pass/Fail",
        "critical_issues": ["issue 1", "issue 2"],
        "improvement_suggestions": "detailed instructions",
        "missing_facts": ["fact 1", "fact 2"]
    }}
    """

    try:
        # تنفيذ الطلب مع وضع الـ tools داخل الـ config وبدون response_mime_type
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[google_tool],
                temperature=0.1
            )
        )
        
        if not response or not response.text:
            log("      ⚠️ Auditor received an empty response.")
            return None

        # تنظيف النص وتحويله لـ JSON يدوياً باستخدام المفسر الذكي
        result = master_json_parser(response.text)
        
        if result:
            log(f"      📝 Audit Score: {result.get('quality_score')}/10 | Verdict: {result.get('verdict')}")
            return result
        
        return None

    except Exception as e:
        log(f"      ❌ Auditor Error: {e}")
        return None
