# FILE: deep_dive_researcher.py
# ROLE: The Elite Investigator executing the high-value source acquisition protocol.

import json
from config import log
from api_manager import generate_step_strict

# البرومبت المتقدم الذي طلبته، تم وضعه هنا كنص ثابت
PROMPT_DEEP_DIVE = """
use grounding with Google search and URL context, get your response just from grounding with Google search,get {topic} official resources name and its direct link, mention the page name with its direct link , mention the latest official resources and documents and at least 4 official document and 3 researches and 3 persons experience  and 3 independent_critiques with their prov ,but they must be Very high value and from high value source or website.

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
  {
    "source_name": "Name of the independent publication (e.g., a competitor's blog, an industry analysis site)",
    "page_name": "Title of the critical article or review",
    "url": "Direct link to the critique",
    "summary": "A brief summary of the main counter-argument, weakness, or alternative perspective identified."
  }
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
            PROMPT_DEEP_DIVE.format(topic=topic),
            "Deep Dive Research",
            required_keys=["official_sources", "research_studies", "personal_experiences"],
            use_google_search=True
        )
        
        # التحقق من جودة النتائج
        if (len(result.get("official_sources", [])) < 2 or 
            len(result.get("research_studies", [])) < 1 or
            len(result.get("personal_experiences", [])) < 1):
            log("   ⚠️ Deep Dive returned insufficient sources. Results may be partial.")
        
        log("   ✅ Deep Dive research completed successfully.")
        return result

    except Exception as e:
        log(f"   ❌ CRITICAL: Deep Dive research failed: {e}")
        return None
