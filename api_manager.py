# FILE: api_manager.py
# ROLE: Advanced AI Orchestrator (Hybrid Waterfall Strategy)
# STRATEGY: Puter.js (Claude/GPT) -> Gemini 2.0 -> Gemini 1.5 Pro -> Gemini Flash
# DESCRIPTION: Ensures the highest quality model is always used, degrading gracefully only on failure.
# FEATURES: Key Rotation, Self-Healing JSON, Multi-Provider Redundancy.

import os
import time
import json
import logging
import regex
import json_repair
import puter as puter_sdk
from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log
from config import log

# --- CONFIGURATION ---
API_HEAT = 30  # Seconds to wait between heavy calls to prevent flooding

# 1. Primary Engine (The Best Writer available via Puter)
PUTER_MODEL = "claude-3-5-sonnet" 

# 2. Google Gemini Fallback Chain (Ordered from Strongest/Smartest to Fastest/Cheapest)
GEMINI_FALLBACK_CHAIN = [
    "gemini-3-flash-preview",   # Best reasoning capabilities
    "gemini-2.5-flash-lite,  # Best context handling
    "gemini-2.5-flash",       # Balanced performance
    "gemini-robotics-er-1.5-preview"        # Reliable fallback
]

class KeyManager:
    def __init__(self):
        self.keys = []
        # Load up to 10 keys for rotation from Environment Variables
        for i in range(1, 11):
            k = os.getenv(f'GEMINI_API_KEY_{i}')
            if k: self.keys.append(k)
        # Load legacy single key if exists
        if not self.keys:
            k = os.getenv('GEMINI_API_KEY')
            if k: self.keys.append(k)
            
        self.current_index = 0
        log(f"🔑 Loaded {len(self.keys)} Gemini API Keys.")

    def get_current_key(self):
        if not self.keys: return None
        return self.keys[self.current_index]

    def switch_key(self):
        if self.current_index < len(self.keys) - 1:
            self.current_index += 1
            log(f"   🔄 Switching to Gemini Key #{self.current_index + 1}...")
            return True
        log("   ⚠️ All Gemini keys exhausted. Resetting to Key #1 (Looping)...")
        self.current_index = 0
        return False

# Singleton Instance
key_manager = KeyManager()

# Logging Setup
logger = logging.getLogger("RetryEngine")
logger.setLevel(logging.INFO)

# Custom Exceptions
class JSONValidationError(Exception): pass
class JSONParsingError(Exception): pass

# System Prompt for strict format adherence
STRICT_SYSTEM_PROMPT = """
You are an assistant that MUST return ONLY the exact output requested. 
No explanations, no headings, no extra text, no apologies. 
Output exactly and only what the user asked for. 
If the user requests JSON, return PURE JSON. 
Obey safety policy.
"""

def master_json_parser(text):
    """
    Robust JSON extraction: Handles Markdown blocks, raw text, and minor syntax errors.
    """
    if not text: return None
    
    # Clean Markdown wrappers
    clean_text = text.replace("```json", "").replace("```", "").strip()
    
    # Regex to extract the first JSON object/array
    match = regex.search(r'\{(?:[^{}]|(?R))*\}|\[(?:[^\[\]]|(?R))*\]', clean_text, regex.DOTALL)
    candidate = match.group(0) if match else clean_text
    
    # Attempt 1: json_repair (Best for minor syntax errors like trailing commas)
    try:
        decoded = json_repair.repair_json(candidate, return_objects=True)
        if isinstance(decoded, (dict, list)): return decoded
    except: pass
    
    # Attempt 2: Standard JSON load
    try:
        return json.loads(candidate)
    except: return None

def validate_structure(data, required_keys):
    """
    Ensures the JSON contains necessary fields.
    """
    if not isinstance(data, dict):
        raise JSONValidationError(f"Expected Dictionary, got {type(data)}")
    
    missing = [k for k in required_keys if k not in data]
    if missing:
        raise JSONValidationError(f"Missing keys: {missing}")
    return True

# ==============================================================================
# ENGINE 1: PUTER.JS (PRIMARY / TIER 1)
# ==============================================================================
def try_puter_generation(prompt, system_prompt):
    """
    Attempts to generate content using Puter.js (Accessing Claude/GPT).
    """
    try:
        # log(f"   ⚡ Attempting Tier 1: Puter.js ({PUTER_MODEL})...")
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        # Puter SDK call
        response = puter_sdk.ai.chat(
            messages=messages,
            model=PUTER_MODEL,
            stream=False
        )
        
        # Robustly handle Puter response structure
        text = ""
        if hasattr(response, 'message') and hasattr(response.message, 'content'):
            text = response.message.content
        elif isinstance(response, str):
            text = response
        else:
            text = str(response)

        if not text: return None
        
        parsed = master_json_parser(text)
        if parsed:
            return parsed
        else:
            log("      ⚠️ Puter returned content but JSON parsing failed.")
            return None

    except Exception as e:
        # Silently failover to Gemini (Uncomment log for debugging)
        # log(f"      ⚠️ Puter.js Skipped: {str(e)[:100]}")
        return None

