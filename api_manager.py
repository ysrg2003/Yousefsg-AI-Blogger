# FILE: api_manager.py
# ROLE: Advanced AI Orchestrator (Gemini-first, deterministic)
# DESCRIPTION: Robust, production-safe Gemini caller with:
#  - automatic sanitization of system_instruction
#  - deterministic json-first requests (response_mime_type)
#  - normalization/repair for varied outputs
#  - key rotation & simple fallback on validation errors
#  - NO Puter usage (Gemini-only)

import os
import time
import json
import logging
import regex
import json_repair
from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log
from config import log, EEAT_GUIDELINES
from pydantic import ValidationError as PydanticValidationError

# ------------------------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------------------------

API_HEAT = 30  # Seconds to wait between heavy calls to prevent flooding

# Gemini Fallback Chain (primary -> fallback order)
GEMINI_FALLBACK_CHAIN = [
    "gemini-3-flash-preview",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-robotics-er-1.5-preview"
]

# Default deterministic temperature for critical JSON outputs
DEFAULT_TEMPERATURE = 0.0

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
        # If we cycled through all keys, reset and return False
        log("   ⚠️ All Gemini keys exhausted. Resetting to Key #1 (Looping)...")
        self.current_index = 0
        return False

key_manager = KeyManager()

# ------------------------------------------------------------------------------
# LOGGING SETUP
# ------------------------------------------------------------------------------

logger = logging.getLogger("RetryEngine")
logger.setLevel(logging.INFO)
# Reduce verbose matplotlib font-manager warnings if present
logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)

# ------------------------------------------------------------------------------
# EXCEPTIONS
# ------------------------------------------------------------------------------

class JSONValidationError(Exception):
    pass

class JSONParsingError(Exception):
    pass

# ------------------------------------------------------------------------------
# JSON PARSER & VALIDATOR
# ------------------------------------------------------------------------------

def master_json_parser(text):
    """
    Robust JSON extraction from messy LLM outputs.
    Returns parsed dict/list or None.
    """
    if not text:
        return None

    # Remove common code fences and trim
    clean_text = text.replace("```json", "").replace("```", "").strip()

    # Find first JSON object/array
    match = regex.search(r'\{(?:[^{}]|(?R))*\}|\[(?:[^\[\]]|(?R))*\]', clean_text, regex.DOTALL)
    candidate = match.group(0) if match else clean_text

    # Try repair library first (best effort)
    try:
        decoded = json_repair.repair_json(candidate, return_objects=True)
        if isinstance(decoded, (dict, list)):
            return decoded
    except Exception:
        pass

    # Try json.loads as fallback
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
# SANITIZERS (system_instruction & contents)
# ------------------------------------------------------------------------------

def _sanitize_system_instruction(sys_inst):
    """
    Ensure system_instruction is a string or list of strings (never a dict).
    If dict -> convert to readable multiline string.
    """
    if not sys_inst:
        return ""
    if isinstance(sys_inst, (list, tuple)):
        return [str(x) for x in sys_inst]
    if isinstance(sys_inst, dict):
        lines = []
        for k, v in sys_inst.items():
            if isinstance(v, (dict, list)):
                v_str = json.dumps(v, ensure_ascii=False)
            else:
                v_str = str(v)
            lines.append(f"{k}: {v_str}")
        return "\n".join(lines)
    return str(sys_inst)

def _build_contents_for_api(contents):
    """
    Build a contents payload acceptable to google-genai.
    Prefer types.Text when available.
    """
    # If list, convert elements
    if isinstance(contents, list):
        converted = []
        for c in contents:
            if isinstance(c, (bytes, bytearray)):
                if hasattr(types, "Part") and hasattr(types.Part, "from_bytes"):
                    converted.append(types.Part.from_bytes(data=bytes(c), mime_type="application/octet-stream"))
                else:
                    converted.append(bytes(c))
            else:
                converted.append(types.Text(str(c)) if hasattr(types, "Text") else str(c))
        return converted

    if isinstance(contents, (bytes, bytearray)):
        if hasattr(types, "Part") and hasattr(types.Part, "from_bytes"):
            return [types.Part.from_bytes(data=bytes(contents), mime_type="application/octet-stream")]
        return [bytes(contents)]

    # Default: text
    return [types.Text(str(contents))] if hasattr(types, "Text") else str(contents)

