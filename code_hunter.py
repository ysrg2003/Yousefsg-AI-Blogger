# FILE: code_hunter.py
# ROLE: Finds practical, verifiable code snippets to enhance E-E-A-T.

from config import log
from api_manager import generate_step_strict

def find_code_snippet(topic: str, model_name: str) -> str | None:
    """
    Searches for a relevant Python code snippet for a given technical topic.
    """
    log(f"   💻 [Code Hunter] Searching for a practical code snippet for: '{topic}'")
    
    # تصحيح الخطأ هنا: إزالة الشرطات المائلة العكسية قبل علامات التنصيص
    prompt = f"""
    ROLE: Senior Developer & Technical Writer.
    TASK: Find or generate a single, practical Python code snippet that demonstrates how to use the core technology mentioned in the topic: "{topic}".

    STRICT REQUIREMENTS:
    1.  **Relevance:** The code MUST be directly related to the topic. For "Gemini 3.0 API", it should show an API call. For "Sora Video Gen", it might show how to call a hypothetical API.
    2.  **Simplicity:** The code should be a clear, "hello world" style example. Easy to copy, paste, and run. It must be self-contained.
    3.  **Correctness:** Use modern, idiomatic Python. Add comments explaining the key parts.
    4.  **Source Priority:** First, search for an official code example from documentation. If none is found, generate a clear, functional example.

    OUTPUT JSON ONLY:
    {{
      "code_found": true/false,
      "snippet_html": "<pre><code class=\\"language-python\\"># Your Python code here...\\nprint('Hello, World!')</code></pre>",
      "explanation": "A brief, one-sentence explanation of what this code does."
    }}
    """
    
    try:
        response = generate_step_strict(
            model_name, 
            prompt, 
            "Code Snippet Hunter",
            required_keys=["code_found", "snippet_html"],
            use_google_search=True # Essential for finding official examples
        )
        
        if response and response.get("code_found"):
            log("      ✅ Found a relevant code snippet.")
            return response.get("snippet_html")
        else:
            log("      ⚠️ No suitable code snippet was found for this topic.")
            return None
            
    except Exception as e:
        log(f"      ❌ Code Hunter crashed: {e}")
        return None
