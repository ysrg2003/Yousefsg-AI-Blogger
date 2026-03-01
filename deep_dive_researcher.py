# FILE: deep_dive_researcher.py
# ROLE: The Elite Investigator executing the high-value source acquisition protocol.
# FIX: Escaped curly braces for independent_critiques to prevent KeyError.

import json
from config import log, EEAT_GUIDELINES
from api_manager import generate_step_strict

# البرومبت المتقدم مع تصحيح الأقواس (Doubled Curly Braces)
PROMPT_DEEP_DIVE = """
ROLE: Elite Research Investigator.
TASK: Conduct a comprehensive E-E-A-T focused deep dive into: "{topic}"

MANDATORY REQUIREMENTS:
1. **Experience:** Find at least 3 high-value personal experiences or expert reviews (YouTube, X, Professional Blogs).
2. **Expertise:** Find at least 4 official documents, whitepapers, or API documentations.
3. **Authoritativeness:** Find at least 3 academic researches or industry-leading studies (MIT, Gartner, etc.).
4. **Trustworthiness:** Find at least 3 independent critiques or "counter-arguments" to ensure a balanced, trustworthy perspective.

E-E-A-T GUIDELINES: {eeat_guidelines}

Use grounding with Google search and URL context. Get your response ONLY from grounding with Google search. Mention the source name, page name, and direct link for every resource. Every source must be high-value and from a reputable domain.

CRITICAL OUTPUT INSTRUCTION: You MUST return a single valid JSON object. Do not add any text before or after the JSON.

The JSON structure MUST be:
{{
  "official_sources": [
    {{
      "source_name": "Name of the official website (e.g., OpenAI)",
      "page_name": "The exact title of the page or document",
      "url": "The direct link to the resource"
    }}
  ],
  "research_studies": [
    {{
      "source_name": "Name of the research platform (e.g., ArXiv, MIT Technology Review)",
      "page_name": "Title of the research paper or article",
      "url": "The direct link to the study"
    }}
  ],
  "personal_experiences": [
    {{
      "person_name": "Name of the expert (e.g., Casey Neistat, Dr. Jim Fan)",
      "proof": "A brief description of their proof (e.g., YouTube video, X/Twitter thread)",
      "url": "The direct link to the proof"
    }}
  ],
  "independent_critiques": [
    {{
      "source_name": "Name of the independent publication (e.g., a competitor's blog, an industry analysis site)",
      "page_name": "Title of the critical article or review",
      "url": "Direct link to the critique",
      "summary": "A brief summary of the main counter-argument, weakness, or alternative perspective identified."
    }}
  ]
}}
"""

def conduct_deep_dive(topic: str, model_name: str):
    """
    Executes the deep dive research prompt to gather high-value, structured sources.
    """
    log(f"🕵️‍♂️ [Deep Dive Researcher] Initiating high-value source acquisition for: '{topic}'")
    
    try:
        # استدعاء الـ API مع تفعيل البحث الإجباري
        result = generate_step_strict(
            model_name,
            PROMPT_DEEP_DIVE.format(topic=topic, eeat_guidelines=json.dumps(EEAT_GUIDELINES, ensure_ascii=False)),
            "Deep Dive Research",
            # تمت إضافة independent_critiques لقائمة التحقق لضمان وجودها
            required_keys=["official_sources", "research_studies", "personal_experiences", "independent_critiques"],
            use_google_search=True,
            system_instruction=EEAT_GUIDELINES
        )
        
        # التحقق من جودة النتائج
        if (len(result.get("official_sources", [])) < 1 or 
            len(result.get("research_studies", [])) < 1):
            log("   ⚠️ Deep Dive returned insufficient sources. Results may be partial.")
        
        log("   ✅ Deep Dive research completed successfully.")
        return result

    except Exception as e:
        log(f"   ❌ CRITICAL: Deep Dive research failed: {e}")
        return None