# ------------------------------------------------------------------------------
# NORMALIZER: coerce parsed output into required shape if possible
# ------------------------------------------------------------------------------

def _normalize_parsed_output(parsed, required_keys=None, original_text=None):
    """
    Heuristic normalization:
      - dict missing keys: try to extract fields from original_text via regex
      - list -> merge or form headline/body
      - string -> attempt reparsing or split into headline/body
    Returns best-effort dict/list/string.
    """
    if required_keys is None:
        required_keys = []

    # dict case
    if isinstance(parsed, dict):
        missing = [k for k in required_keys if k not in parsed]
        if not missing:
            return parsed
        text = original_text or json.dumps(parsed, ensure_ascii=False)
        for key in missing:
            m = regex.search(rf'["\']{key}["\']\s*:\s*["\'](.+?)["\']', text, regex.DOTALL | regex.IGNORECASE)
            if m:
                parsed[key] = m.group(1).strip()
        missing2 = [k for k in required_keys if k not in parsed]
        if not missing2:
            return parsed
        # fallback split for headline/article_body
        if 'headline' in required_keys and 'article_body' in required_keys:
            lines = (original_text or "").strip().splitlines()
            if len(lines) >= 2:
                parsed.setdefault('headline', lines[0].strip())
                parsed.setdefault('article_body', "\n".join(lines[1:]).strip())
                missing2 = [k for k in required_keys if k not in parsed]
                if not missing2:
                    return parsed
        return parsed

    # list case
    if isinstance(parsed, list):
        # list of dicts -> merge
        if all(isinstance(x, dict) for x in parsed):
            merged = {}
            for item in parsed:
                merged.update(item)
            return _normalize_parsed_output(merged, required_keys, original_text or json.dumps(parsed, ensure_ascii=False))
        # list of strings -> headline + body
        if all(isinstance(x, str) for x in parsed):
            if 'headline' in required_keys and 'article_body' in required_keys:
                headline = parsed[0].strip() if parsed else ""
                body = "\n".join(parsed[1:]).strip() if len(parsed) > 1 else ""
                return {'headline': headline, 'article_body': body}
            return {'items': parsed}
        # mixed -> stringify & reparsed
        textified = "\n".join([json.dumps(x, ensure_ascii=False) if not isinstance(x, str) else x for x in parsed])
        reparsed = master_json_parser(textified)
        if reparsed and isinstance(reparsed, dict):
            return _normalize_parsed_output(reparsed, required_keys, original_text or textified)
        return {'items': parsed}

    # string case
    if isinstance(parsed, str):
        reparsed = master_json_parser(parsed)
        if reparsed and reparsed is not parsed:
            return _normalize_parsed_output(reparsed, required_keys, original_text or parsed)
        if 'headline' in required_keys and 'article_body' in required_keys:
            lines = parsed.strip().splitlines()
            if len(lines) >= 2:
                return {'headline': lines[0].strip(), 'article_body': "\n".join(lines[1:]).strip()}
            else:
                return {'headline': parsed.strip(), 'article_body': ''}
        return parsed

    return parsed

# ------------------------------------------------------------------------------
# GEMINI CALLER (robust, deterministic, sanitized)
# ------------------------------------------------------------------------------

