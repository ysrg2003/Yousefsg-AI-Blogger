# FILE: api_manager.py
# ROLE: Gemini-first, deterministic, tool-aware caller
# DESCRIPTION: Handles incompatible tool+mime usages and robust key/model rate-limit handling.

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
GEMINI_FALLBACK_CHAIN = [
    "gemini-3-flash-preview",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-robotics-er-1.5-preview"
]
DEFAULT_TEMPERATURE = 0.0
MODEL_PAUSE_SECONDS = 60  # pause a model for 60s when all keys hit quota for it

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

    def rotate_key(self):
        """
        Advance to next key. Return True if rotated, False if cycled back to start.
        """
        if not self.keys:
            return False
        if self.current_index < len(self.keys) - 1:
            self.current_index += 1
            log(f"   🔄 Switching to Gemini Key #{self.current_index + 1}...")
            return True
        # cycled through all keys -> reset to 0 and indicate exhaustion
        self.current_index = 0
        log("   ⚠️ All Gemini keys exhausted. Resetting to Key #1 (Looping)...")
        return False

key_manager = KeyManager()

# ------------------------------------------------------------------------------
# LOGGING
# ------------------------------------------------------------------------------
logger = logging.getLogger("RetryEngine")
logger.setLevel(logging.INFO)
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
    if not text:
        return None
    clean_text = text.replace("```json", "").replace("```", "").strip()
    match = regex.search(r'\{(?:[^{}]|(?R))*\}|\[(?:[^\[\]]|(?R))*\]', clean_text, regex.DOTALL)
    candidate = match.group(0) if match else clean_text
    try:
        decoded = json_repair.repair_json(candidate, return_objects=True)
        if isinstance(decoded, (dict, list)):
            return decoded
    except Exception:
        pass
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
# SANITIZERS
# ------------------------------------------------------------------------------
def _sanitize_system_instruction(sys_inst):
    if not sys_inst:
        return ""
    if isinstance(sys_inst, (list, tuple)):
        return [str(x) for x in sys_inst]
    if isinstance(sys_inst, dict):
        lines = []
        for k, v in sys_inst.items():
            v_str = json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)
            lines.append(f"{k}: {v_str}")
        return "\n".join(lines)
    return str(sys_inst)

def _build_contents_for_api(contents):
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
    return [types.Text(str(contents))] if hasattr(types, "Text") else str(contents)

# ------------------------------------------------------------------------------
# NORMALIZER (kept simple — same as prior)
# ------------------------------------------------------------------------------
def _normalize_parsed_output(parsed, required_keys=None, original_text=None):
    if required_keys is None:
        required_keys = []
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
        if 'headline' in required_keys and 'article_body' in required_keys:
            lines = (original_text or "").strip().splitlines()
            if len(lines) >= 2:
                parsed.setdefault('headline', lines[0].strip())
                parsed.setdefault('article_body', "\n".join(lines[1:]).strip())
                missing2 = [k for k in required_keys if k not in parsed]
                if not missing2:
                    return parsed
        return parsed
    if isinstance(parsed, list):
        if all(isinstance(x, dict) for x in parsed):
            merged = {}
            for item in parsed:
                merged.update(item)
            return _normalize_parsed_output(merged, required_keys, original_text or json.dumps(parsed, ensure_ascii=False))
        if all(isinstance(x, str) for x in parsed):
            if 'headline' in required_keys and 'article_body' in required_keys:
                headline = parsed[0].strip() if parsed else ""
                body = "\n".join(parsed[1:]).strip() if len(parsed) > 1 else ""
                return {'headline': headline, 'article_body': body}
            return {'items': parsed}
        textified = "\n".join([json.dumps(x, ensure_ascii=False) if not isinstance(x, str) else x for x in parsed])
        reparsed = master_json_parser(textified)
        if reparsed and isinstance(reparsed, dict):
            return _normalize_parsed_output(reparsed, required_keys, original_text or textified)
        return {'items': parsed}
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
# In-memory map to pause models when rate-limited across all keys
# ------------------------------------------------------------------------------
rate_limited_models = {}  # model_name -> resume_timestamp (epoch)

