import json
from api_manager import generate_step_strict
from config import log

def fix_article_content(current_html, audit_report, topic, original_research, iteration=1):
    log(f"   🚑 [Remedy Agent] Surgery Round {iteration}...")
    
    issues = audit_report.get('critical_issues', [])
    suggestions = audit_report.get('improvement_suggestions', '')
    missing_facts = audit_report.get('missing_facts', [])

    prompt = f"""
    ROLE: Elite SEO Editor.
    TASK: Rewrite the article HTML to fix all issues and add missing facts.
    
    TOPIC: {topic}
    ORIGINAL RESEARCH: {original_research[:8000]}
    AUDITOR REPORT: {json.dumps(audit_report)}
    
    CURRENT HTML:
    {current_html}
    
    RULES:
    1. Fix all critical issues.
    2. Add missing facts from the research.
    3. Keep all <img> and <iframe> tags.
    4. Return ONLY the corrected HTML in a JSON key "fixed_html".
    """
    
    try:
        # نستخدم موديل قوي جداً للتصحيح (Gemini 2.0 Flash Exp)
        result = generate_step_strict("gemini-2.0-flash-exp", prompt, "Remedy Surgery", required_keys=["fixed_html"])
        return result.get('fixed_html')
    except Exception as e:
        log(f"      ❌ Remedy Agent Failed: {e}")
        return None
