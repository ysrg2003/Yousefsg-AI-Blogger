# FILE: remedy.py
# ROLE: The Surgical Fixer. 
# ADAPTATION: Uses lower temperature in later rounds to ensure fixes are precise not creative.

import json
from api_manager import generate_step_strict
from config import log

def fix_article_content(current_html, audit_report, topic, iteration=1):
    """
    Re-writes the HTML content based on the strict critique.
    """
    log(f"   🚑 [Remedy Agent] Surgery Round {iteration}...")
    
    critique = audit_report.get('critical_issues', [])
    correction_plan = audit_report.get('correction_plan', '')
    
    # Stricter model settings for later iterations
    # We want CREATIVITY in round 1 (to write missing parts), but PRECISION in round 3 (to fix numbers).
    strictness_instruction = ""
    if iteration > 1:
        strictness_instruction = "IMPORTANT: Do NOT rewrite the whole article. Only fix the specific reported errors. Keep the rest exact."

    model_name = "gemini-2.5-flash" 
    
    prompt = f"""
    ROLE: Elite Technical Editor & HTML Expert.
    TASK: Apply surgical fixes to the HTML based on the critique.
    
    ORIGINAL TOPIC: {topic}
    CRITIQUE: {json.dumps(critique)}
    INSTRUCTIONS: {correction_plan}
    {strictness_instruction}
    
    INPUT HTML:
    ```html
    {current_html}
    ```
    
    ACTIONS:
    1. Fix factual errors exactly as requested.
    2. Maintain Neutral POV.
    3. Return the FULL CORRECTED HTML string.
    """
    
    try:
        # We assume api_manager handles the call. 
        # Note: generate_step_strict uses temp 0.3 by default. 
        # For Remediation, that is generally okay, but the prompt constraints above will force strictness.
        
        json_prompt = prompt + "\n\nOUTPUT FORMAT JSON: {\"fixed_html\": \"...html...\"}"
        result = generate_step_strict(model_name, json_prompt, "Remedy Surgery", required_keys=["fixed_html"])
        
        fixed_html = result.get('fixed_html')
        if fixed_html and len(fixed_html) > 500:
            return fixed_html
        return None
            
    except Exception as e:
        log(f"      ❌ Remedy Agent Failed: {e}")
        return None
