# FILE: api_manager.py
# DESCRIPTION: Manages all interactions with the Gemini API, including key rotation,
#              model discovery, and robust, self-healing API calls.

import os
import time
import json
import logging
import regex
import json_repair
from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log
from config import log

# Global state for model management
TRIED_MODELS = set()
CURRENT_MODEL_OVERRIDE = None

class KeyManager:
    """
    Manages a pool of API keys, rotating them on failure.
    """
    def __init__(self):
        self.keys = []
        for i in range(1, 11):
            k = os.getenv(f'GEMINI_API_KEY_{i}')
            if k: self.keys.append(k)
        if not self.keys:
            k = os.getenv('GEMINI_API_KEY')
            if k: self.keys.append(k)
        self.current_index = 0
        log(f"🔑 Loaded {len(self.keys)} API Keys.")

    def get_current_key(self):
        if not self.keys: return None
        return self.keys[self.current_index]

    def switch_key(self):
        if self.current_index < len(self.keys) - 1:
            self.current_index += 1
            log(f"   🔄 Switching to Key #{self.current_index + 1}...")
            return True
        log("   ⚠️ All keys exhausted. Resetting to Key #1 for Model Switch...")
        self.current_index = 0
        return False

key_manager = KeyManager()

logger = logging.getLogger("RetryEngine")
logger.setLevel(logging.INFO)

class JSONValidationError(Exception): pass
class JSONParsingError(Exception): pass

STRICT_SYSTEM_PROMPT = """
You are an assistant that MUST return ONLY the exact output requested. 
No explanations, no headings, no extra text, no apologies. 
Output exactly and only what the user asked for. 
If the user requests JSON, return PURE JSON. 
Obey safety policy.
"""

def master_json_parser(text):
    if not text: return None
    match = regex.search(r'\{(?:[^{}]|(?R))*\}', text, regex.DOTALL)
    candidate = match.group(0) if match else text
    try:
        decoded = json_repair.repair_json(candidate, return_objects=True)
        if isinstance(decoded, (dict, list)): return decoded
    except: pass
    try:
        clean = candidate.replace("```json", "").replace("```", "").strip()
        return json.loads(clean)
    except: return None

def validate_structure(data, required_keys):
    if not isinstance(data, dict):
        raise JSONValidationError(f"Expected Dictionary output, but got type: {type(data)}")
    missing_keys = [key for key in required_keys if key not in data]
    if missing_keys:
        raise JSONValidationError(f"JSON is valid but missing required keys: {missing_keys}")
    return True

def discover_fresh_model(current_model_name):
    """Finds a new model when the current one fails on all keys."""
    global CURRENT_MODEL_OVERRIDE
    log(f"   🕵️‍♂️ Discovery Mode: Finding replacement for {current_model_name}...")
    TRIED_MODELS.add(current_model_name.replace('models/', ''))
    
    key = key_manager.get_current_key()
    client = genai.Client(api_key=key)
    
    candidates = []
    try:
        for m in client.models.list():
            m_name = m.name.replace('models/', '')
            if 'gemini' in m_name and 'embedding' not in m_name:
                if m_name not in TRIED_MODELS:
                    candidates.append(m_name)
    except Exception as e:
        log(f"   ⚠️ Listing models failed: {e}")

    priority_list = [
        "gemini-3-flash-preview", 
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash-exp",
        "gemini-1.5-flash"
    ]
    
    final_choice = None
    for p in priority_list:
        if p in candidates and p not in TRIED_MODELS:
            final_choice = p
            break
        if not candidates and p not in TRIED_MODELS:
            final_choice = p
            break
            
    if final_choice:
        log(f"   💡 New Model Selected: {final_choice}")
        CURRENT_MODEL_OVERRIDE = final_choice 
        return final_choice
    
    log("   ❌ Fatal: No untried models left.")
    return None

# FILE: api_manager.py

# ... (باقي الكود في الملف: imports, KeyManager, etc. يبقى كما هو) ...

# --- DYNAMIC HEAT MANAGEMENT SYSTEM ---
# Global variable to track API "health". Higher value = more cooldown.
API_HEAT = 5  # Start with a safe 5-second cooldown