# ==============================================================================
# ENGINE 2: GOOGLE GEMINI (BACKUP / TIERS 2-5) - UPDATED WITH INTERNET ACCESS
# ==============================================================================
def try_gemini_generation(model_name, prompt, system_prompt, use_google_search=False):
    """
    Attempts to generate using a specific Gemini model.
    Handles Key Rotation, Self-Repair, and API Errors.
    INTEGRATED: Google Search Grounding (Internet Access) - Follows ai_researcher.py logic.
    """
    model_slug = model_name.replace("models/", "")
    
    # 1. Acquire Key and Client
    key = key_manager.get_current_key()
    if not key: 
        raise RuntimeError("FATAL: No Gemini API Keys available in KeyManager.")
    
    client = genai.Client(api_key=key)
    
    try:
        # 2. Dynamic Tool & Config Selection
        # NOTE: When tools are enabled, response_mime_type must be None to avoid API conflict
        google_tools = None
        current_mime_type = "application/json"
        
        if use_google_search:
            # Activate the 'Radar' - Real-time Google Search access
            google_tools = [types.Tool(google_search=types.GoogleSearch())]
            current_mime_type = None # Disable strict JSON mode at API level to allow Tools
            # log(f"      📡 [Internet Access] Enabled for {model_slug}")

        generation_config = types.GenerateContentConfig(
            response_mime_type=current_mime_type, 
            system_instruction=system_prompt, 
            temperature=0.3,
            tools=google_tools
        )
        
        # 3. API Execution
        response = client.models.generate_content(
            model=model_slug, 
            contents=prompt, 
            config=generation_config
        )
        
        if not response or not response.text:
            return None

        # 4. JSON Extraction Logic (Essential when response_mime_type is None)
        parsed_data = master_json_parser(response.text)
        
        # --- SELF-CORRECTION MECHANISM ---
        # If parsing fails (common when Internet Search adds citations/text), ask for repair
        if not parsed_data:
            # log(f"      🔧 [Self-Repair] Attempting to fix non-JSON output from {model_slug}...")
            repair_prompt = f"Extract ONLY the valid JSON from the following text. Remove citations and conversational filler:\n\n{response.text[:8000]}"
            
            # Simple repair config (No tools, strict JSON)
            repair_config = types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1
            )
            
            repair_resp = client.models.generate_content(
                model="gemini-2.5-flash", # Use the fastest/cheapest model for repair
                contents=repair_prompt, 
                config=repair_config
            )
            parsed_data = master_json_parser(repair_resp.text)
            
        return parsed_data

    except Exception as e:
        error_msg = str(e).lower()
        
        # Handle Rate Limits (429) / Quota Exhaustion
        if "429" in error_msg or "quota" in error_msg or "limit" in error_msg:
            log(f"      ⚠️ Quota hit on {model_slug} (Key #{key_manager.current_index + 1}). Rotating...")
            if key_manager.switch_key():
                # Recursive retry with the new key
                return try_gemini_generation(model_name, prompt, system_prompt, use_google_search)
            else:
                log("      ❌ FATAL: All keys exhausted for this model.")
                return None
                
        # Handle Model Not Found (404)
        elif "404" in error_msg or "not found" in error_msg:
             log(f"      ⚠️ Model {model_slug} not found or unsupported by this API key.")
             return None
             
        else:
            log(f"      ❌ API Error on {model_slug}: {str(e)[:100]}")
            return None

# ==============================================================================
# MASTER GENERATOR (ORCHESTRATOR) - UPDATED FOR MULTI-MODE EXECUTION
# ==============================================================================
@retry(
    stop=stop_after_attempt(5), 
    wait=wait_exponential(multiplier=1, min=2, max=10), 
    retry=retry_if_exception_type(Exception), 
    before_sleep=before_sleep_log(logger, logging.DEBUG)
)
def generate_step_strict(initial_model_name, prompt, step_name, required_keys=[], use_google_search=False):
    """
    The Intelligence Hub.
    Flow: Puter (Tier 1 - Only for Non-Search) -> Gemini Chain (Tiers 2-5).
    """
    global API_HEAT
    if API_HEAT > 0: time.sleep(1) # Micro-pause to prevent flooding
    
    log(f"   🔄 Executing: {step_name} {'(with Web Search 🌐)' if use_google_search else ''}")

    # --- TIER 1: PUTER.JS (CLAUDE/GPT) ---
    # Puter.js currently does NOT support Google Search Tools via this SDK.
    # Therefore, we skip Tier 1 if web search is requested.
    if not use_google_search:
        result = try_puter_generation(prompt, STRICT_SYSTEM_PROMPT)
        if result:
            try:
                if required_keys: validate_structure(result, required_keys)
                log(f"      ✅ Success (Source: Puter/Claude).")
                return result
            except JSONValidationError:
                log("      ⚠️ Puter JSON structure invalid. Falling back to Gemini.")
    else:
        # log(f"      ℹ️ Skipping Puter.js (Tier 1) because Web Search is required.")
        pass

    # --- TIER 2-5: GEMINI WATERFALL ---
    # Construct the prioritized list of models
    models_to_try = []
    clean_initial = initial_model_name.replace("models/", "")
    
    if clean_initial in GEMINI_FALLBACK_CHAIN:
        models_to_try.append(clean_initial)
        # Add the rest of the chain, avoiding duplicates
        models_to_try.extend([m for m in GEMINI_FALLBACK_CHAIN if m != clean_initial])
    else:
        models_to_try = GEMINI_FALLBACK_CHAIN

    # Iterate through the chain until one succeeds or all fail
    for model in models_to_try:
        gemini_result = try_gemini_generation(model, prompt, STRICT_SYSTEM_PROMPT, use_google_search)
        
        if gemini_result:
            try:
                # Validation Gate
                if required_keys: validate_structure(gemini_result, required_keys)
                log(f"      ✅ Success (Source: {model}).")
                return gemini_result
            except JSONValidationError as ve:
                log(f"      ⚠️ {model} returned invalid structure: {ve}. Trying next model...")
                continue # Try next model in the waterfall
        
        # If None (API/Auth failure), the loop continues to the next model automatically.

    # If the loop finishes without a return
    raise RuntimeError(f"❌ CRITICAL FAILURE: All AI Models (Puter + Gemini Chain) failed for step: {step_name}")
