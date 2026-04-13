# FILE: api_manager.py
# ROLE: Advanced AI Orchestrator (Hybrid Waterfall Strategy)
# STRATEGY: Puter.js (Claude/GPT) -> Gemini 2.0 -> Gemini 1.5 Pro -> Gemini Flash
# DESCRIPTION: Ensures the highest quality model is always used, degrading gracefully only on failure.
# FEATURES: Key Rotation, Per-Key Rate Limiting (RPM/TPM/RPD), Controlled Retries, Self-Healing JSON.

import os
import time
import json
import math
import random
import logging
import regex
import json_repair
import puter as puter_sdk
from collections import deque
from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log
from config import log

# --- CONFIGURATION ---
API_HEAT = 30  # Seconds to wait between heavy calls to prevent flooding

# Per-key Gemini rate limits (free tier defaults; adjust as needed)
RPM_LIMIT = 5          # Requests per minute per key
TPM_LIMIT = 250_000    # Tokens per minute per key (approximate)
RPD_LIMIT = 20         # Requests per day per key

# Retry configuration
MAX_RETRIES_PER_KEY = 2      # Attempts on the same key before marking it cooling and switching
MAX_BACKOFF_SECONDS = 60     # Cap for exponential backoff waits

# Lightweight model used for self-repair calls to reduce quota consumption
SELF_REPAIR_MODEL = "gemini-2.5-flash-lite"

# 1. Primary Engine (The Best Writer available via Puter)
PUTER_MODEL = "claude-3-5-sonnet"

# 2. Google Gemini Fallback Chain (Ordered from Strongest/Smartest to Fastest/Cheapest)
# FIX: Removed non-existent models to prevent silent API errors and wasted retry cycles.
GEMINI_FALLBACK_CHAIN = [
    "gemini-3-flash-preview",       # Primary — best balance of speed and quality
    "gemini-2.5-flash",             # Strong fallback
    "gemini-3.1-flash-lite-preview", # Deep context fallback
    "gemini-2.5-flash-lite"         # Last resort — fast and reliable
]


# ==============================================================================
# RATE LIMITER — Per-Key RPM / TPM / RPD Tracking
# ==============================================================================

