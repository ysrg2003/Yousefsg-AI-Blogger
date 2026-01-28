# FILE: ai_researcher.py
# ROLE: Elite autonomous agent using Google Grounding, optimized for Gemini 2.5 Flash.
# FEATURES: Query Decomposition, Multi-Step Research, Strict Filtering, SDK Compatibility.

import json
import re
import time
from google import genai
from google.genai import types
from config import log
from api_manager import generate_step_strict # We will use the main API manager for consistency

# Strict blacklist to ensure high quality sources
LOW_QUALITY_DOMAINS = [
    "reddit.com", "quora.com", "pinterest.com", "linkedin.com", "medium.com", 
    "facebook.com", "instagram.com", "tiktok.com", "vocal.media", "newsbreak.com",
    "msn.com", "aol.com", "yahoo.com", "forbes.com", "blogspot.com", "wordpress.com"
]

def extract_urls_fallback(text):
    """Emergency Regex extractor if JSON parsing fails."""
    url_pattern = re.compile(r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+')
    found = url_pattern.findall(text)
    clean_links = [link for link in set(found) if "google.com" not in link and not any(bad in link for bad in LOW_QUALITY_DOMAINS)]
    return clean_links

def smart_hunt(topic, config, mode="general"):
    """
    The Master Research Function, designed to leverage Gemini 2.5 Flash's capabilities.
    It decomposes the topic into smart queries, then executes a grounded search.
    """
    model_name = "gemini-2.5-flash"  # Focusing on this specific model
    
    # --- 1. DECOMPOSE THE TOPIC INTO SMART QUERIES ---
    # Instead of searching for the long title, we ask the AI to think like a researcher
    # and create short, effective search terms.
    log(f"   🧠 [AI Researcher] Analyzing topic to generate search plan...")
    
    plan_prompt = f"""
    TASK: You are a Search Engine Specialist.
    INPUT TOPIC: "{topic}"
    
    ACTION: Break this topic down into 3 distinct, short Google Search Queries.
    
    1. A query for Official Documentation or the Primary Source.
    2. A query for the Latest News, Reviews, or Analysis.
    3. A query for Visual Evidence like Demos, UI Screenshots, or Charts.
    
    OUTPUT JSON format ONLY:
    {{
        "official_query": "e.g., 'Figure AI official website'",
        "news_query": "e.g., 'Figure AI latest funding news'",
        "visual_query": "e.g., 'Figure 02 robot demo video'"
    }}
    """
    
    try:
        search_plan = generate_step_strict(model_name, plan_prompt, "Search Plan Generation", required_keys=["official_query", "news_query", "visual_query"])
    except Exception as e:
        log(f"      ⚠️ Search Plan generation failed: {e}. Using simple fallback.")
        short_topic = " ".join(topic.split()[:3])
        search_plan = {
            "official_query": f"{short_topic} official site",
            "news_query": f"{short_topic} review",
            "visual_query": f"{short_topic} demo"
        }

    # --- 2. EXECUTE THE SEARCH BASED ON THE 'MODE' ---
    # Select the appropriate query from the generated plan
    if mode == "visual":
        active_query = search_plan["visual_query"]
        system_instruction = "As a Visual Specialist, find pages with UI screenshots, demos, or graphs."
        user_prompt = f"Find 3 pages with strong VISUAL EVIDENCE for: '{active_query}'. OUTPUT JSON."
    elif mode == "official":
        active_query = search_plan["official_query"]
        system_instruction = "As an Authority Validator, find ONLY the Official Documentation, GitHub, or Company Blog."
        user_prompt = f"Find the OFFICIAL source links for: '{active_query}'. OUTPUT JSON."
    else: # "general"
        active_query = search_plan["news_query"]
        system_instruction = "As a Tech Researcher, find high-authority news articles. BAN forums/social media."
        user_prompt = f"Find top 3 authoritative sources for: '{active_query}'. OUTPUT JSON: [{{'title': '...', 'link': '...'}}]"

    log(f"   🕵️‍♂️ [AI Researcher] Executing ({mode}) search for: '{active_query}'...")

    # --- 3. PERFORM THE GROUNDED SEARCH ---
    try:
        # We create a new client instance here to attach the tool correctly
        from api_manager import key_manager
        key = key_manager.get_current_key()
        client = genai.Client(api_key=key)

        search_tool = types.Tool(google_search=types.GoogleSearch())

        # The most stable way to call with tools in the current SDK
        response = client.models.generate_content(
            model=model_name,
            contents=user_prompt,
            tools=[search_tool],
            system_instruction=system_instruction,
            generation_config=types.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.1 # Very low temperature for factual retrieval
            )
        )
        
        raw_text = response.text.replace("```json", "").replace("```", "").strip()
        results = []

        try:
            parsed_data = json.loads(raw_text)
            for item in parsed_data:
                url = item.get('link') or item.get('url')
                if not url: continue
                
                domain = url.split("//")[-1].split("/")[0].lower()
                if any(bad in domain for bad in LOW_QUALITY_DOMAINS) or "google.com/search" in url:
                    continue
                
                results.append({
                    "title": item.get('title', 'AI Found Source'),
                    "link": url,
                    "description": item.get('description') or item.get('snippet', 'Relevant Source'),
                    "type": item.get('type', 'article'),
                    "date": 'Recent'
                })
        except json.JSONDecodeError:
            log("      ⚠️ JSON Parsing failed. Falling back to regex.")
            for link in extract_urls_fallback(raw_text):
                results.append({"title": "AI Discovered (Fallback)", "link": link, "type": "article"})

        if results:
            log(f"      ✅ [AI Researcher] Identified {len(results)} high-quality targets.")
            return results[:3] # Return top 3 for stability
        else:
            log(f"      ⚠️ AI Researcher found no matching sources for mode: {mode}.")
            return []
            
    except Exception as e:
        log(f"      ❌ AI Researcher CRASHED: {e}")
        return []
