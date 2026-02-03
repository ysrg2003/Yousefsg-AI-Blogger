# FILE: live_auditor.py
# ROLE: Strict Google Quality Rater (Actual Live Access)
# DESCRIPTION: Visits the URL via Scraper, verifies content, and judges E-E-A-T & SEO potential.
# UPDATED: Dynamic Date Injection.

import json
import datetime
from config import log
from api_manager import generate_step_strict
import scraper

def audit_live_article(url, target_keyword, iteration=1):
    log(f"   ⚖️ [Live Auditor] Round {iteration} | 🚀 ACTUALLY Visiting: {url}...")
    
    # 1. الوصول الفعلي للمقال (Actual Access)
    # نستخدم السكرابر لجلب النص + الوسائط التي يراها الزائر الحقيقي
    # resolve_and_scrape returns: (url, title, text, image, media_list)
    _, _, page_text, _, media_found = scraper.resolve_and_scrape(url)
    
    if not page_text or len(page_text) < 500:
        log("      ⚠️ Auditor Alert: Could not scrape the live page (Content blocked or empty).")
        return None

    # 2. فحص النظام للأصول (System Check)
    # نساعد الذكاء الاصطناعي: نخبره أننا وجدنا صوراً وفيديو برمجياً، لكي لا يظلم المقال
    has_visuals = len(media_found) > 0
    visual_report = f"✅ DETECTED ({len(media_found)} assets found by Scraper)" if has_visuals else "❌ NOT DETECTED"

    # 3. التاريخ الديناميكي (Dynamic Date)
    today_date = str(datetime.date.today())

    # 4. البرومبت الصارم (The Strict Veteran Expert Prompt)
    prompt = f"""
    ROLE: Strict Veteran Google Search Quality Rater (E-E-A-T Expert).
    TASK: Deep Dive Audit of a LIVE Article (Actual Access).

    I have performed an ACTUAL VISIT to the URL: {url}
    
    Here is the RAW CONTENT I extracted from the page:
    ===================================================
    {page_text[:20000]}
    ===================================================

    METADATA:
    - Target Keyword: {target_keyword}
    - Current Date: {today_date} (CRITICAL: Use this date to judge "Timeline Paradoxes").
    - Visual Assets System Check: {visual_report} (If DETECTED, do NOT complain about missing images).

    YOUR MISSION (AS A STRICT GOOGLE EXPERT):
    1. **EXPLORE & ANALYZE:** Read the content above thoroughly. Do not hallucinate. Judge what is actually there.
    2. **TIMELINE CHECK (CRITICAL):** Today is {today_date}. Does the article speak about old tech as if it's new? Or does it hallucinate future tech? It MUST be consistent with the text provided.
    3. **SEO PREDICTION:** Will this rank on Page 1? Or is it "AI Slop"?
    4. **LINK CHECK:** Does the text mention sources? (Assume links exist if the text cites names like "According to OpenAI").

    OUTPUT JSON ONLY:
    {{
        "quality_score": 0.0 to 10.0,
        "verdict": "Pass/Fail",
        "critical_flaws": ["List ONLY factual/logic/timeline errors. Be specific."],
        "remedy_instructions": "Step-by-step guide to fix the logic/timeline errors.",
        "seo_opinion": "Your honest expert opinion on its ranking potential and how to solve and improve."
    }}
    """

    try:
        # نستخدم generate_step_strict لضمان الحصول على JSON نظيف
        result = generate_step_strict("gemini-2.5-flash", prompt, "Live Audit", required_keys=["quality_score", "critical_flaws"])
        
        score = result.get('quality_score', 0)
        verdict = result.get('verdict', 'Fail')
        seo_op = result.get('seo_opinion', 'No opinion')
        
        log(f"      📝 Audit Score: {score}/10 | Verdict: {verdict}")
        log(f"      🔮 SEO Expert Opinion: {seo_op[:100]}...")
        
        return result
        
    except Exception as e:
        log(f"      ❌ Auditor Error: {e}")
        return None
