# FILE: code_hunter.py
# ROLE: Finds practical, verified code snippets. 
# STRICT UPDATE: Anti-Hallucination Protocol. Verifies SDK existence before generation.

from config import log
from api_manager import generate_step_strict

def find_code_snippet(topic: str, model_name: str) -> str | None:
    """
    Searches for a RELEVANT and VERIFIED code snippet.
    Now includes a pre-check to ensure the library actually exists.
    """
    log(f"   💻 [Code Hunter] Initiating Strict Search for: '{topic}'")
    
    # 1. PHASE 1: EXISTENCE CHECK (The Firewall)
    # We ask the AI to specifically look for documentation or PyPI packages.
    check_prompt = f"""
    ROLE: Senior Developer & Library Auditor.
    TASK: Verify if a PUBLIC Python SDK or API library exists for the topic: {topic}.

    ---
    mandatory requirement: 
    ---
    1. use a grounding with Google search 
    2. use URL context 
    
    INSTRUCTIONS:
    1. Search for pypi {topic} or {topic} python sdk or {topic} api documentation.
    2. STRICT RULE: Do NOT invent a library. If 'Fieldguide' is a SaaS with no public python package, you MUST return false.
    3. Only return true if there is a documented way to interact with it via code (Requests, LangChain, Official SDK).
    
    OUTPUT JSON ONLY:
    {{
        "exists": true/false,
        "library_name": "name of the real library (e.g. 'google-genai' or 'openai')",
        "documentation_url": "link to docs or pypi"
    }}
    """
    
    try:
        # We enforce Google Search here to verify reality
        check_result = generate_step_strict(
            model_name, 
            check_prompt, 
            "Code Existence Check",
            required_keys=["exists"],
            use_google_search=True 
        )
        
        if not check_result.get("exists"):
            log(f"      ⛔ Code Hunter: No public API/SDK found for '{topic}'. Skipping code generation to prevent hallucination.")
            return None
            
        lib_name = check_result.get("library_name", "standard_library")
        doc_url = check_result.get("documentation_url", "Official Docs")
        log(f"      ✅ Verified Library: {lib_name} ({doc_url})")

    except Exception as e:
        log(f"      ⚠️ Code Existence Check Failed: {e}")
        return None

    # 2. PHASE 2: GENERATION (Only if verified)
    generation_prompt = f"""
    ROLE: Senior Developer.
    TASK: Write a REAL, WORKING Python code snippet for: {topic}.

    ---
    mandatory requirement: 
    ---
    1. use a grounding with Google search 
    2. use URL context 
    
    CONTEXT: You have verified that the library '{lib_name}' exists.
    
    STRICT REQUIREMENTS:
    1.  **Use the ACTUAL library syntax.** Do not hallucinate methods like `.generate_awesome_stuff()`. Use real endpoints.
    2.  **Authentication:** Show where the API Key goes (e.g., `api_key="YOUR_KEY"`).
    3.  **Comments:** Explain what the code does briefly.
    4.  **Output HTML:** Must use a single `<pre><code class=\"language-python\">...</code></pre>` block.
    
    OUTPUT JSON ONLY:
    {{
      "code_found": true,
      "snippet_html": "<pre><code class=\\"language-python\\">import {lib_name}\\n# Real code here...</code></pre>"
    }}
    """
    
    try:
        response = generate_step_strict(
            model_name, 
            generation_prompt, 
            "Code Generation",
            required_keys=["snippet_html"],
            use_google_search=True # Keep search on to find correct syntax
        )
        
        if response and response.get("snippet_html"):
            log("      ✅ Generated verified code snippet.")
            return response.get("snippet_html")
        else:
            return None
            
    except Exception as e:
        log(f"      ❌ Code Generation Crashed: {e}")
        return None
