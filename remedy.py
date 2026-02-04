# FILE: remedy.py (The Executioner - Link Preservation Edition v2.0)
# ROLE: A surgical tool that executes precise commands from The Judge while treating links as sacred.

import json
import re
from config import log
from api_manager import generate_step_strict

def fix_article_content(current_html, audit_report, topic, iteration=1):
    log(f"   外科医 [The Executioner] Round {iteration} | Executing Surgical Orders with Link Preservation Protocol...")
    
    orders = audit_report.get('surgical_orders', [])
    if not orders:
        log("      ✅ No surgical orders received. Execution complete.")
        return current_html

    # --- THE SACRED LINK PRESERVATION PROTOCOL ---
    # 1. We extract all hyperlinks from the current HTML and assign them a unique, unbreakable ID.
    #    Example: <a href="https://example.com">some text</a> -> [[LINK_ID_0]]
    # 2. We send the "sanitized" HTML (without real links) to the AI for editing.
    # 3. We receive the edited HTML from the AI.
    # 4. We replace our unbreakable IDs back with the original, full hyperlink tags.
    # This makes it IMPOSSIBLE for the AI to accidentally delete or modify a link.

    link_map = {}
    link_counter = 0

    def preserve_links(match):
        nonlocal link_counter
        link_tag = match.group(0)
        link_id = f"[[LINK_ID_{link_counter}]]"
        link_map[link_id] = link_tag
        link_counter += 1
        return link_id

    # Find all <a> tags using a robust regex and replace them with our placeholder
    # This regex handles various attributes and content within the <a> tag.
    sanitized_html = re.sub(r'<a\s+(?:[^>]*?\s+)?href="[^"]*".*?<\/a>', preserve_links, current_html, flags=re.IGNORECASE | re.DOTALL)
    
    log(f"      🛡️ Link Preservation: Protected and mapped {len(link_map)} hyperlinks.")

    # We build one massive prompt to execute all orders in one go, using the sanitized HTML.
    prompt = f"""
    MANDATORY INSTRUCTION: YOU ARE AN EXECUTIONER, NOT A THINKER. FOLLOW ORDERS EXACTLY.
    
    ROLE: You are "The Executioner", a hyper-precise HTML editor. Your only job is to execute the surgical orders from "The Judge".
    
    **CRITICAL RULE:** The HTML I am providing has had its hyperlinks (`<a>` tags) replaced with placeholders like `[[LINK_ID_0]]`, `[[LINK_ID_1]]`, etc. YOU MUST NOT DELETE, MODIFY, OR CHANGE THE ORDER of these placeholders. Treat them as unbreakable, sacred text.
    
    SANITIZED HTML (FOR EDITING):
    {sanitized_html}
    
    SURGICAL ORDERS:
    {json.dumps(orders, indent=2)}

    ---
    EXECUTION PROTOCOL:
    ---
    1.  **READ EACH ORDER:** For each `order_id` in the `SURGICAL ORDERS` list:
    2.  **EXECUTE THE SEARCH:** The `execution_command` will contain a "SEARCH" directive. Use Google Search with that exact query.
    3.  **EXECUTE THE EXTRACTION:** The command will have an "EXTRACT" directive. Find that specific piece of information from your search results.
    4.  **EXECUTE THE INTEGRATION:** The command will have an "INTEGRATE" directive. Surgically modify the `SANITIZED HTML` to insert the extracted evidence at the specified location, with the specified formatting (e.g., new H3, bold text, citations).
    5.  **PRESERVE EVERYTHING ELSE:** Do NOT touch any part of the HTML that is not mentioned in an order. All existing images, tables, code blocks, and especially the `[[LINK_ID_X]]` placeholders MUST remain untouched and in their original positions.
    
    FINAL OUTPUT:
    Return the complete, modified HTML after executing ALL orders.
    
    OUTPUT JSON ONLY:
    {{
        "fixed_html": "The full HTML code after all surgical modifications, still containing the [[LINK_ID_X]] placeholders."
    }}
    """
    
    try:
        # Using a powerful model is recommended for this complex task
        result = generate_step_strict(
            "gemini-2.5-flash",
            prompt, 
            "The Executioner: Applying Fixes", 
            required_keys=["fixed_html"],
            use_google_search=True 
        )
        
        fixed_sanitized_html = result.get('fixed_html')
        
        if not fixed_sanitized_html:
            log("      ❌ Executioner returned empty content. Discarding changes.")
            return None

        # --- RESTORE THE SACRED LINKS ---
        restored_html = fixed_sanitized_html
        for link_id, original_tag in link_map.items():
            # Use count=1 to replace only the first instance, preventing errors if ID appears multiple times
            restored_html = restored_html.replace(link_id, original_tag, 1)
            
        # Final check to ensure we didn't lose any links
        original_link_count = len(link_map)
        restored_link_count = restored_html.count('<a href')
        
        if restored_link_count < original_link_count:
            log(f"      ❌ CRITICAL FAILURE: Executioner deleted {original_link_count - restored_link_count} protected links. Discarding all changes.")
            return None # Reject the entire edit if any link was lost.

        log(f"      ✅ Link Restoration: Successfully restored all {restored_link_count} hyperlinks.")
        return restored_html
        
    except Exception as e:
        log(f"      ❌ The Executioner Failed: {e}")
        return None
