# FILE: api_manager.py
# ROLE: Advanced AI Orchestrator (Hybrid Waterfall Strategy)
# STRATEGY: Puter.js (Claude/GPT) -> Gemini Chain
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
from config import log, EEAT_GUIDELINES

# ------------------------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------------------------

API_HEAT = 30  # Seconds to wait between heavy calls to prevent flooding

# Primary Engine
PUTER_MODEL = "claude-3-5-sonnet"

# Gemini Fallback Chain
GEMINI_FALLBACK_CHAIN = [
    "gemini-3-flash-preview",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-robotics-er-1.5-preview"
]

# ------------------------------------------------------------------------------
# KEY MANAGER
# ------------------------------------------------------------------------------

class KeyManager:
    def __init__(self):
        self.keys = []

        for i in range(1, 11):
            k = os.getenv(f"GEMINI_API_KEY_{i}")
            if k:
                self.keys.append(k)

        if not self.keys:
            k = os.getenv("GEMINI_API_KEY")
            if k:
                self.keys.append(k)

        self.current_index = 0
        log(f"🔑 Loaded {len(self.keys)} Gemini API Keys.")

    def get_current_key(self):
        if not self.keys:
            return None
        return self.keys[self.current_index]

    def switch_key(self):
        if self.current_index < len(self.keys) - 1:
            self.current_index += 1
            log(f"   🔄 Switching to Gemini Key #{self.current_index + 1}...")
            return True

        log("   ⚠️ All Gemini keys exhausted. Resetting to Key #1 (Looping)...")
        self.current_index = 0
        return False


key_manager = KeyManager()

# ------------------------------------------------------------------------------
# LOGGING
# ------------------------------------------------------------------------------

logger = logging.getLogger("RetryEngine")
logger.setLevel(logging.INFO)

# ------------------------------------------------------------------------------
# EXCEPTIONS
# ------------------------------------------------------------------------------

class JSONValidationError(Exception):
    pass


class JSONParsingError(Exception):
    pass


# ------------------------------------------------------------------------------
# STRICT SYSTEM PROMPT
# ------------------------------------------------------------------------------

STRICT_SYSTEM_PROMPT = """
You are an assistant that MUST return ONLY the exact output requested.
No explanations, no headings, no extra text, no apologies.
Output exactly and only what the user asked for.
If the user requests JSON, return PURE JSON.
"""

# ------------------------------------------------------------------------------
# JSON PARSER
# ------------------------------------------------------------------------------

def master_json_parser(text):
    """
    Robust JSON extraction from messy LLM outputs.
    """
    if not text:
        return None

    clean_text = text.replace("```json", "").replace("```", "").strip()

    match = regex.search(
        r'\{(?:[^{}]|(?R))*\}|\[(?:[^\[\]]|(?R))*\]',
        clean_text,
        regex.DOTALL
    )

    candidate = match.group(0) if match else clean_text

    try:
        decoded = json_repair.repair_json(candidate, return_objects=True)
        if isinstance(decoded, (dict, list)):
            return decoded
    except:
        pass

    try:
        return json.loads(candidate)
    except:
        return None


def validate_structure(data, required_keys):
    if not isinstance(data, dict):
        raise JSONValidationError(f"Expected Dictionary, got {type(data)}")

    missing = [k for k in required_keys if k not in data]
    if missing:
        raise JSONValidationError(f"Missing keys: {missing}")

    return True

# ------------------------------------------------------------------------------
# ENGINE 1 — PUTER (CLAUDE / GPT)
# ------------------------------------------------------------------------------

def try_puter_generation(prompt, system_prompt):
    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]

        response = puter_sdk.ai.chat(
            messages=messages,
            model=PUTER_MODEL,
            stream=False
        )

        text = ""

        if hasattr(response, "message") and hasattr(response.message, "content"):
            text = response.message.content
        elif isinstance(response, str):
            text = response
        else:
            text = str(response)

        if not text:
            return None

        parsed = master_json_parser(text)
        return parsed

    except Exception:
        return None

