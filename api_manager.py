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

TRIED_MODELS = set()
CURRENT_MODEL_OVERRIDE = None
API_HEAT = 30 

class KeyManager:
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
        log("   ⚠️ All keys exhausted. Resetting to Key #1...")
        self.current_index = 0
        return False

# تصدير نسخة واحدة مشتركة
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
        raise JSONValidationError(f"Expected Dictionary, got {type(data)}")
    missing = [k for k in required_keys if k not in data]
    if missing:
        raise JSONValidationError(f"Missing keys: {missing}")
    return True

@retry(
    stop=stop_after_attempt(10), 
    wait=wait_exponential(multiplier=2, min=4, max=60), 
    retry=retry_if_exception_type(Exception), 
    before_sleep=before_sleep_log(logger, logging.WARNING)
)
def generate_step_strict(initial_model_name, prompt, step_name, required_keys=[]):
    global API_HEAT
    model_to_use = (CURRENT_MODEL_OVERRIDE if CURRENT_MODEL_OVERRIDE else initial_model_name).replace("models/", "")
    
    log(f"   🔄 [Tenacity] Executing: {step_name} | Model: {model_to_use}")
    
    key = key_manager.get_current_key()
    if not key: raise RuntimeError("FATAL: No API Keys.")
    
    client = genai.Client(api_key=key)
    
    try:
        if API_HEAT > 0:
            log(f"      🌡️ API Heat is at {API_HEAT}s. Cooling down...")
            time.sleep(API_HEAT)
        
        generation_config = types.GenerateContentConfig(
            response_mime_type="application/json", 
            system_instruction=STRICT_SYSTEM_PROMPT, 
            temperature=0.3
        )
        
        response = client.models.generate_content(
            model=model_to_use, 
            contents=prompt, 
            config=generation_config
        )
        
        if not response.text:
            raise JSONParsingError("Empty response from API.")

        parsed_data = master_json_parser(response.text)
        
        if not parsed_data:
            log(f"      ⚠️ Parsing failed. Triggering AI Repair...")
            repair_resp = client.models.generate_content(
                model="gemini-3-flash-preview", 
                contents=f"Fix this broken JSON:\n{response.text[:5000]}", 
                config=generation_config
            )
            parsed_data = master_json_parser(repair_resp.text)
            if not parsed_data:
                raise JSONParsingError("Repair failed.")

        if required_keys:
            validate_structure(parsed_data, required_keys)
        
        API_HEAT = max(3, API_HEAT - 2)
        log(f"      ✅ Success: {step_name} completed.")
        return parsed_data

    except Exception as e:
        error_msg = str(e).lower()
        if "429" in error_msg or "quota" in error_msg:
            log(f"      ⚠️ Quota Error. Switching Key...")
            if not key_manager.switch_key():
                raise RuntimeError("All keys exhausted.")
            raise e
        elif "503" in error_msg:
            API_HEAT += 30
            raise e
        else:
            log(f"      ❌ Error in {step_name}: {str(e)[:100]}")
            raise e
