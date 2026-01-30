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
    "gemini-2.0-flash-exp",   # Best reasoning capabilities
    "gemini-1.5-pro-latest",  # Best context handling
    "gemini-2.5-flash",       # Balanced performance
    "gemini-1.5-flash"        # Reliable fallback
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
# ENGINE 2: GOOGLE GEMINI (BACKUP / TIERS 2-5)
# ==============================================================================
def try_gemini_generation(model_name, prompt, system_prompt):
    """
    Attempts to generate using a specific Gemini model.
    Handles Key Rotation, Self-Repair, and API Errors.
    """
    model_slug = model_name.replace("models/", "")
    
    key = key_manager.get_current_key()
    if not key: raise RuntimeError("FATAL: No Gemini API Keys.")
    
    client = genai.Client(api_key=key)
    
    try:
        generation_config = types.GenerateContentConfig(
            response_mime_type="application/json", 
            system_instruction=system_prompt, 
            temperature=0.3
        )
        
        response = client.models.generate_content(
            model=model_slug, 
            contents=prompt, 
            config=generation_config
        )
        
        if not response.text:
            return None

        parsed_data = master_json_parser(response.text)
        
        # --- SELF-CORRECTION MECHANISM ---
        # If Gemini returns invalid JSON, ask a fast model to fix it.
        if not parsed_data:
            log(f"      🔧 Repairing broken JSON from {model_slug}...")
            repair_resp = client.models.generate_content(
                model="gemini-2.5-flash", # Use fast model for repair
                contents=f"Fix this broken JSON to be valid (Return ONLY JSON):\n{response.text[:5000]}", 
                config=generation_config
            )
            parsed_data = master_json_parser(repair_resp.text)
            
        return parsed_data

    except Exception as e:
        error_msg = str(e).lower()
        
        # Handle Rate Limits (429) / Quota Exhaustion
        if "429" in error_msg or "quota" in error_msg:
            log(f"      ⚠️ Quota hit on {model_slug}. Rotating key...")
            if key_manager.switch_key():
                # Recursive retry with new key
                return try_gemini_generation(model_name, prompt, system_prompt)
            else:
                return None # All keys died
                
        # Handle Model Not Found (404)
        elif "404" in error_msg or "not found" in error_msg:
             log(f"      ⚠️ Model {model_slug} not found/supported by this key.")
             return None
             
        else:
            log(f"      ❌ Error on {model_slug}: {str(e)[:50]}")
            return None

# ==============================================================================
# MASTER GENERATOR (ORCHESTRATOR)
# ==============================================================================
@retry(
    stop=stop_after_attempt(5), 
    wait=wait_exponential(multiplier=1, min=2, max=10), 
    retry=retry_if_exception_type(Exception), 
    before_sleep=before_sleep_log(logger, logging.DEBUG)
)
def generate_step_strict(initial_model_name, prompt, step_name, required_keys=[]):
    """
    The Intelligence Hub.
    Flow: Puter (Tier 1) -> Gemini Chain (Tiers 2-5).
    """
    global API_HEAT
    if API_HEAT > 0: time.sleep(1) # Micro-pause to ease rate limits
    
    log(f"   🔄 Executing: {step_name}")

    # --- TIER 1: PUTER.JS (CLAUDE/GPT) ---
    # We prioritize this for high-quality writing steps.
    # If it fails, we seamlessly drop to Gemini.
    result = try_puter_generation(prompt, STRICT_SYSTEM_PROMPT)
    if result:
        try:
            if required_keys: validate_structure(result, required_keys)
            log(f"      ✅ Success (Source: Puter/Claude).")
            return result
        except JSONValidationError:
            log("      ⚠️ Puter JSON structure invalid. Falling back to Gemini.")

    # --- TIER 2-5: GEMINI WATERFALL ---
    # Build the list of models to try
    models_to_try = []
    clean_initial = initial_model_name.replace("models/", "")
    
    # If the requested model is valid, try it first
    if clean_initial in GEMINI_FALLBACK_CHAIN:
        models_to_try.append(clean_initial)
        models_to_try.extend([m for m in GEMINI_FALLBACK_CHAIN if m != clean_initial])
    else:
        models_to_try = GEMINI_FALLBACK_CHAIN

    # Iterate through the chain until one succeeds
    for model in models_to_try:
        gemini_result = try_gemini_generation(model, prompt, STRICT_SYSTEM_PROMPT)
        
        if gemini_result:
            try:
                if required_keys: validate_structure(gemini_result, required_keys)
                log(f"      ✅ Success (Source: {model}).")
                return gemini_result
            except JSONValidationError as ve:
                log(f"      ⚠️ {model} returned invalid structure. Trying next model...")
                continue # Try next model in chain
        
        # If None returned (Network/Auth error), loop continues to next model.

    # If all tiers fail
    raise RuntimeError(f"❌ ALL AI MODELS (Puter + Gemini Chain) FAILED for step: {step_name}")
