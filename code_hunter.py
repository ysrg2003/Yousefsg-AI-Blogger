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
    Find or generate a single, practical Python code snippet that demonstrates the core API usage for the topic: {topic}. 
    STRICT REQUIREMENTS:
    1.  **API Specificity (CRITICAL):** If the topic involves Google, AWS, or OpenAI, the code MUST use the actual, correct Python SDK (e.g., `google-genai` or `openai` library calls). **Hypothetical or generic API calls (e.g., `api.example.com`) are FORBIDDEN if an official SDK exists.**
    2.  **Relevance:** The code MUST be directly related to the topic's advanced function (e.g., multimodal chat, function calling, batch processing).
    3.  **Simplicity:** The code should be a clear, self-contained example.
    4.  **Output HTML:** Must use a single `<pre><code class=\"language-python\">...</code></pre>`
    5.  **Correctness:** Use modern, idiomatic Python. Add comments explaining the key parts.
    6.  **Source Priority:** First, search for an official code example from documentation.
    7. **DOMAIN SPECIFICITY:** If the topic is about an "Answer Engine" or a "Guide", the code MUST include an explicit example of citation retrieval or limiting the model's knowledge base. If the topic is about "Veo 3.1", the code MUST show how to pass an 'Ingredient Image' URI. The code must be tailored to the core feature.

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
