# FILE: remedy.py (The Executioner Edition)
# ROLE: A surgical tool that executes precise commands from The Judge.

import json
from config import log
from api_manager import generate_step_strict

def fix_article_content(current_html, audit_report, topic, iteration=1):
    log(f"   外科医 [The Executioner] Round {iteration} | Executing Surgical Orders...")
    
    orders = audit_report.get('surgical_orders', [])
    if not orders:
        log("      ✅ No surgical orders received. Execution complete.")
        return current_html

    # We build one massive prompt to execute all orders in one go.
    # This gives the AI full context to avoid breaking the HTML.

    prompt = f"""
    MANDATORY INSTRUCTION: YOU ARE AN EXECUTIONER, NOT A THINKER. FOLLOW ORDERS EXACTLY.
    
    ROLE: You are "The Executioner", a hyper-precise HTML editor. Your only job is to execute the surgical orders from "The Judge".
    
    CURRENT HTML:
    {current_html}
    
    SURGICAL ORDERS:
    {json.dumps(orders, indent=2)}

    ---
    EXECUTION PROTOCOL:
    ---
    1.  **READ EACH ORDER:** For each `order_id` in the `SURGICAL ORDERS` list:
    2.  **EXECUTE THE SEARCH:** The `execution_command` will contain a "SEARCH" directive. Use Google Search with that exact query.
    3.  **EXECUTE THE EXTRACTION:** The command will have an "EXTRACT" directive. Find that specific piece of information from your search results.
    4.  **EXECUTE THE INTEGRATION:** The command will have an "INTEGRATE" directive. Surgically modify the `CURRENT HTML` to insert the extracted evidence at the specified location, with the specified formatting (e.g., new H3, bold text, citations).
    5.  **PRESERVE EVERYTHING ELSE:** Do NOT touch any part of the HTML that is not mentioned in an order. All existing images, links, tables, and code blocks MUST remain untouched.
    
    FINAL OUTPUT:
    Return the complete, modified HTML after executing ALL orders.
    
    OUTPUT JSON ONLY:
    {{
        "fixed_html": "The full HTML code after all surgical modifications."
    }}
    """
    
    try:
        result = generate_step_strict(
            "gemini-2.5-flash",
            prompt, 
            "The Executioner: Applying Fixes", 
            required_keys=["fixed_html"],
            use_google_search=True 
        )
        return result.get('fixed_html')
        
    except Exception as e:
        log(f"      ❌ The Executioner Failed: {e}")
        return None
