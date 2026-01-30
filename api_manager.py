# FILE: api_manager.py
# ROLE: Advanced AI Orchestrator (GitHub Models Edition)
# STRATEGY: GPT-4o (The King) for everything.
# INFRASTRUCTURE: Microsoft Azure AI via GitHub.

import os
import time
import json
import logging
import regex
import json_repair
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log
from config import log

# --- CONFIGURATION ---
# GitHub Models Endpoint
GITHUB_MODELS_BASE_URL = "https://models.inference.ai.azure.com"

# Models Available on GitHub Marketplace
WRITING_MODEL = "gpt-4o" 
REASONING_MODEL = "gpt-4o" 
FALLBACK_MODEL = "gpt-4o-mini" # Very fast and cheap/free limits

class KeyManager:
    def __init__(self):
        # We use the GITHUB_TOKEN directly.
        # In GitHub Actions, this is usually passed as an env var.
        # You need to create a Personal Access Token (PAT) and put it in secrets as GH_MODELS_TOKEN
        self.token = os.getenv('GH_MODELS_TOKEN') or os.getenv('GITHUB_TOKEN')
        
        if not self.token:
            log("⚠️ WARNING: No GitHub Token found. AI calls will fail.")
        else:
            log(f"🔑 Loaded GitHub Token.")

    def get_current_key(self):
        return self.token

    def switch_key(self):
        # GitHub Models usually relies on one user token. 
        # Rate limits are per account. Switching keys isn't really a thing unless you have multiple accounts.
        log("   ⚠️ Rate limit hit on GitHub Models. Waiting 60s...")
        time.sleep(60) 
        return True

# Singleton Instance
key_manager = KeyManager()

# Logging Setup
logger = logging.getLogger("RetryEngine")
logger.setLevel(logging.INFO)

# Custom Exceptions
class JSONValidationError(Exception): pass
class JSONParsingError(Exception): pass

# System Prompt
STRICT_SYSTEM_PROMPT = """
You are an assistant that MUST return ONLY the exact output requested. 
No explanations, no headings, no extra text, no apologies. 
Output exactly and only what the user asked for. 
If the user requests JSON, return PURE JSON. 
Obey safety policy.
"""

def master_json_parser(text):
    if not text: return None
    clean_text = text.replace("```json", "").replace("```", "").strip()
    match = regex.search(r'\{(?:[^{}]|(?R))*\}|\[(?:[^\[\]]|(?R))*\]', clean_text, regex.DOTALL)
    candidate = match.group(0) if match else clean_text
    try:
        decoded = json_repair.repair_json(candidate, return_objects=True)
        if isinstance(decoded, (dict, list)): return decoded
    except: pass
    try:
        return json.loads(candidate)
    except: return None

def validate_structure(data, required_keys):
    if not isinstance(data, dict):
        raise JSONValidationError(f"Expected Dictionary, got {type(data)}")
    missing = [k for k in required_keys if k not in data]
    if missing:
        raise JSONValidationError(f"Missing keys: {missing}")
    return True

def get_client():
    key = key_manager.get_current_key()
    if not key: raise RuntimeError("FATAL: No GitHub Token.")
    
    return OpenAI(
        base_url=GITHUB_MODELS_BASE_URL,
        api_key=key,
    )

@retry(
    stop=stop_after_attempt(5), 
    wait=wait_exponential(multiplier=1, min=10, max=60), # Increased wait for GitHub limits
    retry=retry_if_exception_type(Exception), 
    before_sleep=before_sleep_log(logger, logging.DEBUG)
)
def generate_step_strict(model_name, prompt, step_name, required_keys=[]):
    """
    The Intelligence Hub (GitHub Models Edition).
    """
    # GitHub Models Free Tier has rate limits (RPM/TPM).
    # We add a small delay to be safe.
    time.sleep(2) 
    
    log(f"   🔄 Executing: {step_name} using {model_name} (GitHub)...")

    client = get_client()
    
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": STRICT_SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            top_p=1.0
        )
        
        text_output = response.choices[0].message.content
        parsed_data = master_json_parser(text_output)

        # --- SELF-CORRECTION ---
        if not parsed_data:
            log(f"      🔧 Repairing broken JSON using {FALLBACK_MODEL}...")
            repair_resp = client.chat.completions.create(
                model=FALLBACK_MODEL,
                messages=[
                    {"role": "system", "content": "You are a JSON fixer. Return ONLY valid JSON."},
                    {"role": "user", "content": f"Fix this broken JSON to be valid (Return ONLY JSON):\n{text_output[:10000]}"}
                ]
            )
            parsed_data = master_json_parser(repair_resp.choices[0].message.content)
            
        if required_keys and parsed_data:
            validate_structure(parsed_data, required_keys)
            
        if not parsed_data:
            raise JSONParsingError(f"Failed to parse JSON from {model_name}")

        log(f"      ✅ Success ({step_name}).")
        return parsed_data

    except Exception as e:
        error_msg = str(e).lower()
        
        # Handle Rate Limits (429)
        if "429" in error_msg:
            log(f"      ⚠️ GitHub Rate Limit Hit. Waiting 60 seconds...")
            time.sleep(60)
            # Retry recursively
            return generate_step_strict(model_name, prompt, step_name, required_keys)
        
        log(f"      ❌ Error on {step_name}: {str(e)[:100]}")
        raise e
