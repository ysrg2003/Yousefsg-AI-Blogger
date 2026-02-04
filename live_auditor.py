# FILE: live_auditor.py
# ROLE: Level 10 Google Search Quality Rater (The Merciless General)
# VERSION: 5.0 - Strategic E-E-A-T Audit with Hyper-Specific Remedy Commands

import json
import datetime
from config import log
from api_manager import generate_step_strict

# FILE: live_auditor.py (The Judge Edition)
# ... (imports stay the same) ...

def audit_live_article(url, target_keyword, iteration=1):
    log(f"   ⚖️ [The Judge] Round {iteration} | 🚀 VERDICT on '{url}' vs. Page 1...")
    
    today_date = str(datetime.date.today())

    prompt = f"""
    MANDATORY INSTRUCTION: USE GOOGLE SEARCH & THINK STEP-BY-STEP.
    
    ROLE: You are "The Judge", Google's most ruthless E-E-A-T auditor. Your job is to find EVERY reason why an article will FAIL to rank #1.
    
    Article URL Under Audit: {url}
    Target Keyword: {target_keyword}

    ---
    🧠 PHASE 1: JUDGEMENT PROTOCOL (Internal Reasoning)
    ---
    <thought>
    1. **Scan Article:** I will read the content from the URL to understand its claims.
    2. **Identify Top Competitor:** I will search Google for {target_keyword} and analyze the #1 ranked organic result in depth.
    3. **E-E-A-T GAP Analysis:** I will compare my article to the #1 competitor on these 4 pillars:
       - **Experience:** Does the competitor show first-hand usage, unique data, or a real case study?
       - **Expertise:** Does the competitor have a more detailed author bio, cite academic papers, or show complex data analysis?
       - **Authoritativeness:** Is the competitor a globally recognized brand (e.g., Gartner, Forbes, Deloitte)?
       - **Trustworthiness:** Does the competitor have more external citations, transparent data sources, and fewer unsourced claims?
    4. **Generate Surgical Orders:** For each gap found, I will create a hyper-specific, actionable command for the "Executioner" agent. This command must be a "what-if" scenario.
    </thought>

    ---
    ✍️ PHASE 2: THE VERDICT (JSON Output)
    ---
    OUTPUT JSON ONLY:
    {{
        "quality_score": 0.0 to 10.0, // A brutally honest score.
        "is_page_one_ready": false, // Assume 'false' unless it's perfect.
        "top_competitor_url": "URL of the #1 ranked competitor",
        "surgical_orders": [ // A list of precise, executable commands.
            {{
                "order_id": "ORDER_01_EXPERIENCE_INJECTION",
                "problem": "Article is too theoretical. Lacks 'I tried this and...' experience.",
                "competitor_advantage": "The top competitor at example.com includes a section 'Our Test Results' with screenshots and performance metrics.",
                "execution_command": "SEARCH: 'Fieldguide user reviews on G2' OR 'auditor experience with Fieldguide forum'. EXTRACT: Two direct quotes (positive or negative) about using the software. INTEGRATE: these quotes into a new H3 section titled 'Real-World User Feedback', citing the source URL for each quote."
            }},
            {{
                "order_id": "ORDER_02_DATA_VERIFICATION",
                "problem": "The claim '70% automation' is not sourced.",
                "competitor_advantage": "The top competitor links this claim to an official Fieldguide press release.",
                "execution_command": "SEARCH: 'Fieldguide 70% automation press release' OR 'Fieldguide case study data'. FIND: the primary source URL for this number. INTEGRATE: this URL as a hyperlink on the text '70% automation' in the article."
            }}
        ]
    }}
    """

    try:
        result = generate_step_strict(
            "gemini-2.5-flash", 
            prompt, 
            "The Judge: E-E-A-T Verdict", 
            required_keys=["surgical_orders", "quality_score"],
            use_google_search=True 
        )
        return result
    except Exception as e:
        log(f"      ❌ The Judge Failed: {e}")
        return None
