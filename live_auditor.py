# FILE: live_auditor.py
import json
from config import log
from api_manager import generate_step_strict
import scraper  # سنستخدم السكرابر القوي الموجود لدينا

def audit_live_article(url, target_keyword, iteration=1):
    log(f"   ⚖️ [Live Auditor] Round {iteration} | Visiting: {url}...")
    
    # 1. استخدام السكرابر لجلب المحتوى الحقيقي الذي يراه الزائر
    # نستخدم scraper.resolve_and_scrape لأنه يتعامل مع الجافاسكريبت والتحويلات
    _, _, page_text, _, _ = scraper.resolve_and_scrape(url)
    
    if not page_text or len(page_text) < 500:
        log("      ⚠️ Auditor could not scrape the live page (Content too short or blocked).")
        return None

    # 2. التحليل باستخدام Gemini (بدون Google Tools لتقليل الأخطاء)
    prompt = f"""
    ROLE: Senior Google Search Quality Rater (Strict & Harsh).
    TASK: Audit this LIVE article content.
    TARGET KEYWORD: "{target_keyword}"
    CURRENT DATE: 2026-01-29
    
    ARTICLE CONTENT:
    {page_text[:15000]} 
    
    CRITICAL CHECKS:
    1. **Timeline Paradox:** Does the article mention "Claude 3" as new, while implying it's 2026? Or does it hallucinate "Claude 5"? 
       - Rule: The tech specs MUST match the actual text provided, do not invent versions.
    2. **Visual Proof:** Does the text explicitly refer to images/videos that are MISSING in the content?
    3. **Value:** Is this just fluff?

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
        # نستخدم generate_step_strict الموثوقة بدلاً من استدعاء العميل مباشرة
        result = generate_step_strict("gemini-2.5-flash", prompt, "Live Audit", required_keys=["quality_score", "critical_flaws"])
        
        log(f"      📝 Audit Score: {result.get('quality_score')}/10 | Verdict: {result.get('verdict')}")
        return result
    except Exception as e:
        log(f"      ❌ Auditor Error: {e}")
        return None
