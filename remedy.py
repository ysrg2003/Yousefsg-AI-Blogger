# FILE: remedy.py
# ROLE: The Strict Surgeon (Code-Aware & Link-Preserving)
# UPDATED: Forces Temperature 0.1 & Protects <a> tags.

import json
import datetime
from google import genai
from google.genai import types
from config import log
from api_manager import key_manager, master_json_parser

def fix_article_content(current_html, audit_report, topic, original_research, iteration=1):
    log(f"   🚑 [Remedy Agent] Surgery Round {iteration} (Temp: 0.1)...")
    
    flaws = audit_report.get('critical_flaws', [])
    instructions = audit_report.get('remedy_instructions', '')
    
    # تاريخ اليوم لضمان عدم الهلوسة الزمنية
    today_date = str(datetime.date.today())

    # الحصول على مفتاح API نشط
    key = key_manager.get_current_key()
    if not key:
        log("      ❌ Remedy Skipped: No API Key available.")
        return None
        
    client = genai.Client(api_key=key)

    prompt = f"""
    ROLE: Expert HTML Editor & Fact-Checker (Code-Aware).
    TASK: Fix specific logical/factual errors in the HTML WITHOUT destroying the existing structure, links, or assets.
    
    CONTEXT:
    - Topic: {topic}
    - Current Date: {today_date}
    - Original Research: {original_research[:5000]}
    - Flaws to Fix: {json.dumps(flaws)}
    - Instructions: {instructions}
    
    CURRENT HTML:
    {current_html}
    
    🛑 STRICT PRESERVATION RULES (NON-NEGOTIABLE):
    1. **LINKS ARE SACRED:** You MUST preserve ALL `<a href="...">` tags exactly as they are. Do NOT remove internal links, external citations, or source links.
    2. **MEDIA PRESERVATION (CRITICAL):** You are FORBIDDEN from deleting or modifying any media asset. Keep all `<img>`, `<iframe>`, `<video>`, and `<div class="video-wrapper">` tags **EXACTLY AS THEY ARE**. If the video is broken, do NOT delete the tag.    3. **CODE BLOCKS:** Keep all `<pre><code>` blocks untouched.
    4. **TIMELINE FIX:** If the text says "Claude 3 is coming" but it's 2026, change the TEXT to "Claude 3 was released...", but DO NOT delete the section.
    5. **MINIMAL INTERVENTION:** Only edit the specific paragraphs that contain the errors. Leave the rest of the code untouched.
    6. **CSS PRESERVATION:** Keep all inline styles (e.g., `style="..."`) and class names.
 

    OUTPUT JSON ONLY:
    {{
        "fixed_html": "The complete HTML code with fixes"
    }}
    """
        
    try:
        # إعدادات التوليد الصارمة (Temperature 0.1)
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.1, # تجميد الإبداع للحفاظ على الكود
            top_p=0.95,
            max_output_tokens=65536
        )

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=config
        )
        
        # تحليل الرد
        result = master_json_parser(response.text)
        if not result: return None
        
        fixed_content = result.get('fixed_html')
        
        if not fixed_content: return None

        # --- شبكة الأمان (Safety Net) ---
        # نتأكد أن الجراح لم يقتل المريض (حذف الروابط أو الفيديو)
        
        # 1. فحص الفيديو
        if "iframe" in current_html and "iframe" not in fixed_content:
            log("      ⚠️ Remedy failed: Video/Iframe was deleted. Discarding changes.")
            return None
            
        # 2. فحص الروابط (نقبل نقصاً بسيطاً ولكن ليس إبادة جماعية)
        original_links_count = current_html.count("<a href")
        new_links_count = fixed_content.count("<a href")
        
        if original_links_count > 0 and new_links_count == 0:
             log(f"      ⚠️ Remedy failed: All {original_links_count} links were deleted. Discarding changes.")
             return None
             
        if new_links_count < (original_links_count * 0.8): # إذا حذف أكثر من 20% من الروابط
             log(f"      ⚠️ Remedy Warning: Significant link loss ({original_links_count} -> {new_links_count}). Proceeding with caution.")

        return fixed_content
        
    except Exception as e:
        log(f"      ❌ Remedy Agent Failed: {e}")
        return None
