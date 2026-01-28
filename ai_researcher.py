# FILE: ai_researcher.py
# ROLE: Elite autonomous agent using Google Grounding for verified, high-quality research.
# FEATURES: 
#   1. Query Decomposition: Breaks down long topics into smart search queries.
#   2. Multi-Mode Research: Can hunt for general news, official docs, or visual evidence.
#   3. Syntactically Correct: Uses the proper method for calling Gemini with Tools.

import json
import re
import time
from google import genai
from google.genai import types
from config import log
from api_manager import key_manager

# Strict blacklist of domains to avoid for authoritative research
LOW_QUALITY_DOMAINS = [
    "reddit.com", "quora.com", "pinterest.com", "linkedin.com", "medium.com", 
    "facebook.com", "instagram.com", "tiktok.com", "vocal.media", "newsbreak.com",
    "msn.com", "aol.com", "yahoo.com", "forbes.com"
]

def extract_urls_fallback(text):
    """Emergency Regex extractor if JSON parsing fails."""
    url_pattern = re.compile(r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+')
    found = url_pattern.findall(text)
    clean_links = [link for link in set(found) if "google.com" not in link and not any(bad in link for bad in LOW_QUALITY_DOMAINS)]
    return clean_links

def generate_search_plan(topic, client, model_name):
    """
    Analyzes the long topic and creates specific, targeted search queries to ensure results.
    """
    log(f"   🧠 [AI Researcher] Analyzing topic to create a search plan...")
    prompt = f"""
    TASK: You are a Search Engine Specialist.
    INPUT TOPIC: "{topic}"
    
    ACTION: Break this long, descriptive topic down into 3 short, effective Google Search Queries.
    
    1. A query for the latest news and reviews (e.g., "DeepSeek R1 review").
    2. A query for official documentation or the company's website (e.g., "DeepSeek official documentation").
    3. A query for finding visual demonstrations or screenshots (e.g., "DeepSeek R1 demo video UI").
    
    OUTPUT JSON format ONLY:
    {{
        "news_query": "...",
        "official_query": "...",
        "visual_query": "..."
    }}
    """
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            generation_config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1)
        )
        return json.loads(response.text)
    except:
        # Simple string manipulation fallback if the AI planner fails
        log("      ⚠️ Search plan generation failed. Using simple keyword extraction.")
        short_topic = " ".join(topic.split()[:4])
        return {
            "news_query": f"{short_topic} review",
            "official_query": f"{short_topic} official website",
            "visual_query": f"{short_topic} demo"
        }

def smart_hunt(topic, config, mode="general"):
    """
    The Master Research Function. It plans, then executes the search.
    """
    # Use a fast, stable model that supports tools reliably
    model_name = "gemini-2.5-flash" 
    
    key = key_manager.get_current_key()
    if not key:
        log("      ❌ API Key Error: No keys available for AI Researcher.")
        return []

    client = genai.Client(api_key=key)
    
    # 1. PLAN THE SEARCH (This solves the "long title" problem)
    search_plan = generate_search_plan(topic, client, model_name)
    
    # Determine which optimized query to use based on the mode
    active_query = search_plan.get("news_query", topic) # Default to news
    if mode == "official":
        active_query = search_plan.get("official_query", topic)
    if mode == "visual":
        active_query = search_plan.get("visual_query", topic)
    
    log(f"   🕵️‍♂️ [AI Researcher] Executing ({mode}) search for: '{active_query}'")

    # 2. Configure Google Search Tool
    google_search_tool = types.Tool(google_search=types.GoogleSearch())

    # 3. Dynamic Prompting based on the optimized query
    if mode == "visual":
        system_instruction = "Find pages with UI screenshots, demos, or graphs. Ignore text-only pages."
        user_prompt = f"Find 3 pages with strong VISUAL EVIDENCE for: '{active_query}'. OUTPUT JSON."
    elif mode == "official":
        system_instruction = "Find ONLY the Official Documentation, GitHub Repository, Whitepaper, or Company Blog."
        user_prompt = f"Find the OFFICIAL source links for: '{active_query}'. OUTPUT JSON."
    else: # "general"
        system_instruction = "Find high-authority, recent articles. BAN forums and social media."
        user_prompt = f"Find top 3 authoritative sources for: '{active_query}'. OUTPUT JSON: [{{'title': '...', 'link': '...'}}]"

    # 4. Execute Search with the CORRECTED SYNTAX
    try:
        
        response = client.models.generate_content(
    model=model_name,
    contents=user_prompt,
    config=types.GenerateContentConfig(  # التعديل هنا: وضع الأدوات داخل الـ config
        tools=[google_search_tool],
        system_instruction=system_instruction,
        response_mime_type="application/json",
        temperature=0.2
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
                # Strict Filtering
                if any(bad in domain for bad in LOW_QUALITY_DOMAINS) or "google.com/search" in url:
                    continue
                
                results.append({
                    "title": item.get('title', 'AI Source'),
                    "link": url,
                    "url": url, # for compatibility
                    "description": item.get('description') or item.get('snippet', 'Source found by AI'),
                    "type": item.get('type', 'article'),
                    "date": "Recent"
                })
        except json.JSONDecodeError:
            log("      ⚠️ JSON Parsing failed. Using Regex fallback.")
            found_links = extract_urls_fallback(raw_text)
            for link in found_links:
                results.append({"title": "AI Source (Fallback)", "link": link, "url": link, "description": "Extracted via regex", "type": "article"})

        if results:
            log(f"      ✅ [AI Researcher] Found {len(results)} valid sources for '{active_query}'.")
            return results
        else:
            log(f"      ⚠️ AI Researcher found 0 sources for '{active_query}'.")
            return []

    except Exception as e:
        log(f"      ❌ AI Researcher CRASHED: {e}")
        return []
