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
from pydantic import ValidationError as PydanticValidationError

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
# LOGGING SETUP
# ------------------------------------------------------------------------------

logger = logging.getLogger("RetryEngine")
logger.setLevel(logging.INFO)

# Reduce noisy matplotlib font-manager warnings in server/container environments
logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)

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

    # Remove common fences and trim
    clean_text = text.replace("```json", "").replace("```", "").strip()

    # Try to find the first JSON object or array
    match = regex.search(
        r'\{(?:[^{}]|(?R))*\}|\[(?:[^\[\]]|(?R))*\]',
        clean_text,
        regex.DOTALL
    )

    candidate = match.group(0) if match else clean_text

    # Try repair (best effort)
    try:
        decoded = json_repair.repair_json(candidate, return_objects=True)
        if isinstance(decoded, (dict, list)):
            return decoded
    except Exception:
        pass

    # Final attempt: json.loads
    try:
        return json.loads(candidate)
    except Exception:
        return None


def validate_structure(data, required_keys):
    if not isinstance(data, dict):
        raise JSONValidationError(f"Expected Dictionary, got {type(data)}")

    missing = [k for k in required_keys if k not in data]
    if missing:
        raise JSONValidationError(f"Missing keys: {missing}")

    return True

# ------------------------------------------------------------------------------
# UTIL: SANITIZERS FOR Gemini API
# ------------------------------------------------------------------------------

def _sanitize_system_instruction(sys_inst):
    """
    Ensure system_instruction is a string or list of strings (never a dict/object).
    If dict -> convert to readable multiline string "key: value".
    """
    if not sys_inst:
        return ""

    if isinstance(sys_inst, (list, tuple)):
        return [str(x) for x in sys_inst]

    if isinstance(sys_inst, dict):
        lines = []
        for k, v in sys_inst.items():
            # If nested dict/list, json.dumps to produce readable text
            if isinstance(v, (dict, list)):
                v_str = json.dumps(v, ensure_ascii=False)
            else:
                v_str = str(v)
            lines.append(f"{k}: {v_str}")
        return "\n".join(lines)

    return str(sys_inst)


def _build_contents_for_api(contents):
    """
    Build a contents payload acceptable to google-genai:
      - prefer types.Text if available
      - convert bytes -> types.Part.from_bytes
      - accept list[str] or list[parts]
    Returns either a single value or a list acceptable to client.models.generate_content
    """
    # If it's already a list, convert items
    if isinstance(contents, list):
        converted = []
        for c in contents:
            if isinstance(c, (bytes, bytearray)):
                if hasattr(types, "Part") and hasattr(types.Part, "from_bytes"):
                    converted.append(types.Part.from_bytes(data=bytes(c), mime_type="application/octet-stream"))
                else:
                    converted.append(bytes(c))
            else:
                # prefer types.Text if present
                if hasattr(types, "Text"):
                    converted.append(types.Text(str(c)))
                else:
                    converted.append(str(c))
        return converted

    # single bytes
    if isinstance(contents, (bytes, bytearray)):
        if hasattr(types, "Part") and hasattr(types.Part, "from_bytes"):
            return [types.Part.from_bytes(data=bytes(contents), mime_type="application/octet-stream")]
        return [bytes(contents)]

    # otherwise treat as text
    if hasattr(types, "Text"):
        return [types.Text(str(contents))]
    return str(contents)

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

    except Exception as e:
        log(f"   ⚠️ Puter generation failed: {str(e)[:200]}")
        return None

# ------------------------------------------------------------------------------
# ENGINE 2 — GEMINI (Robust / Sanitized)
# ------------------------------------------------------------------------------

def try_gemini_generation(
    model_name,
    prompt,
    system_prompt,
    use_google_search=False,
    system_instruction=None
):
    """
    Robust Gemini caller:
      - sanitizes system_instruction (no dicts)
      - sanitizes contents
      - attempts structured call, then falls back to a very simple call on validation errors
      - rotates key on quota errors
    """
    model_slug = model_name.replace("models/", "")

    key = key_manager.get_current_key()
    if not key:
        raise RuntimeError("No Gemini API Keys available.")

    client = genai.Client(api_key=key)

    # Sanitize system_instruction and prompt/contents
    safe_system = _sanitize_system_instruction(system_instruction or system_prompt)
    contents_payload = _build_contents_for_api(prompt)

    generation_config = None

    try:
        # Build config safely (avoid passing raw dicts/objects)
        if use_google_search and hasattr(types, "Tool") and hasattr(types, "GoogleSearch"):
            tools = [types.Tool(google_search=types.GoogleSearch())]
            generation_config = types.GenerateContentConfig(
                tools=tools,
                temperature=0.3,
                system_instruction=safe_system
            )
        else:
            generation_config = types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
                system_instruction=safe_system
            )

        response = client.models.generate_content(
            model=model_slug,
            contents=contents_payload,
            config=generation_config
        )

        if not response:
            return None

        # prefer .text; some SDKs return different shapes
        text = getattr(response, "text", None)
        if not text:
            # try other known attributes
            if hasattr(response, "content"):
                text = str(response.content)
            else:
                text = str(response)

        parsed = master_json_parser(text)

        # If parsing failed, attempt a repair-extraction using a specialized prompt
        if not parsed:
            repair_prompt = f"Extract ONLY valid JSON from this text:\n\n{text[:8000]}"
            repair_contents = _build_contents_for_api(repair_prompt)
            repair_config = types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.05
            )
            try:
                repair = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=repair_contents,
                    config=repair_config
                )
                repair_text = getattr(repair, "text", None) or str(repair)
                parsed = master_json_parser(repair_text)
            except Exception as repair_e:
                log(f"   ⚠️ Gemini repair attempt failed: {str(repair_e)[:200]}")

        return parsed

    except Exception as e:
        err = str(e)
        low = err.lower()

        # If validation-related error (common message: "Extra inputs are not permitted" or pydantic validation)
        if "extra inputs are not permitted" in low or "validation error" in low or isinstance(e, PydanticValidationError):
            log(f"   ⚠️ Gemini validation error detected for {model_slug}. Retrying with a minimal/simple payload...")
            try:
                # Minimal fallback: plain string contents, no config
                simple_contents = prompt if isinstance(prompt, str) else json.dumps(prompt, ensure_ascii=False)
                simple_resp = client.models.generate_content(
                    model=model_slug,
                    contents=simple_contents
                )
                txt = getattr(simple_resp, "text", None) or str(simple_resp)
                parsed = master_json_parser(txt)
                if parsed:
                    return parsed
            except Exception as e2:
                log(f"   ❌ Gemini fallback simple request failed for {model_slug}: {str(e2)[:200]}")

        # Throttle/quota handling -> rotate key then retry once
        if "429" in low or "quota" in low or "exhausted" in low:
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

        # Model not found / invalid model
        if "404" in low or "not found" in low:
            log(f"Model not found: {model_slug}")
            return None

        # Generic logging for other errors
        log(f"API Error on {model_slug}: {str(e)[:240]}")
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

    # Prepare a sanitized system instruction to pass consistently
    sanitized_system = _sanitize_system_instruction(system_instruction or STRICT_SYSTEM_PROMPT)

    # Tier 1 — Puter
    if not use_google_search:
        result = try_puter_generation(
            prompt,
            sanitized_system
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
            sanitized_system,
            use_google_search,
            sanitized_system
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