def try_gemini_generation(
    model_name,
    prompt,
    system_prompt,
    use_google_search=False,
    system_instruction=None,
    required_keys=None
):
    """
    Primary Gemini caller. Returns normalized parsed output or None.
    """
    model_slug = model_name.replace("models/", "")
    key = key_manager.get_current_key()
    if not key:
        raise RuntimeError("No Gemini API Keys available.")
    client = genai.Client(api_key=key)

    # Sanitize inputs
    safe_system = _sanitize_system_instruction(system_instruction or system_prompt or EEAT_GUIDELINES)
    contents_payload = _build_contents_for_api(prompt)

    # Safety: ensure minimal temperature for deterministic JSON
    temperature = DEFAULT_TEMPERATURE

    try:
        # Build a safe config
        if use_google_search and hasattr(types, "Tool") and hasattr(types, "GoogleSearch"):
            tools = [types.Tool(google_search=types.GoogleSearch())]
            generation_config = types.GenerateContentConfig(
                tools=tools,
                temperature=temperature,
                system_instruction=safe_system,
                response_mime_type="application/json"
            )
        else:
            generation_config = types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=temperature,
                system_instruction=safe_system
            )

        response = client.models.generate_content(
            model=model_slug,
            contents=contents_payload,
            config=generation_config
        )

        if not response:
            return None

        text = getattr(response, "text", None)
        if not text:
            if hasattr(response, "content"):
                text = str(response.content)
            else:
                text = str(response)

        parsed = master_json_parser(text)

        # If nothing parsed, attempt a repair extraction using a careful prompt
        if not parsed:
            repair_prompt = f"Extract ONLY valid JSON matching the requested schema from this text. Return PURE JSON with keys if possible:\n\n{text[:12000]}"
            repair_contents = _build_contents_for_api(repair_prompt)
            repair_config = types.GenerateContentConfig(response_mime_type="application/json", temperature=0.0)
            try:
                repair = client.models.generate_content(model="gemini-2.5-flash", contents=repair_contents, config=repair_config)
                repair_text = getattr(repair, "text", None) or str(repair)
                parsed = master_json_parser(repair_text)
            except Exception as repair_e:
                log(f"   ⚠️ Gemini repair attempt failed: {str(repair_e)[:200]}")

        normalized = _normalize_parsed_output(parsed, required_keys=required_keys or [], original_text=text)
        return normalized

    except Exception as e:
        err = str(e)
        low = err.lower()

        # Validation error due to sending dict/object in system_instruction or config
        if "extra inputs are not permitted" in low or "validation error" in low or isinstance(e, PydanticValidationError):
            log(f"   ⚠️ Gemini validation error detected for {model_slug}. Retrying with a minimal/simple payload...")
            try:
                simple_contents = prompt if isinstance(prompt, str) else json.dumps(prompt, ensure_ascii=False)
                simple_resp = client.models.generate_content(model=model_slug, contents=simple_contents)
                txt = getattr(simple_resp, "text", None) or str(simple_resp)
                parsed = master_json_parser(txt)
                normalized = _normalize_parsed_output(parsed, required_keys=required_keys or [], original_text=txt)
                if normalized:
                    return normalized
            except Exception as e2:
                log(f"   ❌ Gemini fallback simple request failed for {model_slug}: {str(e2)[:200]}")

        # Quota/throttled -> rotate key and retry once
        if "429" in low or "quota" in low or "exhausted" in low:
            log(f"Quota hit on {model_slug}. Rotating key...")
            if key_manager.switch_key():
                return try_gemini_generation(model_name, prompt, system_prompt, use_google_search, system_instruction, required_keys)
            return None

        # Model not found
        if "404" in low or "not found" in low:
            log(f"Model not found: {model_slug}")
            return None

        log(f"API Error on {model_slug}: {str(e)[:300]}")
        return None

# ------------------------------------------------------------------------------
# MASTER ORCHESTRATOR (Gemini-only)
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

    # Sanitize system instruction once at this top layer (ensures callers can pass dicts safely)
    sanitized_system = _sanitize_system_instruction(system_instruction or EEAT_GUIDELINES or "")

    # Build model list to try (start from initial if included)
    clean_initial = initial_model_name.replace("models/", "")
    if clean_initial in GEMINI_FALLBACK_CHAIN:
        models_to_try = [clean_initial] + [m for m in GEMINI_FALLBACK_CHAIN if m != clean_initial]
    else:
        models_to_try = GEMINI_FALLBACK_CHAIN.copy()

    for model in models_to_try:
        result = try_gemini_generation(model, prompt, sanitized_system, use_google_search, sanitized_system, required_keys)
        if result:
            # Attempt final structural validation (after normalization)
            try:
                if required_keys:
                    validate_structure(result, required_keys)
                log(f"      ✅ Success (Source: {model})")
                return result
            except JSONValidationError as ve:
                log(f"Invalid structure from {model}: {ve}")
                # continue to next model in chain

    raise RuntimeError(f"❌ CRITICAL FAILURE: All Gemini models failed for step: {step_name}")
