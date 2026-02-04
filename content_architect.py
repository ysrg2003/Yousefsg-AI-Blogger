# FILE: content_architect.py
# ROLE: The Master Strategist (The Overlord)
# DESCRIPTION: Analyzes all raw data and produces a hyper-detailed, unbreakable article blueprint.

import json
from config import log
from api_manager import generate_step_strict

# The most important prompt in the entire system.
PROMPT_ARCHITECT_BLUEPRINT = """
ROLE: You are "The Overlord," the Editor-in-Chief of a world-class tech publication (e.g., Stratechery, The Verge). You DO NOT WRITE articles. You create hyper-detailed, bulletproof blueprints for your writers.

TASK: Analyze all the provided data and create a "Master Blueprint" for an article about "{topic}".

RAW DATA BUNDLE:
- Research Data (News, blogs): {research_data}
- Reddit Community Intel: {reddit_context}
- Available Visuals & Code: {visual_context}

---
🧠 PHASE 1: DEEP STRATEGIC ANALYSIS (Internal Reasoning)
---
<thought>
1.  **Identify the Core Narrative:** What is the REAL story here? Is it a funding announcement (boring), or is it about a new technology's impact (interesting)?
2.  **Target Persona & Accessibility:** Who is this for? A developer who needs code? A business owner who needs ROI? Is the product B2B (closed) or B2C (public)? This dictates my entire structure. If it's B2B, a "how-to" guide is dishonest.
3.  **Find the "Golden Nugget":** What is the one piece of information in all this data (a Reddit comment, a specific benchmark number) that will make this article unique and valuable?
4.  **Structure the Argument:** I will design a logical flow (Hook -> Problem -> The Solution (the product) -> The Proof (data/code) -> The Human Element (Reddit) -> The Verdict).
5.  **Assign Evidence:** I will pre-assign every single piece of visual evidence (`[[VISUAL_EVIDENCE_X]]`) and data point to a specific section in my blueprint. No asset will be left unassigned or misplaced.
</thought>

---
✍️ PHASE 2: THE BLUEPRINT (Your Output)
---
Produce a strict JSON object that contains the entire plan.

OUTPUT JSON ONLY:
{{
    "final_title": "A compelling, version-aware, and honest headline based on your analysis.",
    "target_persona": "e.g., 'Python Developer', 'Non-technical Founder', 'AI Hobbyist'",
    "core_narrative": "A one-sentence summary of the article's unique angle.",
    "emotional_hook": "The specific feeling or question the intro must evoke (e.g., 'Is this the end of manual auditing?').",
    "article_blueprint": [
        {{
            "section_type": "H2",
            "title": "Section 1 Title (e.g., The Pitch vs. Reality)",
            "instructions": "Briefly introduce the official claims, then immediately counter with the most relevant Reddit insight.",
            "key_data_to_include": ["Cite the Series C funding amount from the official source.", "Quote u/TechUser from Reddit."],
            "visual_asset_to_place": "null" // or "[[VISUAL_EVIDENCE_1]]"
        }},
        {{
            "section_type": "H2",
            "title": "Section 2 Title (e.g., Performance Benchmarks: The Hard Numbers)",
            "instructions": "Create a quantitative comparison table here. Explain what the numbers mean for the target persona.",
            "key_data_to_include": ["Use the latency data from the research.", "Explain the cost-per-report metric."],
            "visual_asset_to_place": "[[GENERATED_CHART]]"
        }},
        {{
            "section_type": "H2",
            "title": "Section 3 Title (e.g., Getting Started: The Code)",
            "instructions": "Present the code snippet as a practical tool for developers. Explain its function in simple terms. If your analysis found no real code, this section should not be in the blueprint.",
            "key_data_to_include": [],
            "visual_asset_to_place": "[[CODE_SNIPPET_1]]"
        }}
    ],
    "final_verdict_summary": "A one-sentence summary of the final recommendation you want the writer to make."
}}
"""

def create_article_blueprint(topic, research_data, reddit_context, visual_context, model_name):
    log("   🧠 [The Architect] Designing the master article blueprint...")
    
    prompt = PROMPT_ARCHITECT_BLUEPRINT.format(
        topic=topic,
        research_data=research_data[:15000], # Limit context to save tokens
        reddit_context=reddit_context[:5000],
        visual_context=visual_context
    )
    
    try:
        blueprint = generate_step_strict(
            "gemini-2.5-flash", # Must use a powerful thinking model
            prompt,
            "Blueprint Creation",
            required_keys=["final_title", "article_blueprint"]
        )
        log("      ✅ Master blueprint created successfully.")
        return blueprint
    except Exception as e:
        log(f"      ❌ CRITICAL: The Architect failed to create a blueprint: {e}")
        return None