def is_model_paused(model_name):
    ts = rate_limited_models.get(model_name)
    if not ts:
        return False
    return time.time() < ts

def pause_model(model_name, seconds=MODEL_PAUSE_SECONDS):
    rate_limited_models[model_name] = time.time() + seconds
    log(f"   ⏸️ Pausing model {model_name} for {seconds}s due to repeated quota errors.")

# ------------------------------------------------------------------------------
# GEMINI CALLER (tool-aware + robust key/model handling)
# ------------------------------------------------------------------------------
def try_gemini_generation(
    model_name,
    prompt,
    system_prompt,
    use_google_search=False,
    system_instruction=None,
    required_keys=None
):
    model_slug = model_name.replace("models/", "")
    if is_model_paused(model_slug):
        log(f"   ⚠️ Skipping {model_slug} because it's currently paused due to prior quota errors.")
        return None

    key = key_manager.get_current_key()
    if not key:
        raise RuntimeError("No Gemini API Keys available.")
    client = genai.Client(api_key=key)

    safe_system = _sanitize_system_instruction(system_instruction or system_prompt or EEAT_GUIDELINES)
    contents_payload = _build_contents_for_api(prompt)
    temperature = DEFAULT_TEMPERATURE

    # Helper to build config with awareness: if use_google_search then DO NOT set response_mime_type="application/json"
    def build_config(use_tools):
        if use_tools and hasattr(types, "Tool") and hasattr(types, "GoogleSearch"):
            tools = [types.Tool(google_search=types.GoogleSearch())]
            # Tool use + application/json is unsupported per API error; omit response_mime_type
            cfg = types.GenerateContentConfig(
                tools=tools,
                temperature=temperature,
                system_instruction=safe_system
            )
            return cfg
        else:
            return types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=temperature,
                system_instruction=safe_system
            )

    # We'll try at most two phases:
    # Phase A: preferred config (with tools if requested)
    # Phase B: if the API returns 400 about tool+json, retry without response_mime_type (i.e., text output) and parse.
    tried_configs = []

    try:
        cfg = build_config(use_google_search)
        tried_configs.append(("primary", use_google_search and True or False))
        response = client.models.generate_content(
            model=model_slug,
            contents=contents_payload,
            config=cfg
        )

        if not response:
            return None

        text = getattr(response, "text", None) or getattr(response, "content", None) or str(response)
        parsed = master_json_parser(text)

        # If no JSON parsed, attempt a repair extraction
        if not parsed:
            repair_prompt = f"Extract ONLY valid JSON matching requested schema from this text. Return PURE JSON if possible:\n\n{text[:12000]}"
            repair_contents = _build_contents_for_api(repair_prompt)
            # If we used tools initially, call repair without tools and with deterministic JSON
            repair_cfg = types.GenerateContentConfig(response_mime_type="application/json", temperature=0.0)
            try:
                repair = client.models.generate_content(model="gemini-2.5-flash", contents=repair_contents, config=repair_cfg)
                repair_text = getattr(repair, "text", None) or str(repair)
                parsed = master_json_parser(repair_text)
            except Exception as repair_e:
                log(f"   ⚠️ Gemini repair attempt failed: {str(repair_e)[:200]}")

        normalized = _normalize_parsed_output(parsed, required_keys=required_keys or [], original_text=text)
        return normalized

    except Exception as e:
        err = str(e)
        low = err.lower()

        # Specific 400: tool + json unsupported -> retry without response_mime_type (text output) if we used tools initially
        if "tool use with a response mime type" in low or "extra inputs are not permitted" in low or isinstance(e, PydanticValidationError):
            log(f"   ⚠️ Gemini validation/tool error for {model_slug}: {str(e)[:200]}")
            # If it mentioned tool+json, retry without response_mime_type
            try:
                # Build a simpler config without response_mime_type (text output)
                cfg2 = types.GenerateContentConfig(
                    temperature=DEFAULT_TEMPERATURE,
                    system_instruction=_sanitize_system_instruction(system_instruction or system_prompt or EEAT_GUIDELINES)
                )
                # Try a simple call (no tools) first if use_google_search was true (tool support problematic)
                # If original intent needed google_search, we should consider doing google search outside Gemini.
                response2 = client.models.generate_content(model=model_slug, contents=_build_contents_for_api(prompt), config=cfg2)
                text2 = getattr(response2, "text", None) or getattr(response2, "content", None) or str(response2)
                parsed2 = master_json_parser(text2)
                normalized2 = _normalize_parsed_output(parsed2, required_keys=required_keys or [], original_text=text2)
                if normalized2:
                    return normalized2
            except Exception as e2:
                log(f"   ⚠️ Retry without response_mime_type failed for {model_slug}: {str(e2)[:200]}")

        # Quota handling (429) -> rotate key and try next key once; if all keys produce 429, pause this model for a while
        if "429" in low or "quota" in low or "too many requests" in low or "exhausted" in low:
            log(f"Quota hit on {model_slug}. Attempting to rotate key...")
            # Attempt to cycle through keys until either we get a new key that might work or we detect exhaustion
            initial_key_index = key_manager.current_index
            tried_all_keys = False
            any_success = False
            for attempt in range(len(key_manager.keys)):
                rotated = key_manager.rotate_key()
                # If rotate_key returned False and we returned to start -> we've cycled through all keys
                if not rotated and key_manager.current_index == initial_key_index:
                    tried_all_keys = True
                    break
                # Try a light request with the new key but do not block in a tight loop: a simple HEAD-like attempt is not possible,
                # so we just try one minimal request below and rely on exception handling to continue.
                try:
                    key = key_manager.get_current_key()
                    client = genai.Client(api_key=key)
                    # Minimal call: model ping by sending a tiny prompt and minimal config (no tools)
                    test_cfg = types.GenerateContentConfig(temperature=0.0)
                    test_resp = client.models.generate_content(model=model_slug, contents="ping", config=test_cfg)
                    # If no exception -> not immediately rate-limited (we'll treat as success and proceed to full attempt next)
                    any_success = True
                    break
                except Exception as exk:
                    if "429" in str(exk).lower() or "quota" in str(exk).lower():
                        continue
                    else:
                        # other error -> break and treat as non-quota
                        break

            if not any_success:
                # All keys produced quota errors or we couldn't find a usable key -> pause this model temporarily
                pause_model(model_slug, MODEL_PAUSE_SECONDS)
                return None
            else:
                # We have a rotated key that might work: try the full request again recursively (once)
                return try_gemini_generation(model_name, prompt, system_prompt, use_google_search, system_instruction, required_keys)

        # Model not found
        if "404" in low or "not found" in low:
            log(f"Model not found: {model_slug}")
            return None

        log(f"API Error on {model_slug}: {str(e)[:300]}")
        return None

# ------------------------------------------------------------------------------
# MASTER ORCHESTRATOR (Gemini-only, tool-aware)
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

    sanitized_system = _sanitize_system_instruction(system_instruction or EEAT_GUIDELINES or "")

    clean_initial = initial_model_name.replace("models/", "")
    if clean_initial in GEMINI_FALLBACK_CHAIN:
        models_to_try = [clean_initial] + [m for m in GEMINI_FALLBACK_CHAIN if m != clean_initial]
    else:
        models_to_try = GEMINI_FALLBACK_CHAIN.copy()

    for model in models_to_try:
        result = try_gemini_generation(model, prompt, sanitized_system, use_google_search, sanitized_system, required_keys)
        if result:
            try:
                if required_keys:
                    validate_structure(result, required_keys)
                log(f"      ✅ Success (Source: {model})")
                return result
            except JSONValidationError as ve:
                log(f"Invalid structure from {model}: {ve}")
                continue

    raise RuntimeError(f"❌ CRITICAL FAILURE: All Gemini models failed for step: {step_name}")
