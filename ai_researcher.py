# FILE: ai_researcher.py
# ROLE: Elite autonomous agent using Google Grounding for verified, high-quality research.
# CRITICAL FIX (V7.3): Corrected function signature to accept 'mode' argument.
#                      Updated tool name from 'google_search_retrieval' to 'google_search' 
#                      to match the latest Google GenAI library, resolving 400 Bad Request errors.

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
    "msn.com", "aol.com", "yahoo.com", "forbes.com" # Forbes is often paywalled/low-quality
]

def extract_urls_fallback(text):
    """Emergency Regex extractor if JSON parsing fails."""
    url_pattern = re.compile(r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+')
    found = url_pattern.findall(text)
    clean_links = [link for link in found if "google.com" not in link and not any(bad in link for bad in LOW_QUALITY_DOMAINS)]
    return list(set(clean_links))

# --- FIX #1: The function signature now correctly accepts the 'mode' argument ---
def smart_hunt(topic, config, mode="general"):
    """
    The Master Research Function. Uses different prompts based on the research mode.
    """
    # Use a model known for reliable Grounding support
    # Using 1.5-flash as it's stable, fast, and supports the latest tools.
    model_name = "gemini-1.5-flash-latest" 
    
    log(f"   🕵️‍♂️ [AI Researcher] Conducting ({mode}) deep web search for: '{topic}'...")
    
    key = key_manager.get_current_key()
    if not key:
        log("      ❌ API Key Error: No keys available for AI Researcher.")
        return []

    client = genai.Client(api_key=key)
    
    # --- FIX #2: Using the new, correct tool name 'google_search' ---
    # 1. Setup Google Search Tool with the updated name
    search_tool = types.Tool(
        google_search=types.GoogleSearch()
    )

    # 2. Dynamic Prompting based on Mode
    if mode == "visual":
        system_instruction = "You are a Visual Research Specialist. Find direct URLs to pages with visual evidence (Screenshots, Diagrams, Demos)."
        user_prompt = f"Find 3-5 pages containing strong VISUAL EVIDENCE for: '{topic}'. OUTPUT JSON: [{{'type': 'image/video', 'url': '...', 'description': '...'}}]"
    elif mode == "official":
        system_instruction = "You are an Authority Validator. Find ONLY the Official Documentation, GitHub Repository, Whitepaper, or Company Blog."
        user_prompt = f"Find the OFFICIAL source links for: '{topic}'. OUTPUT JSON: [{{'title': 'Official Doc', 'url': '...'}}]"
    else: # "general"
        system_instruction = "You are an Elite Tech Researcher. Find the most authoritative, recent, and factual articles from major tech publications."
        user_prompt = f"Find top 3-5 authoritative sources for: '{topic}'. OUTPUT JSON: [{{'title': 'Article Title', 'link': '...', 'snippet': '...', 'date': '...'}}]"

    # 3. Execution
    try:
        # The modern way to use tools is by getting the model instance first
        model_instance = genai.GenerativeModel(
            model_name=model_name,
            api_key=key,
            system_instruction=system_instruction
        )
        
        response = model_instance.generate_content(
            user_prompt,
            tools=[search_tool],
            generation_config=types.GenerationConfig(
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
                if any(bad in domain for bad in LOW_QUALITY_DOMAINS) or "google.com/search" in url:
                    continue
                
                results.append({
                    "title": item.get('title', 'AI Found Source'),
                    "link": url,
                    "description": item.get('description') or item.get('snippet', 'Relevant Source'),
                    "type": item.get('type', 'article'),
                    "date": item.get('date', 'Recent')
                })
        except json.JSONDecodeError:
            log("      ⚠️ JSON Parsing failed. Falling back to regex extraction...")
            found_links = extract_urls_fallback(raw_text)
            for link in found_links:
                results.append({"title": "AI Discovered (Fallback)", "link": link, "type": "article"})

        if results:
            log(f"      ✅ [AI Researcher] Identified {len(results)} high-quality targets ({mode} mode).")
            return results[:5] 
        else:
            log(f"      ⚠️ AI Researcher found no matching sources for mode: {mode}.")
            return []
    except Exception as e:
        log(f"      ❌ AI Researcher Critical Error: {e}")
        return []
