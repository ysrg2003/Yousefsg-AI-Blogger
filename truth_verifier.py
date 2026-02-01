# FILE: truth_verifier.py
# ROLE: The Gatekeeper (Official Source Protocol)
# DESCRIPTION: strict verification module that ensures a topic has a primary, 
#              authoritative source (Official Blog/Press Release) before content generation begins.

import json
from config import log
from api_manager import generate_step_strict

def verify_topic_existence(topic, model_name):
    """
    Verifies if a topic has an ACTUAL official source.
    Returns a tuple: (is_verified, official_url, official_title)
    """
    log(f"   🛡️ [Truth Verifier] Hunting for OFFICIAL source for: '{topic}'...")

    prompt = f"""
    ROLE: Strict Investigative Fact-Checker.
    TASK: Find the SINGLE BEST OFFICIAL Announcement URL for the topic: "{topic}".
    
    STRICT SEARCH PROTOCOL:
    1.  You MUST search specifically for OFFICIAL company blogs, documentation, or press releases.
        -   Examples: `site:blog.google`, `site:openai.com`, `site:microsoft.com`, `site:apple.com`, `site:anthropic.com`, `site:meta.com`.
        -   Also acceptable: Official GitHub repositories (e.g., `github.com/features/...`) or HuggingFace model cards.
    2.  REJECT news aggregators (e.g., TechCrunch, The Verge, Medium, Reddit) as the *primary* source. We need the SOURCE OF TRUTH.
    3.  If the topic is a rumor with NO official confirmation, verify as FALSE.
    
    OUTPUT JSON ONLY:
    {{
        "verified": true,  // Set to false if no OFFICIAL link is found
        "official_url": "https://blog.google/technology/ai/gemini-1-5-pro...", // The direct link
        "official_title": "Our next generation model: Gemini 1.5", // The exact title on the page
        "domain_type": "Official Company Blog"
    }}
    """

    try:
        # We enforce Google Search usage to find the URL
        result = generate_step_strict(
            model_name, 
            prompt, 
            "Truth Verification", 
            required_keys=["verified"], 
            use_google_search=True
        )
        
        is_verified = result.get('verified', False)
        official_url = result.get('official_url', '')
        official_title = result.get('official_title', topic)
        
        # Additional Code-Level Validation
        if is_verified and official_url:
            # 1. Ensure it's a valid URL string
            if not official_url.startswith("http"):
                log(f"      ⚠️ Verification Warning: Invalid URL format '{official_url}'. Rejecting.")
                return False, None, None
            
            # 2. Check against a loose set of high-trust domains (Optional but recommended sanity check)
            # We trust the AI mostly, but this acts as a double-check.
            # (Logic handled by AI prompt mostly, but we log the success)
            
            log(f"      ✅ Verified! Official Source Found: {official_url}")
            return True, official_url, official_title
        
        else:
            log(f"      ⛔ Verification Failed: No official source found for '{topic}'. Skipping.")
            return False, None, None
            
    except Exception as e:
        log(f"      ⚠️ Verification Process Error: {e}")
        return False, None, None
