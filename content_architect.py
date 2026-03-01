# FILE: content_architect.py
# ROLE: The Master Strategist & Blueprint Creator (The Overlord)
# DESCRIPTION: Analyzes all raw data and produces a hyper-detailed, unbreakable article blueprint to guide the writer.

import json
from config import log, EEAT_GUIDELINES
from api_manager import generate_step_strict
from prompts import PROMPT_ARCHITECT_BLUEPRINT, PROMPT_B_TEMPLATE  # أضفنا استيراد قالب البرومبت للكتابة

def create_article_blueprint(topic, content_type, research_data, reddit_context, visual_context, model_name):
    """
    Orchestrates the creation of the master blueprint by calling the thinking model.
    """
    log("   🧠 [The Architect] Designing the master article blueprint...")
    
    prompt = PROMPT_ARCHITECT_BLUEPRINT.format(
        topic=topic,
        content_type=content_type,
        research_data=research_data[:20000], # Giving it more context
        reddit_context=reddit_context[:8000],
        visual_context=visual_context,
        eeat_guidelines=json.dumps(EEAT_GUIDELINES)
    )
    
    try:
        # We must use a powerful thinking model for this critical step
        blueprint = generate_step_strict(
            "gemini-2.5-flash", 
            prompt,
            "Blueprint Creation",
            required_keys=["final_title", "article_blueprint"]
        )
        log("      ✅ Master blueprint created successfully.")
        return blueprint
    except Exception as e:
        log(f"      ❌ CRITICAL: The Architect failed to create a blueprint: {e}")
        # In case of failure, we can try to build a simpler, failsafe blueprint
        log("      ⚠️ Architect failed. Building a failsafe emergency blueprint.")
        return {
            "final_title": topic,
            "target_persona": "General Tech Enthusiast",
            "core_narrative": f"An overview of the latest news and features regarding {topic}.",
            "emotional_hook": f"What's new with {topic} and why should you care?",
            "article_blueprint": [
                {"section_type": "H2", "title": f"What is {topic}?", "instructions": "Explain the product or technology based on the provided research.", "key_data_to_include": [], "visual_asset_to_place": "[[VISUAL_EVIDENCE_1]]"},
                {"section_type": "H2", "title": "Key Features and Updates", "instructions": "Detail the main features mentioned in the research data.", "key_data_to_include": [], "visual_asset_to_place": "[[VISUAL_EVIDENCE_2]]"},
                {"section_type": "H2", "title": "Final Thoughts", "instructions": "Provide a concluding summary.", "key_data_to_include": [], "visual_asset_to_place": "null"}
            ],
            "final_verdict_summary": "A balanced summary of the product's potential."
        }

def write_article_from_blueprint(blueprint, raw_data_bundle, collected_assets, model_name, eeat_guidelines, forbidden_phrases, boring_keywords):
    """
    Generates the final article HTML from the blueprint and raw data.
    """
    log("   ✍️ [The Artisan] Writing article from blueprint...")

    prompt = PROMPT_B_TEMPLATE.format(
        blueprint_json=json.dumps(blueprint),
        raw_data_bundle=json.dumps(raw_data_bundle),
        eeat_guidelines=json.dumps(eeat_guidelines),
        forbidden_phrases=json.dumps(forbidden_phrases),
        boring_keywords=json.dumps(boring_keywords)
    )

    try:
        article_content = generate_step_strict(
            model_name,
            prompt,
            "Article Writing",
            required_keys=["finalContent"],
            system_instruction=eeat_guidelines
        )
        log("      ✅ Article content generated successfully.")
        # article_content متوقع أن يكون dict؛ نرجع finalContent أو النص كـ fallback
        return article_content.get("finalContent") if isinstance(article_content, dict) else article_content
    except Exception as e:
        log(f"      ❌ CRITICAL: The Artisan failed to write the article: {e}")
        # إرجاع HTML احتياطي مغلق بشكل صحيح
        return (
            "<h1>Error: Article Generation Failed</h1>"
            "<p>Due to a critical error during the article generation process, we were unable to produce the content. "
            "Please try again later or review the system logs for more details.</p>"
        )