# ------------------------------------------------------------------------------
# ENGINE 2 — GEMINI
# ------------------------------------------------------------------------------

def try_gemini_generation(
    model_name,
    prompt,
    system_prompt,
    use_google_search=False,
    system_instruction=None
):
    model_slug = model_name.replace("models/", "")

    key = key_manager.get_current_key()
    if not key:
        raise RuntimeError("No Gemini API Keys available.")

    client = genai.Client(api_key=key)

    generation_config = None

    try:
        # Build config safely
        if use_google_search:
            tools = [types.Tool(google_search=types.GoogleSearch())]

            generation_config = types.GenerateContentConfig(
                tools=tools,
                temperature=0.3,
                system_instruction=system_instruction or system_prompt
            )
        else:
            generation_config = types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
                system_instruction=system_instruction or system_prompt
            )

        response = client.models.generate_content(
            model=model_slug,
            contents=prompt,
            config=generation_config
        )

        if not response:
            return None

        text = getattr(response, "text", None)

        if not text:
            text = str(response)

        parsed = master_json_parser(text)

        if not parsed:
            repair_prompt = f"""
Extract ONLY valid JSON from this text:

{text[:8000]}
"""

            repair_config = types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1
            )

            repair = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=repair_prompt,
                config=repair_config
            )

            repair_text = getattr(repair, "text", str(repair))
            parsed = master_json_parser(repair_text)

        return parsed

    except Exception as e:
        error_msg = str(e).lower()

        if "429" in error_msg or "quota" in error_msg:
            log(f"Quota hit on {model_slug}. Rotating key...")
            if key_manager.switch_key():
                return try_gemini_generation(
                    model_name,
                    prompt,
                    system_prompt,
                    use_google_search,
                    system_instruction
                )
            return None

        if "404" in error_msg:
            log(f"Model not found: {model_slug}")
            return None

        log(f"API Error on {model_slug}: {str(e)[:120]}")
        return None

# ------------------------------------------------------------------------------
# MASTER ORCHESTRATOR
# ------------------------------------------------------------------------------

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception),
    before_sleep=before_sleep_log(logger, logging.DEBUG)
)
def generate_step_strict(
    initial_model_name,
    prompt,
    step_name,
    required_keys=None,
    use_google_search=False,
    system_instruction=None
):
    global API_HEAT

    if required_keys is None:
        required_keys = []

    if API_HEAT > 0:
        time.sleep(1)

    log(f"   🔄 Executing: {step_name}")

    # Tier 1 — Puter
    if not use_google_search:
        result = try_puter_generation(
            prompt,
            system_instruction or STRICT_SYSTEM_PROMPT
        )

        if result:
            try:
                if required_keys:
                    validate_structure(result, required_keys)

                log("      ✅ Success (Source: Puter)")
                return result
            except JSONValidationError:
                log("      ⚠️ Puter returned invalid JSON structure.")

    # Tier 2 — Gemini Chain
    models_to_try = []

    clean_initial = initial_model_name.replace("models/", "")

    if clean_initial in GEMINI_FALLBACK_CHAIN:
        models_to_try.append(clean_initial)
        models_to_try.extend(
            [m for m in GEMINI_FALLBACK_CHAIN if m != clean_initial]
        )
    else:
        models_to_try = GEMINI_FALLBACK_CHAIN

    for model in models_to_try:
        result = try_gemini_generation(
            model,
            prompt,
            STRICT_SYSTEM_PROMPT,
            use_google_search,
            system_instruction or STRICT_SYSTEM_PROMPT
        )

        if result:
            try:
                if required_keys:
                    validate_structure(result, required_keys)

                log(f"      ✅ Success (Source: {model})")
                return result

            except JSONValidationError as ve:
                log(f"Invalid structure from {model}: {ve}")
                continue

    raise RuntimeError(
        f"❌ CRITICAL FAILURE: All AI models failed for step: {step_name}"
    )