def _estimate_tokens(text):
    """Rough token estimation: ~4 characters per token. Returns at least 100."""
    return max(100, len(text) // 4)


class KeyRateLimiter:
    """
    Tracks per-key RPM, TPM (via 60-second sliding window) and RPD (daily counter)
    to prevent Gemini API limit overruns.  Also supports a forced cooldown period
    that is applied after a key sustains 429 errors.
    """

    def __init__(self, num_keys, rpm_limit=RPM_LIMIT, tpm_limit=TPM_LIMIT, rpd_limit=RPD_LIMIT):
        self.rpm_limit = rpm_limit
        self.tpm_limit = tpm_limit
        self.rpd_limit = rpd_limit

        # Per-key sliding windows: deque of (timestamp, token_count) tuples
        self.request_windows = [deque() for _ in range(num_keys)]

        # Per-key daily counters: list of (date_str, count) tuples
        self.daily_counts = [(None, 0)] * num_keys

        # Per-key cooldown expiry timestamps (unix time)
        self.cooldown_until = [0.0] * num_keys

    def _prune_window(self, key_index, now):
        """Drop sliding-window entries older than 60 seconds."""
        window = self.request_windows[key_index]
        cutoff = now - 60.0
        while window and window[0][0] < cutoff:
            window.popleft()

    def is_cooling(self, key_index):
        """Return True if key is within a forced cooldown period."""
        return time.time() < self.cooldown_until[key_index]

    def mark_cooling(self, key_index, cooldown_seconds):
        """Force a key into cooldown for *cooldown_seconds* seconds."""
        expire = time.time() + cooldown_seconds
        self.cooldown_until[key_index] = expire
        log(f"   ❄️ Key #{key_index + 1} cooling for {cooldown_seconds:.0f}s "
            f"(until {time.strftime('%H:%M:%S', time.localtime(expire))})")

    def can_use(self, key_index):
        """
        Check whether a key can be used right now.

        Returns:
            (True, 0.0)          — key is available immediately
            (False, wait_secs)   — key is throttled; wait at least *wait_secs*
        """
        now = time.time()

        # Forced cooldown check
        if self.is_cooling(key_index):
            return False, self.cooldown_until[key_index] - now

        self._prune_window(key_index, now)
        window = self.request_windows[key_index]

        # RPM check
        if len(window) >= self.rpm_limit:
            oldest_ts = window[0][0]
            wait = 60.0 - (now - oldest_ts)
            if wait > 0:
                return False, wait

        # TPM check
        tokens_this_minute = sum(t for _, t in window)
        if tokens_this_minute >= self.tpm_limit:
            oldest_ts = window[0][0]
            wait = 60.0 - (now - oldest_ts)
            if wait > 0:
                return False, wait

        # RPD check
        today = time.strftime("%Y-%m-%d")
        date_str, count = self.daily_counts[key_index]
        if date_str != today:
            self.daily_counts[key_index] = (today, 0)
            count = 0

        if count >= self.rpd_limit:
            # Wait until midnight
            now_local = time.localtime(now)
            midnight = time.mktime(time.struct_time((
                now_local.tm_year, now_local.tm_mon, now_local.tm_mday + 1,
                0, 0, 0, now_local.tm_wday, now_local.tm_yday, now_local.tm_isdst
            )))
            return False, max(0.0, midnight - now)

        return True, 0.0

    def record_request(self, key_index, estimated_tokens=1000):
        """Record a request against the key's sliding window and daily counter."""
        now = time.time()
        self._prune_window(key_index, now)
        self.request_windows[key_index].append((now, estimated_tokens))

        today = time.strftime("%Y-%m-%d")
        date_str, count = self.daily_counts[key_index]
        if date_str == today:
            self.daily_counts[key_index] = (today, count + 1)
        else:
            self.daily_counts[key_index] = (today, 1)

    def get_best_available_key(self, key_indices):
        """
        Return (key_index, wait_seconds) for the best available key in *key_indices*.
        If any key is immediately available, wait_seconds is 0.0.
        Otherwise returns the key with the shortest wait time.
        """
        min_wait = math.inf
        best_key = key_indices[0] if key_indices else None

        for idx in key_indices:
            available, wait = self.can_use(idx)
            if available:
                return idx, 0.0
            if wait < min_wait:
                min_wait = wait
                best_key = idx

        return best_key, min_wait


# ==============================================================================
# KEY MANAGER — Loads / Rotates Keys + Rate Limiter Integration
# ==============================================================================

class KeyManager:
    def __init__(self):
        self.keys = []
        # Load up to 10 keys for rotation from Environment Variables
        for i in range(1, 11):
            k = os.getenv(f'GEMINI_API_KEY_{i}')
            if k:
                self.keys.append(k)
        # Load legacy single key if exists
        if not self.keys:
            k = os.getenv('GEMINI_API_KEY')
            if k:
                self.keys.append(k)

        self.current_index = 0
        self.rate_limiter = KeyRateLimiter(max(len(self.keys), 1))
        log(f"🔑 Loaded {len(self.keys)} Gemini API Keys.")

    def get_current_key(self):
        if not self.keys:
            return None
        return self.keys[self.current_index]

    def get_key(self, index):
        """Return the key at *index*, or None if out of range."""
        if not self.keys or index >= len(self.keys):
            return None
        return self.keys[index]

    def switch_key(self):
        """Advance current_index to the next key (non-recursive, wraps around)."""
        if self.current_index < len(self.keys) - 1:
            self.current_index += 1
            log(f"   🔄 Switching to Gemini Key #{self.current_index + 1}...")
            return True
        log("   ⚠️ All Gemini keys exhausted. Resetting to Key #1 (Looping)...")
        self.current_index = 0
        return False

    def find_available_key(self, preferred_index=None):
        """
        Find the best available key considering rate limits.

        Returns:
            (key_index, wait_seconds) — wait_seconds is 0 if immediately usable.
        """
        if not self.keys:
            return None, 0.0

        indices = list(range(len(self.keys)))
        if preferred_index is not None and preferred_index in indices:
            indices.remove(preferred_index)
            indices.insert(0, preferred_index)

        return self.rate_limiter.get_best_available_key(indices)


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
# ENGINE 2: GOOGLE GEMINI (BACKUP / TIERS 2-5) — CONTROLLED RATE-LIMITED RETRIES
# ==============================================================================

def _call_gemini_api(client, model_slug, prompt, system_prompt, use_google_search=False):
    """
    Execute a single Gemini API call and return the raw response text.
    Does NOT handle retries or key rotation — that responsibility belongs to the caller.
    """
    google_tools = None
    current_mime_type = "application/json"

    if use_google_search:
        # Activate real-time Google Search grounding
        google_tools = [types.Tool(google_search=types.GoogleSearch())]
        current_mime_type = None  # Disable strict JSON mode at API level when tools are active

    generation_config = types.GenerateContentConfig(
        response_mime_type=current_mime_type,
        system_instruction=system_prompt,
        temperature=0.3,
        tools=google_tools
    )

    response = client.models.generate_content(
        model=model_slug,
        contents=prompt,
        config=generation_config
    )

    if not response or not response.text:
        return None
    return response.text


def try_gemini_generation(model_name, prompt, system_prompt, use_google_search=False, required_keys=None):
    """
    Attempt to generate content with a specific Gemini model using a controlled,
    non-recursive retry loop across available API keys.

    Strategy:
    - Respect per-key RPM/TPM/RPD limits before each call (wait if needed).
    - Retry the *same* key up to MAX_RETRIES_PER_KEY times with exponential
      backoff on 429 (rate limit) and 503 (service unavailable) errors.
    - After exhausting retries on a key, mark it as cooling and move to the next.
    - Never recurse — all retry/rotation logic lives in explicit loops.
    - Self-repair is conditional: only triggered when JSON parsing fails AND
      required_keys is non-empty (meaning structured output is actually expected).
    """
    model_slug = model_name.replace("models/", "")
    estimated_tokens = _estimate_tokens(prompt)

    num_keys = len(key_manager.keys)
    if num_keys == 0:
        raise RuntimeError("FATAL: No Gemini API Keys available in KeyManager.")

    # Build a rotation order starting from the current key
    start_idx = key_manager.current_index
    key_order = [(start_idx + i) % num_keys for i in range(num_keys)]

    for key_idx in key_order:
        key = key_manager.get_key(key_idx)
        if not key:
            continue

        # --- Respect rate limits before attempting this key ---
        available, wait_time = key_manager.rate_limiter.can_use(key_idx)
        if not available:
            if wait_time > 3600:
                # Key is RPD-exhausted for the day — skip it entirely
                log(f"   ⏭️ [Rate Limit] Key #{key_idx + 1} RPD exhausted "
                    f"(~{wait_time / 3600:.1f}h until reset). Skipping...")
                continue
            log(f"   ⏳ [Rate Limit] Key #{key_idx + 1} throttled — "
                f"waiting {wait_time:.1f}s (RPM/TPM/cooldown)...")
            time.sleep(wait_time + 0.5)  # Small buffer to avoid edge-case re-trigger

        client = genai.Client(api_key=key)

        # --- Per-key retry loop ---
        for attempt in range(MAX_RETRIES_PER_KEY):
            try:
                log(f"   🔑 Using Key #{key_idx + 1}, Model: {model_slug} "
                    f"(attempt {attempt + 1}/{MAX_RETRIES_PER_KEY})")

                # Record the request before calling so the window stays accurate
                key_manager.rate_limiter.record_request(key_idx, estimated_tokens)

                raw_text = _call_gemini_api(client, model_slug, prompt, system_prompt, use_google_search)

                if raw_text is None:
                    break  # Empty response — move to next key

                parsed_data = master_json_parser(raw_text)

                # --- CONDITIONAL SELF-REPAIR ---
                # Only attempt repair when JSON parsing failed AND structured output
                # is actually required.  This avoids burning quota on plain-text steps.
                if parsed_data is None and required_keys:
                    log(f"      🔧 [Self-Repair] JSON parse failed; "
                        f"attempting repair via {SELF_REPAIR_MODEL}...")
                    repair_prompt = (
                        "Extract ONLY the valid JSON from the following text. "
                        "Remove citations and conversational filler:\n\n"
                        f"{raw_text[:8000]}"
                    )
                    repair_config = types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.1
                    )
                    # Check rate limit before the repair call
                    rep_available, rep_wait = key_manager.rate_limiter.can_use(key_idx)
                    if not rep_available and rep_wait < 60:
                        log(f"   ⏳ [Rate Limit] Waiting {rep_wait:.1f}s before repair call...")
                        time.sleep(rep_wait + 0.5)
                    try:
                        repair_client = genai.Client(api_key=key)
                        key_manager.rate_limiter.record_request(key_idx, 2000)
                        repair_resp = repair_client.models.generate_content(
                            model=SELF_REPAIR_MODEL,
                            contents=repair_prompt,
                            config=repair_config
                        )
                        if repair_resp and repair_resp.text:
                            parsed_data = master_json_parser(repair_resp.text)
                    except Exception as repair_err:
                        log(f"      ⚠️ Self-repair call failed: {str(repair_err)[:80]}")

                # Successful call — update current_index and return
                key_manager.current_index = key_idx
                return parsed_data

            except Exception as e:
                error_msg = str(e).lower()

                if ("429" in error_msg or "quota" in error_msg
                        or "resource_exhausted" in error_msg or "rate_limit" in error_msg):
                    # Exponential backoff before retry (or key switch)
                    backoff = min(MAX_BACKOFF_SECONDS,
                                  (2 ** attempt) * 5 + random.uniform(0, 3))
                    log(f"      ⚠️ [429] Rate limit on Key #{key_idx + 1}, "
                        f"Model: {model_slug}. Backoff {backoff:.1f}s...")
                    time.sleep(backoff)

                    if attempt == MAX_RETRIES_PER_KEY - 1:
                        # Exhausted retries on this key — put it in cooldown
                        cooldown = min(MAX_BACKOFF_SECONDS, 30 * (attempt + 1))
                        key_manager.rate_limiter.mark_cooling(key_idx, cooldown)
                    continue  # Retry same key

                elif ("503" in error_msg or "unavailable" in error_msg
                      or "service_unavailable" in error_msg):
                    # Backoff with jitter for transient service errors
                    backoff = min(MAX_BACKOFF_SECONDS,
                                  (2 ** attempt) * 3 + random.uniform(1, 5))
                    log(f"      ⚠️ [503] Service unavailable on Key #{key_idx + 1}, "
                        f"Model: {model_slug}. Backoff {backoff:.1f}s...")
                    time.sleep(backoff)
                    continue  # Retry same key

                elif "404" in error_msg or "not found" in error_msg:
                    log(f"      ⚠️ Model {model_slug} not found. Skipping model...")
                    return None  # Skip this model entirely

                else:
                    log(f"      ❌ API Error on Key #{key_idx + 1}, "
                        f"{model_slug}: {str(e)[:100]}")
                    break  # Switch to next key

    log(f"      ❌ All keys exhausted for model {model_slug}.")
    return None

# ==============================================================================
# MASTER GENERATOR (ORCHESTRATOR) — UPDATED FOR CONTROLLED RETRIES
# ==============================================================================
@retry(
    # Reduced from 5 to 2: internal per-key loops now handle most transient failures.
    # The outer tenacity layer is a lightweight safety net for hard RuntimeError failures only.
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=2, min=5, max=30),
    retry=retry_if_exception_type(RuntimeError),
    before_sleep=before_sleep_log(logger, logging.INFO)
)
def generate_step_strict(initial_model_name, prompt, step_name, required_keys=[], use_google_search=False):
    """
    The Intelligence Hub.
    Flow: Puter (Tier 1 - Only for Non-Search) -> Gemini Chain (Tiers 2-5).

    Rate limiting and per-key retry logic is handled inside try_gemini_generation.
    The tenacity decorator provides a lightweight outer safety net for hard failures only.
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
        gemini_result = try_gemini_generation(
            model, prompt, STRICT_SYSTEM_PROMPT, use_google_search, required_keys
        )
        
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
