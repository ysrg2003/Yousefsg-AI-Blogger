# FILE: remedy.py
import json
from api_manager import generate_step_strict
from config import log

def fix_article_content(current_html, audit_report, topic, original_research, iteration=1):
    log(f"   🚑 [Remedy Agent] Surgery Round {iteration}...")
    
    flaws = audit_report.get('critical_flaws', [])
    instructions = audit_report.get('remedy_instructions', '')
    missing_evidence = audit_report.get('missing_evidence', [])

    prompt = f"""
    ROLE: Elite SEO Editor & Content Surgeon.
    TASK: Rewrite the article to fix all flaws and achieve a 10/10 score.
    
    TOPIC: {topic}
    ORIGINAL RESEARCH (The Truth): {original_research[:8000]}
    AUDITOR REPORT: {json.dumps(audit_report)}
    
    CURRENT HTML:
    {current_html}
    
    SURGERY RULES:
    1. Fix all "Timeline" errors using the Original Research.
    2. Inject missing facts naturally.
    3. NEVER remove existing <img> or <iframe> tags.
    4. Improve the human tone and expertise (E-E-A-T).

    OUTPUT: Return ONLY the corrected HTML in a JSON key "fixed_html".
    """
    
    try:
        # نستخدم المفسر الموحد لضمان الجودة
        result = generate_step_strict("gemini-2.5-flash", prompt, "Remedy Surgery", required_keys=["fixed_html"])
        return result.get('fixed_html')
    except Exception as e:
        log(f"      ❌ Remedy Agent Failed: {e}")
        return None