@retry(
    stop=stop_after_attempt(15), 
    wait=wait_exponential(multiplier=2.5, min=5, max=90), # Increased max wait time
    retry=retry_if_exception_type(Exception), 
    before_sleep=before_sleep_log(logger, logging.WARNING)
)
def generate_step_strict(initial_model_name, prompt, step_name, required_keys=[]):
    """
    An intelligent, self-healing function for making Gemini API calls.
    Features: Dynamic cooldown, granular error handling, and robust JSON repair.
    """
    global API_HEAT
    
    # --- Model Selection ---
    # The global override (from model discovery) has the highest priority.
    model_to_use = (CURRENT_MODEL_OVERRIDE if CURRENT_MODEL_OVERRIDE else initial_model_name).replace("models/", "") 
    
    log(f"   🔄 [Tenacity] Executing: {step_name} | Model: {model_to_use}")
    
    # --- Key Selection ---
    key = key_manager.get_current_key()
    if not key: 
        raise RuntimeError("FATAL: All API Keys have been exhausted.")
    
    client = genai.Client(api_key=key)
    
    try:
        # 1. Proactive Cooling (Dynamic Heat Management)
        # The system cools down before every request based on recent server health.
        if API_HEAT > 0:
            log(f"      🌡️ API Heat is at {API_HEAT}s. Cooling down...")
            time.sleep(API_HEAT) 
        
        # --- API Call ---
        generation_config = types.GenerateContentConfig(
            response_mime_type="application/json", 
            system_instruction=STRICT_SYSTEM_PROMPT, 
            temperature=0.3, 
            top_p=0.8
        )

        request_options = {"timeout": 300} # انتظر حتى 5 دقائق للرد
        
        response = client.models.generate_content(
            model=model_to_use, 
            contents=prompt, 
            config=generation_config,
            request_options=request_options
            
    
        )
        
        # --- Robust Parsing & Repair ---
        if not response.text:
            log(f"      ❌ CRITICAL: API returned an empty response for {step_name}. Retrying.")
            raise JSONParsingError("API returned an empty response.")

        parsed_data = master_json_parser(response.text)
        
        if not parsed_data:
            log(f"      ⚠️ Parsing failed. Triggering AI-powered repair...")
            time.sleep(2) # Brief pause before repair call
            repair_response = client.models.generate_content(
                model=model_to_use, 
                contents=f"CRITICAL: Fix the following broken JSON syntax:\n{response.text[:5000]}", 
                config=generation_config
            )
            parsed_data = master_json_parser(repair_response.text)
            
            if not parsed_data:
                log(f"      ❌ CRITICAL: AI Repair failed for {step_name}. Forcing full retry.")
                raise JSONParsingError(f"Failed to parse JSON for {step_name} even after repair attempt.")

        if required_keys: 
            validate_structure(parsed_data, required_keys)
        
        # 2. SUCCESS: Cool down the system
        # On success, we reduce the cooldown period for the next call.
        API_HEAT = max(5, API_HEAT // 2) 
        log(f"      ✅ Success: {step_name} completed. API Heat reduced to {API_HEAT}s.")
        return parsed_data

    except Exception as e:
        error_msg = str(e).lower()
        
        # --- Granular Error Handling ---
        is_quota_or_permission_error = "429" in error_msg or "quota" in error_msg or "403" in error_msg
        is_server_overload_error = "503" in error_msg or "overloaded" in error_msg
        is_model_not_found_error = "404" in error_msg or "not found" in error_msg
        
        if is_quota_or_permission_error:
            # Action: Switch Key. If all keys fail, switch model.
            log(f"      ⚠️ Key-specific Error on Key #{key_manager.current_index + 1}. Switching key...")
            if not key_manager.switch_key():
                log(f"      ⛔ Model {model_to_use} failed on ALL keys. Switching model...")
                time.sleep(20) 
                new_model = discover_fresh_model(model_to_use)
                if not new_model: 
                    raise RuntimeError("FATAL: All models failed. Cannot continue.")
            raise e # Re-raise for Tenacity to retry with the new key/model
        
        elif is_server_overload_error:
            # Action: Increase heat and wait. Do NOT switch key.
            API_HEAT = min(90, API_HEAT + 15) # Drastically increase heat, cap at 90s
            log(f"      🔥 Server Overload (503). API Heat increased to {API_HEAT}s. Waiting for exponential backoff.")
            raise e # Re-raise for Tenacity to wait and retry with the same key
        
        elif is_model_not_found_error:
             # Action: Switch Model immediately.
             log(f"      ❌ Model {model_to_use} NOT FOUND. Switching immediately.")
             discover_fresh_model(model_to_use)
             raise e # Re-raise for Tenacity to retry with the new model
             
        else:
            # Action: For any other error (e.g., parsing), just let Tenacity handle the retry.
            log(f"      ❌ General Error for {step_name}: {str(e)[:200]}")
            raise e
