# main.py
import os
import json
import time
import requests
import random
import sys
import datetime
import urllib.parse
import traceback
import trafilatura
from bs4 import BeautifulSoup
import re
from urllib.parse import urlparse
from typing import Any, Callable, Optional, Dict

# --- Core Configurations & Modules ---
from config import log, FORBIDDEN_PHRASES, ARTICLE_STYLE, BORING_KEYWORDS, EEAT_GUIDELINES
import api_manager
import news_fetcher
import scraper
import image_processor
import history_manager
import publisher
import content_validator_pro
import reddit_manager
import social_manager
import video_renderer
import youtube_manager
import url_resolver
from prompts import *
import cluster_manager
import indexer
import gardener
import ai_researcher
import ai_strategy
import live_auditor
import remedy

# --- NEW INTELLIGENCE MODULES ---
import trend_watcher
import truth_verifier
import chart_generator
import code_hunter
import image_enricher
import content_architect
import deep_dive_researcher

# ----- safety fallbacks & JSON repair helpers (paste after `from prompts import *`) -----
import json, re

# Fallback PROMPT_D_TEMPLATE if prompts.py didn't define it (prevents NameError)
if 'PROMPT_D_TEMPLATE' not in globals():
    PROMPT_D_TEMPLATE = (
        "CONTEXT: Humanizer fallback. Input HTML in {content_input}.\n\n"
        "TASK: Return a JSON object with key 'finalContent' containing the humanized HTML.\n\n"
        "OUTPUT (JSON only): {\"finalContent\": \"<p>unknown</p>\"}"
    )

def _safe_load_json_from_text(text: Any) -> dict:
    """
    Try to parse the first JSON object found inside `text`.
    Returns a dict (may be empty) and never raises.
    """
    try:
        if isinstance(text, dict):
            return text
        if not text or not isinstance(text, str):
            return {}
        # try direct load first
        try:
            return json.loads(text)
        except Exception:
            pass
        # extract first {...} block (non-recursive but practical)
        m = re.search(r'(\{(?:[^{}]|\{[^{}]*\})*\})', text, re.S)
        if m:
            candidate = m.group(1)
            # common quick repairs
            candidate = candidate.replace("\r\n", " ").replace("\n", " ")
            candidate = re.sub(r',\s*}', '}', candidate)
            candidate = re.sub(r',\s*]', ']', candidate)
            try:
                return json.loads(candidate)
            except Exception:
                # try replacing single quotes with double (last resort)
                try:
                    return json.loads(candidate.replace("'", '"'))
                except Exception:
                    return {}
        return {}
    except Exception:
        return {}
# ---------------------------------------------------------------------------------------


# ---------------------------
# Generic safe execution helpers (fallback + optional retries)
# ---------------------------
def safe_execute(fn: Callable, fallback: Any = None, context: str = None, retries: int = 0, retry_delay: float = 1.0, *args, **kwargs) -> Any:
    """
    Execute fn(*args, **kwargs) safely. On exception, log and return fallback.
    - context: short description used in logs
    - retries: number of retries on failure (0 = no retry)
    """
    ctx = f"[safe] {context}" if context else "[safe]"
    attempt = 0
    while True:
        try:
            attempt += 1
            return fn(*args, **kwargs)
        except Exception as e:
            log(f"   ⚠️ {ctx} failed on attempt {attempt}: {e}")
            try:
                raw = getattr(api_manager, "last_response", None)
                if raw:
                    log(f"      🔍 Raw API snippet: {str(raw)[:2000]}")
            except Exception:
                pass
            if attempt > retries:
                log(f"   ❌ {ctx} giving up after {attempt} attempts. Returning fallback.")
                traceback.print_exc()
                return fallback
            else:
                log(f"   🔁 Retrying {ctx} after {retry_delay}s...")
                time.sleep(retry_delay)


# ---------------------------
# AI wrappers and smart fallbacks
# ---------------------------
def _log_raw_api_response_if_available():
    try:
        raw = getattr(api_manager, "last_response", None)
        if raw:
            log("🔍 Raw API response snippet:\n" + str(raw)[:4000])
    except Exception:
        pass


def safe_generate_step_strict(model_name: str, prompt_text: str, step_name: str, required_keys=None, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Wrapper around api_manager.generate_step_strict that logs exceptions and raw responses.
    Returns parsed dict on success or None on failure.
    """
    try:
        result = api_manager.generate_step_strict(model_name, prompt_text, step_name, required_keys or [], **kwargs)
        return result
    except Exception as e:
        log(f"   ⚠️ {step_name} failed: {e}")
        _log_raw_api_response_if_available()
        return None


def safe_generate_for_key(model_name: str, prompt_text: str, step_name: str, required_key: str, system_instruction: Optional[Dict] = None) -> Any:
    """
    Ask the model to return a single JSON key. If fails, return None.
    """
    wrapper_prompt = f"""{prompt_text}

IMPORTANT: Return ONLY a valid JSON object containing the single key "{required_key}".
Example: {{ "{required_key}": "<value>" }}. No extra commentary."""
    try:
        resp = api_manager.generate_step_strict(
            model_name,
            wrapper_prompt,
            step_name,
            [required_key],
            system_instruction=system_instruction
        )
        if resp and required_key in resp:
            return resp[required_key]
        return None
    except Exception as e:
        log(f"   ⚠️ {step_name} (single-key) failed: {e}")
        _log_raw_api_response_if_available()
        return None


def ensure_and_fill_missing_keys(model_name: str, json_c: Dict[str, Any], final_body_html: str) -> Dict[str, Any]:
    """
    Ensure json_c contains required keys: finalTitle, finalContent, seo, schemaMarkup.
    For any missing key attempt to generate it using the model (smart fallback).
    Logs every missing key and whether generation succeeded.
    """
    required = {
        "finalTitle": f"Generate an SEO-friendly headline (<=70 chars) for this article. Keep it concise.\n\nHTML_CONTENT:\n{final_body_html}",
        "finalContent": f"Rewrite and humanize the following HTML content. Preserve paragraph structure and important facts. Return full HTML.\n\nHTML_CONTENT:\n{final_body_html}",
        "seo": f"Generate an SEO object for the article: meta_title (<=70 chars), meta_description (<=155 chars), and a list of 3-6 focus_keywords. Provide as JSON object with keys meta_title, meta_description, focus_keywords.\n\nHTML_CONTENT:\n{final_body_html}",
        "schemaMarkup": f"Generate a JSON-LD object for an Article (schema.org) with keys as a JSON object under 'schema_json_ld'. Provide valid JSON-LD suitable for injection. Use 'unknown' for missing fields.\n\nHTML_CONTENT:\n{final_body_html}"
    }

    if not isinstance(json_c, dict):
        json_c = {}

    # finalTitle
    if not json_c.get("finalTitle"):
        log("   ⚠️ Missing key: 'finalTitle'. Attempting AI regeneration...")
        gen = safe_generate_for_key(model_name, required["finalTitle"], "Regenerate finalTitle", "finalTitle", system_instruction=EEAT_GUIDELINES)
        if gen:
            json_c["finalTitle"] = gen
            log("   ✅ 'finalTitle' regenerated by AI.")
        else:
            json_c["finalTitle"] = "unknown"
            log("   ❌ Could not regenerate 'finalTitle'. Using fallback 'unknown'.")

    # finalContent
    if not json_c.get("finalContent"):
        log("   ⚠️ Missing key: 'finalContent'. Attempting AI regeneration...")
        gen = safe_generate_for_key(model_name, required["finalContent"], "Regenerate finalContent", "finalContent", system_instruction=EEAT_GUIDELINES)
        if gen:
            json_c["finalContent"] = gen
            log("   ✅ 'finalContent' regenerated by AI.")
        else:
            json_c["finalContent"] = final_body_html or "unknown"
            log("   ❌ Could not regenerate 'finalContent'. Falling back to draft HTML or 'unknown'.")

    # seo
    if not isinstance(json_c.get("seo"), dict) or not json_c.get("seo"):
        log("   ⚠️ Missing or invalid key: 'seo'. Attempting AI regeneration...")
        gen = safe_generate_for_key(model_name, required["seo"], "Regenerate seo", "seo", system_instruction=EEAT_GUIDELINES)
        if gen and isinstance(gen, dict):
            json_c["seo"] = gen
            log("   ✅ 'seo' regenerated by AI.")
        else:
            json_c["seo"] = {"meta_title": json_c.get("finalTitle", "unknown"), "meta_description": "unknown", "focus_keywords": []}
            log("   ❌ Could not regenerate 'seo'. Using fallback structure.")

    # schemaMarkup
    if not isinstance(json_c.get("schemaMarkup"), dict) or not json_c.get("schemaMarkup"):
        log("   ⚠️ Missing or invalid key: 'schemaMarkup'. Attempting AI regeneration...")
        gen = safe_generate_for_key(model_name, required["schemaMarkup"], "Regenerate schemaMarkup", "schemaMarkup", system_instruction=EEAT_GUIDELINES)
        if gen and isinstance(gen, dict):
            json_c["schemaMarkup"] = gen
            log("   ✅ 'schemaMarkup' regenerated by AI.")
        else:
            json_c["schemaMarkup"] = {
                "type": "Article",
                "schema_json_ld": {
                    "@context": "https://schema.org",
                    "@type": "Article",
                    "headline": json_c.get("finalTitle", "unknown"),
                    "description": json_c.get("seo", {}).get("meta_description", "unknown"),
                    "author": {"name": "unknown"},
                    "datePublished": "unknown",
                    "mainEntityOfPage": "unknown",
                    "publisher": {"@type": "Organization", "name": "unknown", "logo": {"@type": "ImageObject", "url": "unknown"}}
                }
            }
            log("   ❌ Could not regenerate 'schemaMarkup'. Using fallback skeleton.")
    return json_c


def ensure_required_keys_generic(model_name: str, json_resp: Dict[str, Any], required_prompts: Dict[str, str]) -> Dict[str, Any]:
    """
    Generic function: given json_resp and a dict required_prompts mapping missing_key->prompt,
    attempt to regenerate any missing keys using safe_generate_for_key.
    Special-case: if keys include the SEO set, call ensure_and_fill_missing_keys instead.
    """
    if not isinstance(json_resp, dict):
        json_resp = {}

    # If the required keys include the SEO group, delegate to ensure_and_fill_missing_keys
    seo_keys = {"finalTitle", "finalContent", "seo", "schemaMarkup"}
    if seo_keys & set(required_prompts.keys()):
        # pass whole object and let ensure_and_fill_missing_keys fill SEO-related keys
        json_resp = ensure_and_fill_missing_keys(model_name, json_resp, required_prompts.get("finalContent", ""))

    # For other missing keys, generate them individually
    for key, prompt in required_prompts.items():
        if key in seo_keys:
            continue  # already handled
        if not json_resp.get(key):
            log(f"   ⚠️ Missing key '{key}'. Attempting AI regeneration...")
            val = safe_generate_for_key(model_name, prompt, f"Regenerate {key}", key, system_instruction=EEAT_GUIDELINES)
            if val is not None:
                json_resp[key] = val
                log(f"   ✅ '{key}' regenerated by AI.")
            else:
                # fallback to simple defaults
                json_resp[key] = None
                log(f"   ❌ Could not regenerate '{key}'. Using fallback None.")
    return json_resp


# ---------------------------
# Unchanged helpers (but we'll use safe_execute for external calls)
# ---------------------------
def is_source_viable(url, min_text_length=600):
    """Checks if a source URL is valid and has content."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.head(url, headers=headers, timeout=5, allow_redirects=True)
        if r.status_code == 404:
            return False, "404 Not Found"
        _, _, text, _, _ = scraper.resolve_and_scrape(url)
        if text and len(text) >= min_text_length:
            return True, "Valid Content"
        return False, "Content too short or empty"
    except:
        return False, "Connection Failed"


def is_url_accessible(url):
    """Checks if a URL is alive (Status 200) and allows hotlinking."""
    if not url:
        return False
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        r = requests.head(url, headers=headers, timeout=3, allow_redirects=True)
        return r.status_code == 200
    except:
        return False


# ---------------------------
# Main pipeline (with ensure-required-keys applied after each AI step)
# ---------------------------
def run_pipeline(category, config, forced_keyword=None, is_cluster_topic=False):
    """
    Executes the full content lifecycle using a robust, multi-layered strategy.
    Integrated with Truth Verification, Data Visualization, Code Hunting, and Strict Quality Loops.
    """
    model_name = config['settings'].get('model_name', "gemini-2.5-flash")
    img_url = None

    vid_main_id, vid_main_url = None, None
    vid_short_id = None
    local_fb_video = None
    reddit_context = ""
    
    # القائمة الرئيسية لجميع الأصول (صور + كود) التي سيتم جمعها
    all_collected_assets = [] 

    try:
        # ======================================================================
        # 0. DECODE OFFICIAL SOURCE (THE TRUTH INJECTION)
        # ======================================================================
        official_source_url = None
        if forced_keyword and "||OFFICIAL_SOURCE=" in forced_keyword:
            parts = forced_keyword.split("||OFFICIAL_SOURCE=")
            target_keyword = parts[0].strip()
            official_source_url = parts[1].replace("||", "").strip()
            log(f"   💎 OFFICIAL SOURCE INJECTED: {official_source_url}")
        else:
            target_keyword = forced_keyword

        # ======================================================================
        # 1. STRATEGY & KEYWORD SELECTION
        # ======================================================================
        if not target_keyword:
            log(f"   👉 [Strategy: Legacy Hunt] Scanning Category: {category}")
            recent_history = history_manager.get_recent_titles_string(category=category)
            seo_p = PROMPT_ZERO_SEO.format(category=category, date=datetime.date.today(), history=recent_history, eeat_guidelines=json.dumps(EEAT_GUIDELINES, ensure_ascii=False))
            seo_plan = safe_generate_step_strict(model_name, seo_p, "SEO Strategy", ["target_keyword"], use_google_search=True, system_instruction=EEAT_GUIDELINES)
            # ensure keys (target_keyword)
            seo_plan = ensure_required_keys_generic(model_name, seo_plan or {}, {"target_keyword": f"Return a single string 'target_keyword' for category {category}"})
            target_keyword = seo_plan.get('target_keyword')

        if not target_keyword: 
            return False

        smart_query = ai_strategy.generate_smart_query(target_keyword)

        log("   🧠 [Strategy] Analyzing Topic Intent & Accessibility...")
        intent_prompt = PROMPT_ARTICLE_INTENT.format(target_keyword=target_keyword, category=category)
        intent_analysis = safe_generate_step_strict(
            model_name, intent_prompt, "Intent Analysis", ["content_type", "visual_strategy", "is_enterprise_b2b"], system_instruction=EEAT_GUIDELINES
        )
        # ensure keys
        intent_analysis = ensure_required_keys_generic(model_name, intent_analysis or {}, {
            "content_type": f"Return a content_type string for: {target_keyword}",
            "visual_strategy": f"Return visual_strategy string for: {target_keyword}",
            "is_enterprise_b2b": f"Return boolean is_enterprise_b2b for: {target_keyword}"
        })
        content_type = intent_analysis.get("content_type", "News Analysis")
        visual_strategy = intent_analysis.get("visual_strategy", "hunt_for_screenshot")
        is_b2b = bool(intent_analysis.get("is_enterprise_b2b", False))
        log(f"   🎯 Intent: {content_type} | B2B Mode: {is_b2b}")
        if is_b2b:
            log("      🔒 Enterprise Topic detected. Disabling Code Hunter to prevent hallucinations.")
            if content_type == "Guide": content_type = "News Analysis"  # safe override

        # ======================================================================
        # 2. SEMANTIC GUARD (ANTI-DUPLICATION)
        # ======================================================================
        if not is_cluster_topic:
            if history_manager.check_semantic_duplication(target_keyword, category, config):
                log(f"   🚫 ABORTING PIPELINE: '{target_keyword}' is a semantic duplicate.")
                return False

        # ======================================================================
        # 3. ADVANCED DEEP DIVE & ASSET HARVEST
        # ======================================================================
        log("   🕵️‍♂️ [Phase 1: Research] Initiating Deep Dive & Asset Harvest...")
        collected_sources = []
        official_domain = None

        # A. Get Sources List
        sources_to_scrape = []
        # PASS POSITIONAL ARGS to match underlying signature (query, model_name)
        deep_dive_results = safe_execute(deep_dive_researcher.conduct_deep_dive, {}, "deep_dive_researcher.conduct_deep_dive", 1, 1.0, target_keyword, model_name)
        if deep_dive_results:
            sources_to_scrape.extend(deep_dive_results.get("official_sources", []))
            sources_to_scrape.extend(deep_dive_results.get("research_studies", []))
            sources_to_scrape.extend(deep_dive_results.get("personal_experiences", []))
            sources_to_scrape.extend(deep_dive_results.get("independent_critiques", []))

        # Add Official Source URL if exists and not already in list
        if official_source_url:
             if not any(s.get('url') == official_source_url for s in sources_to_scrape):
                 sources_to_scrape.insert(0, {"url": official_source_url, "page_name": "Official Source"})
             official_domain = urlparse(official_source_url).netloc

        if len(sources_to_scrape) < 5:
            log("   🔍 [Research Expansion] Deep Dive results insufficient. Expanding search with Multi-Perspective Queries...")
            expansion_queries = ai_strategy.generate_multi_perspective_queries(target_keyword)
            for eq in expansion_queries:
                # news_fetcher.get_strict_rss(query, category) — pass positional args
                exp_items = safe_execute(news_fetcher.get_strict_rss, [], "news_fetcher.get_strict_rss", 1, 1.0, eq, category)
                for item in exp_items[:2]:
                    if not any(s.get('url') == item['link'] for s in sources_to_scrape):
                        sources_to_scrape.append({"url": item['link'], "page_name": item['title']})

        # B. SCRAPE LOOP (WITH ASSET EXTRACTION)
        processed_urls = set()
        for src_item in sources_to_scrape:
            url = src_item.get('url') or src_item.get('link')
            if not url or url in processed_urls: continue
            processed_urls.add(url)
            # scraper.resolve_and_scrape(url) — pass positional url
            res = safe_execute(scraper.resolve_and_scrape, (None, None, None, None, []), "scraper.resolve_and_scrape", 1, 1.0, url)
            if not res:
                log(f"      ⚠️ scraper returned nothing for {url}")
                continue
            s_url, s_title, s_text, s_og_img, extracted_assets = res
            if s_text:
                s_type = "SOURCE"
                if official_source_url and url == official_source_url: s_type = "OFFICIAL SOURCE"
                elif deep_dive_results and any(c.get('url') == url for c in deep_dive_results.get("independent_critiques", [])): s_type = "INDEPENDENT CRITIQUE"
                
                collected_sources.append({
                    "title": s_title or src_item.get('page_name') or "Source",
                    "url": s_url, "text": f"[{s_type}]\n{s_text}", "domain": urllib.parse.urlparse(s_url).netloc
                })
                if extracted_assets:
                    log(f"      📸 Found {len(extracted_assets)} assets in {url[:30]}...")
                    all_collected_assets.extend(extracted_assets)
                if s_type == "OFFICIAL SOURCE" and s_og_img and not img_url:
                    img_url = s_og_img

        if not collected_sources:
             log("   ❌ CRITICAL: No sources found. Aborting.")
             return False
        log(f"   ✅ Research Complete. Found {len(collected_sources)} sources.")

        # ======================================================================
        # 4. REDDIT INTEL & COMPETITOR ANALYSIS
        # ======================================================================
        # reddit_manager.get_community_intel(long_keyword) — pass positional
        reddit_context, reddit_media = safe_execute(reddit_manager.get_community_intel, ("", []), "reddit_manager.get_community_intel", 1, 1.0, smart_query)
        for media in reddit_media:
            all_collected_assets.append({
                "type": "image", "url": media['url'], "description": media['description'],
                "source_url": "Reddit", "score": media.get('score', 5)
            })
        
        log("   🔍 [Competitor Analysis] Identifying market alternatives..."); competitor_data = []; comp_prompt = PROMPT_COMPETITOR_ANALYSIS.format(target_keyword=target_keyword, competitors="auto"); comp_result = ensure_required_keys_generic(model_name, safe_generate_step_strict(model_name, comp_prompt, "Competitor Analysis", ["competitors"], use_google_search=True, system_instruction=EEAT_GUIDELINES) or {}, {"competitors": f"Generate a list of competitors for {target_keyword}"}); comp_result.update(safe_generate_step_strict(model_name, f"{comp_prompt}\n\n⚠️ Previous AI response missing 'competitors', fill only missing using existing data: {comp_result}", "Competitor Analysis Retry", ["competitors"], use_google_search=True, system_instruction=EEAT_GUIDELINES) or {}) if not comp_result.get("competitors") else None; competitor_data = comp_result.get("competitors") if comp_result.get("competitors") else [{"name": f"Top {target_keyword} platform", "tier": "Tier 1"}, {"name": f"Best {target_keyword} tools", "tier": "Tier 2"}, {"name": f"Emerging {target_keyword} startups", "tier": "Tier 3"}]; log(f"      ✅ Found competitors: {[c.get('name') if isinstance(c, dict) else c for c in competitor_data]}")

        
        # ======================================================================
        # 5. ASSET CURATION & PREPARATION (Before Blueprint)
        # ======================================================================
        log("   🎨 [Asset Curation] Filtering and Preparing Assets for AI...")
        unique_assets_map = {a.get('url', a.get('content')): a for a in all_collected_assets}
        unique_assets = list(unique_assets_map.values())
        
        visual_context_for_writer = []
        asset_map = {}
        
        # Prioritize: Hero > Code > High Score Images
        sorted_assets = sorted(unique_assets, key=lambda x: (x.get('is_hero', False), x.get('type') == 'code', x.get('score', 0)), reverse=True)
        
        valid_asset_count = 0
        
        for asset in sorted_assets:
            if valid_asset_count >= 15: break # Limit total assets to 15 for AI context window
            
            # Check URL accessibility for images (crucial step)
            if asset['type'] == 'image':
                if not is_url_accessible(asset['url']): continue
                
            asset_id = f"[[ASSET_{valid_asset_count+1}]]"
            description = asset.get('description', '')
            if asset['type'] == 'code':
                description = f"CODE SNIPPET ({asset.get('language')}): {asset.get('content')[:100]}..."
                
            visual_context_for_writer.append(f"{asset_id}: ({asset['type']}) {description}")
            asset_map[asset_id] = asset
            valid_asset_count += 1
            
        # Add generated chart if applicable
        all_text_blob_for_assets = "\n".join([s['text'] for s in collected_sources])[:20000]
        
        # Determine if chart should run (expanded logic)
        should_run_chart = (
            "benchmark" in target_keyword.lower() or 
            "vs" in target_keyword.lower() or 
            "price" in target_keyword.lower() or # Added this back for explicit detection
            category == "AI Money Engines" or     # If category is Money Engines
            content_type == "Guide"               # If content is a Guide
        )
        chart_data = None
        chart_url = None

        if should_run_chart:  
            log("📊 [Chart Generator] Extracting REAL data for visualization...")  
            chart_sources_text = "\n".join([s['text'] for s in collected_sources])[:20000]  
            chart_prompt = f"""TASK: Extract ONLY real numerical data from the following collected sources for a comparison chart about '{target_keyword}'. Focus on metrics: ROI, Cost, Efficiency, Setup Time, Performance, Score, Price per Unit. Sources Text: {chart_sources_text} Return JSON ONLY in this format: {{'chart_title': 'Comparison Chart for {target_keyword}', 'data_points': {{'Entity Name': value, ...}}}} Return null if no sufficient real data exists."""  
            chart_data = safe_generate_step_strict(model_name, chart_prompt, "Chart Data Extraction", ["data_points"])  
            chart_data = ensure_required_keys_generic(model_name, chart_data or {}, {"data_points": chart_prompt})
                    
      
        if chart_data and isinstance(chart_data.get('data_points'), dict) and len(chart_data['data_points']) >= 2:
            try:
                chart_url = safe_execute(
                    chart_generator.create_chart_from_data,
                    None,
                    "chart_generator.create_chart_from_data",
                    1,
                    1.0,
                    chart_data['data_points'],
                    chart_data.get('chart_title', f'{target_keyword} Comparison')
                )
            except Exception as e:
                log(f"   ⚠️ Chart creation failed: {e}")
                traceback.print_exc()
                chart_url = None

            if chart_url:
                log(f"      ✅ Chart Generated & Uploaded: {chart_url}")
                chart_id = "[[GENERATED_CHART]]"
                visual_context_for_writer.append(f"{chart_id}: A data visualization chart comparing key metrics.")
                asset_map[chart_id] = {
                    "type": "chart",
                    "url": chart_url,
                    "description": chart_data.get('chart_title', 'Comparison Chart'),
                    "score": 20
                }  # High score for charts
            else:
                log("      ℹ️ Not enough REAL chart data found or upload failed. Skipping chart generation.")
                    
        # ======================================================================
        # 6. ARCHITECT BLUEPRINT
        # ======================================================================
        log("   🧠 Assembling data bundle for The Architect...")
        competitor_text = ""
        if competitor_data:
            competitor_text = "\n\n--- COMPETITOR ANALYSIS ---\n" + json.dumps(competitor_data, ensure_ascii=False) # Ensure non-ASCII chars are handled
        combined_text = "\n\n".join([s['text'][:8000] for s in collected_sources]) + competitor_text
        
        # content_architect.create_article_blueprint(target_keyword, content_type, combined_text, reddit_context, visual_context, model_name)
        blueprint = safe_execute(content_architect.create_article_blueprint, None, "content_architect.create_article_blueprint", 1, 1.0, target_keyword, content_type, combined_text, reddit_context, "\n".join(visual_context_for_writer), model_name)
        if not blueprint or not blueprint.get("article_blueprint"):
            log("   ❌ CRITICAL FAILURE: Blueprint creation failed. Aborting pipeline.")
            return False

        # ======================================================================
        # 7. ARTISAN WRITER
        # ======================================================================
        log("   ✍️ [The Artisan] Writing the article...")
        artisan_prompt = PROMPT_B_TEMPLATE.format(
            blueprint_json=json.dumps(blueprint, ensure_ascii=False), # ensure_ascii=False for proper Arabic handling
            raw_data_bundle=json.dumps({"research": combined_text[:15000], "reddit": reddit_context[:5000]}, ensure_ascii=False),
            eeat_guidelines=json.dumps(EEAT_GUIDELINES, ensure_ascii=False),
            forbidden_phrases=json.dumps(FORBIDDEN_PHRASES, ensure_ascii=False),
            boring_keywords=json.dumps(BORING_KEYWORDS, ensure_ascii=False)
        )
        json_b = safe_generate_step_strict(model_name, artisan_prompt, "Artisan Writer", ["headline", "article_body"])
        # ensure required keys from writer
        json_b = ensure_required_keys_generic(model_name, json_b or {}, {
            "headline": f"Return headline for article about {target_keyword}",
            "article_body": f"Return article_body HTML for article about {target_keyword}"
        })

        title = blueprint.get("final_title", json_b.get('headline', target_keyword))
        draft_body_html = json_b.get('article_body', '')

        # ======================================================================
        # 8. FINAL ASSEMBLY & ASSET REPLACEMENT
        # ======================================================================
        log("   🔗 Inserting Real Assets into HTML...")
        final_body_html = draft_body_html
        for asset_id, asset in asset_map.items():
            # CRITICAL: Ensure the asset_id actually exists in the AI-generated HTML
            if asset_id not in final_body_html:
                log(f"      ℹ️ Asset {asset_id} not used by AI in blueprint. Skipping replacement.")
                continue # Skip if AI didn't place the placeholder

            replacement_html = ""
            if asset['type'] == 'image':
                # image_processor.upload_external_image(url, filename)
                final_img_url = safe_execute(image_processor.upload_external_image, asset['url'], "image_processor.upload_external_image", 1, 1.0, asset['url'], f"asset-{target_keyword[:20].replace(' ', '-')}")
                if not final_img_url:
                    log(f"      ❌ Failed to upload image for {asset_id}. Trying original URL.")
                    final_img_url = asset['url'] # Fallback to original if upload fails
                
                replacement_html = f'''<figure style="margin: 30px auto; text-align: center;"><img src="{final_img_url}" alt="{asset['description']}" style="width: 100%; border-radius: 8px; border: 1px solid #ddd; box-shadow: 0 4px 12px rgba(0,0,0,0.08);"><figcaption style="font-size: 13px; color: #555; margin-top: 8px; font-style: italic;">📸 {asset['description']}</figcaption></figure>'''
                if not img_url: img_url = final_img_url # Set hero image if not already set

            elif asset['type'] == 'code':
                replacement_html = f'''<div style="background: #2d2d2d; color: #f8f8f2; padding: 20px; border-radius: 8px; overflow-x: auto; margin: 20px 0; font-family: 'Courier New', Courier, monospace;"><pre><code class="language-{asset.get('language', 'text')}">{asset.get('content')}</code></pre></div>'''
            
            elif asset['type'] == 'chart':
                replacement_html = f'''<figure style="margin: 30px auto; text-align: center;"><img src="{asset['url']}" alt="{asset['description']}" style="width: 100%; border-radius: 8px; border: 1px solid #ddd; box-shadow: 0 4px 12px rgba(0,0,0,0.08);"><figcaption style="font-size: 13px; color: #555; margin-top: 8px; font-style: italic;">📊 {asset['description']}</figcaption></figure>'''
            
            final_body_html = final_body_html.replace(asset_id, replacement_html)
        
        # Cleanup any remaining unused placeholders that AI didn't use or we didn't replace
        final_body_html = re.sub(r'\[\[ASSET_\d+\]\]', '', final_body_html)
        final_body_html = re.sub(r'\[\[GENERATED_CHART\]\]', '', final_body_html) # Also clean chart placeholder if not used

        # ======================================================================
        # 11. VIDEO PRODUCTION & UPLOAD
        # ======================================================================
        log("   🎬 Video Production & Upload...")
        summ = re.sub('<[^<]+?>', '', draft_body_html)[:1000] # Use cleaned draft_body_html
        vs_payload = safe_generate_step_strict(model_name, PROMPT_VIDEO_SCRIPT.format(title=title, text_summary=summ), "Video Script", ["video_script"])
        vs_payload = ensure_required_keys_generic(model_name, vs_payload or {}, {"video_script": PROMPT_VIDEO_SCRIPT.format(title=title, text_summary=summ)})
        script_json = vs_payload.get('video_script', []) if vs_payload else []
        if script_json:
            ts = int(time.time())
            # VideoRenderer.render_video(script, title, filename)
            main_video_path = safe_execute(video_renderer.VideoRenderer(output_dir="output").render_video, None, "video_renderer.render_video_main", 0, 0.0, script_json, title, f"main_{ts}.mp4")
            if main_video_path:
                vid_main_id, vid_main_url = safe_execute(youtube_manager.upload_video_to_youtube, (None, None), "youtube_manager.upload_video_to_youtube_main", 0, 0.0, main_video_path, title, "AI Analysis", [t.strip() for t in category.split()])
            short_video_path = safe_execute(video_renderer.VideoRenderer(output_dir="output", width=1080, height=1920).render_video, None, "video_renderer.render_video_short", 0, 0.0, script_json, title, f"short_{ts}.mp4")
            if short_video_path:
                local_fb_video = short_video_path
                vid_short_id, _ = safe_execute(youtube_manager.upload_video_to_youtube, (None, None), "youtube_manager.upload_video_to_youtube_short", 0, 0.0, short_video_path, f"{title[:50]} #Shorts", "Quick Look", ["shorts", category])

        if vid_main_url and vid_main_url.startswith("https://"):
            video_html = f'<h3>Watch the Video Summary</h3><div class="video-wrapper" style="position:relative;padding-bottom:56.25%;"><iframe src="{vid_main_url}" style="position:absolute;top:0;left:0;width:100%;height:100%;border:0;" allowfullscreen title="{title}"></iframe></div>'
            if "[[TOC_PLACEHOLDER]]" in final_body_html:
                final_body_html = final_body_html.replace("[[TOC_PLACEHOLDER]]", "[[TOC_PLACEHOLDER]]" + video_html)
            else:
                final_body_html = video_html + final_body_html

        sources_data = collected_sources
        kg_links = {}
        # ======================================================================
        # SEO POLISH, HUMANIZER, AND INJECTIONS (Robust with smart fallback)
        # ======================================================================
        placeholders = ["html_content", "original_sources", "knowledge_graph", "eeat_guidelines", "boring_keywords"]

        # Make a work copy
        _tpl = PROMPT_C_TEMPLATE

        # 1) temporarily replace real placeholders with unique tokens
        token_map = {}
        for ph in placeholders:
            token = f"___PH_{ph}___"
            token_map[token] = ph
            _tpl = _tpl.replace("{" + ph + "}", token)

        # 2) escape all remaining { } so .format won't try to interpret them (turn into literal braces)
        _tpl = _tpl.replace("{", "{{").replace("}", "}}")

        # 3) restore the placeholders tokens back to single-brace placeholders
        for token, ph in token_map.items():
            _tpl = _tpl.replace(token, "{" + ph + "}")

        # 4) now safely format with our real values
        prompt_text = _tpl.format(
            html_content=final_body_html,
            original_sources=json.dumps(sources_data, ensure_ascii=False),
            knowledge_graph=json.dumps(kg_links, ensure_ascii=False),
            eeat_guidelines=json.dumps(EEAT_GUIDELINES, ensure_ascii=False),
            boring_keywords=json.dumps(BORING_KEYWORDS, ensure_ascii=False)
        )

        # 5) Call the API using the prepared prompt_text
        raw_resp = None
        json_c = {}
        try:
            resp = api_manager.generate_step_strict(
                model_name,
                prompt_text,
                "SEO Polish",
                ["finalTitle", "finalContent", "seo", "schemaMarkup"],
                system_instruction=EEAT_GUIDELINES
            )
            if isinstance(resp, dict):
                json_c = resp
            else:
                raw_resp = getattr(api_manager, "last_response", None) or resp
                json_c = _safe_load_json_from_text(raw_resp) if raw_resp else {}
        except Exception as e:
            log(f"   ⚠️ SEO Polish generate_step_strict failed: {e}")
            _log_raw_api_response_if_available()
            raw_resp = getattr(api_manager, "last_response", None)
            json_c = _safe_load_json_from_text(raw_resp) if raw_resp else {}
            if not isinstance(json_c, dict):
                json_c = {}
        # ======================================================================


        # Ensure & fill SEO keys (smart)
        json_c = ensure_and_fill_missing_keys(model_name, json_c, final_body_html)

        # Optional: If AI suggested an image generation prompt inside json_c
        if not img_url and isinstance(json_c, dict) and json_c.get('imageGenPrompt'):
            try:
                log("   🎨 No real image found. Falling back to AI Image Generation...")
                # image_processor.generate_and_upload_image(prompt, overlay)
                img_url = safe_execute(image_processor.generate_and_upload_image, None, "image_processor.generate_and_upload_image", 0, 0.0, json_c['imageGenPrompt'], json_c.get('imageOverlayText', ''))
            except Exception as e:
                log(f"   ⚠️ Image generation failed: {e}")

        # Humanizer step
        humanizer_payload = safe_generate_step_strict(model_name, PROMPT_D_TEMPLATE.format(content_input=json_c.get('finalContent', final_body_html)), "Humanizer", ["finalContent"])
        humanizer_payload = ensure_required_keys_generic(model_name, humanizer_payload or {}, {"finalContent": PROMPT_D_TEMPLATE.format(content_input=json_c.get('finalContent', final_body_html))})
        final_title = json_c.get('finalTitle', title)
        full_body_html = humanizer_payload.get('finalContent') if humanizer_payload and humanizer_payload.get('finalContent') else json_c.get('finalContent', final_body_html)

        # 1.5. Inject H1 Title with Dynamic URL Link (using placeholder initially)
        published_url_placeholder = f"https://www.latestai.me/{datetime.date.today().year}/{datetime.date.today().month:02d}/temp-slug.html"
        linked_h1_title_html = f'''
        <h1 style="font-size: 2.2em; color: #2c3e50; text-align: center; margin-bottom: 25px; font-weight: bold; line-height: 1.3;">
            <a href="{published_url_placeholder}" target="_blank" rel="bookmark" style="text-decoration: none; color: inherit;">
                {final_title}
            </a>
        </h1>
        '''
        # Inject H1 at the top of the body or replace existing one
        soup_for_h1 = BeautifulSoup(full_body_html, 'html.parser')
        existing_h1_tag = soup_for_h1.find('h1')
        if existing_h1_tag:
            existing_h1_tag.replace_with(BeautifulSoup(linked_h1_title_html, 'html.parser'))
            full_body_html = str(soup_for_h1)
        else:
            full_body_html = linked_h1_title_html + full_body_html


        # 1. Schema Injection (support multiple possible field names)
        schema_obj = None
        if isinstance(json_c.get('schemaMarkup'), dict):
            sm = json_c.get('schemaMarkup')
            if isinstance(sm.get('OUTPUT'), dict):
                schema_obj = sm.get('OUTPUT')
            elif isinstance(sm.get('schema_json_ld'), dict):
                schema_obj = sm.get('schema_json_ld')
            else:
                schema_obj = sm if sm.get('@context') or sm.get('@type') else None

        if schema_obj:
            try:
                log("   🧬 Injecting JSON-LD Schema into final HTML...")
                schema_data = schema_obj
                schema_data['headline'] = final_title
                schema_data['datePublished'] = datetime.date.today().isoformat()
                if img_url:
                    schema_data['image'] = img_url
                if isinstance(schema_data.get('mainEntityOfPage'), dict) and '@id' in schema_data.get('mainEntityOfPage'):
                    schema_data['mainEntityOfPage']['@id'] = published_url_placeholder
                schema_script = f'<script type="application/ld+json">{json.dumps(schema_data, indent=2, ensure_ascii=False)}</script>'
                full_body_html += schema_script
            except Exception as e:
                log(f"   ⚠️ Schema injection failed: {e}")

        # 2. Hero Image Injection
        if img_url:
            img_html = f'<div class="separator" style="clear: both; text-align: center; margin-bottom: 30px;"><a href="{img_url}" style="margin-left: 1em; margin-right: 1em;"><img border="0" src="{img_url}" alt="{final_title}" style="max-width: 100%; height: auto; border-radius: 10px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);" /></a></div>'
            full_body_html = img_html + full_body_html

        # 3. Dynamic Author Box Injection
        log("   👤 Building dynamic author box...")
        author_info = config.get("author_profile", {})
        if author_info:
            author_box = f'''
            <div style="margin-top:50px; padding:30px; background:#f9f9f9; border-left: 6px solid #2ecc71; border-radius:12px; font-family:sans-serif; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">
                <div style="display:flex; align-items:flex-start; flex-wrap:wrap; gap:25px;">
                    <img src="{author_info.get('profile_image_url', '')}"
                         style="width:90px; height:90px; border-radius:50%; object-fit:cover; border:4px solid #fff; box-shadow:0 2px 8px rgba(0,0,0,0.1);" alt="{author_info.get('name', 'Author')}">
                    <div style="flex:1;">
                        <h4 style="margin:0; font-size:22px; color:#2c3e50; font-weight:800;">{author_info.get('name', '')} | Latest AI</h4>
                        <span style="font-size:12px; background:#e8f6ef; color:#2ecc71; padding:4px 10px; border-radius:6px; font-weight:bold;">{author_info.get('title', 'Tech Editor')}</span>
                        <p style="margin:15px 0; color:#555; line-height:1.7;">{author_info.get('bio', '')}</p>
                        <div style="display:flex; gap:15px; flex-wrap:wrap; margin-top:15px;">
                            <a href="{author_info.get('linkedin_url', '#')}" target="_blank" title="LinkedIn"><img src="https://cdn-icons-png.flaticon.com/512/1384/1384014.png" width="24"></a>
                            <a href="{author_info.get('twitter_url', '#')}" target="_blank" title="X (Twitter)"><img src="https://cdn-icons-png.flaticon.com/512/5969/5969020.png" width="24"></a>
                            <a href="{author_info.get('reddit_url', '#')}" target="_blank" title="Reddit"><img src="https://cdn-icons-png.flaticon.com/512/3536/3536761.png" width="24"></a>
                            <a href="https://www.latestai.me" target="_blank" title="Website"><img src="https://cdn-icons-png.flaticon.com/512/1006/1006771.png" width="24"></a>
                            <a href="https://m.youtube.com/@0latestai" target="_blank" title="YouTube"><img src="https://cdn-icons-png.flaticon.com/512/1384/1384060.png" width="24"></a>
                        </div>
                    </div>
                </div>
            </div>
            '''
            full_body_html += author_box
            
        # ======================================================================
        # 13. PUBLISH & POST-PROCESS
        # ======================================================================
        log(f"   🚀 [Publishing] Final Title: {final_title}")
        log(f"   🏷️  Category Included: {category}")
        # publisher.publish_post(title, html, categories)
        pub_result = safe_execute(publisher.publish_post, (None, None), "publisher.publish_post", 0, 0.0, final_title, full_body_html, [category])
        published_url, post_id = (pub_result if isinstance(pub_result, tuple) else (pub_result, None))

        if not published_url or not post_id:
            log("   ❌ CRITICAL FAILURE: Could not publish the initial draft.")
            return False
            
        # Update schema and H1 with the final URL, then update the post
        if ("schema_script" in locals() and published_url_placeholder in full_body_html) or (linked_h1_title_html in full_body_html):
            log("   ✏️ Updating post with final URL in Schema and H1...")
            final_html_with_correct_urls = full_body_html.replace(published_url_placeholder, published_url)
            safe_execute(publisher.update_existing_post, False, "publisher.update_existing_post", 0, 0.0, post_id, final_title, final_html_with_correct_urls)
            full_body_html = final_html_with_correct_urls # Update for quality loop

        # QUALITY IMPROVEMENT LOOP
        quality_score, attempts, MAX_RETRIES = 0, 0, 1 # Enabled 1 loop
        while quality_score < 9.0 and attempts < MAX_RETRIES:
            attempts += 1
            log(f"   🔄 [Deep Quality Loop] Audit Round {attempts}...")
            audit_report = safe_execute(live_auditor.audit_live_article, None, "live_auditor.audit_live_article", 0, 0.0, published_url, target_keyword, attempts)
            if not audit_report: break
            quality_score = float(audit_report.get('quality_score', 0))
            if quality_score >= 9.5: # If quality is very high, break early
                log(f"      ✨ Article is Page 1 Ready! Score: {quality_score}")
                break
            
            log(f"      🚑 Score {quality_score}/10 is not enough. Launching Surgeon Agent...")
            fixed_html = safe_execute(remedy.fix_article_content, None, "remedy.fix_article_content", 0, 0.0, full_body_html, audit_report, target_keyword, attempts)
            if fixed_html and len(fixed_html) > 2000:
                 updated = safe_execute(publisher.update_existing_post, False, "publisher.update_after_remedy", 0, 0.0, post_id, final_title, fixed_html)
                 if updated:
                     full_body_html = fixed_html # Use updated HTML for next loop/final actions
                     log(f"      ✅ Surgery Successful. Article updated.")
                 else:
                     log("      ⚠️ Failed to update post after surgery. Ending quality loop.")
                     break
            else:
                log("      ⚠️ Surgeon failed to return improved content or returned too little. Ending quality loop.")
                break

        # FINAL DISTRIBUTION
        safe_execute(history_manager.update_kg, None, "history_manager.update_kg", 0, 0.0, final_title, published_url, category, post_id)
        safe_execute(indexer.submit_url, None, "indexer.submit_url", 0, 0.0, published_url)
        
        try:
            fb_dat = safe_generate_step_strict(model_name, PROMPT_FACEBOOK_HOOK.format(title=final_title), "FB Hook", ["FB_Hook"])
            fb_dat = ensure_required_keys_generic(model_name, fb_dat or {}, {"FB_Hook": PROMPT_FACEBOOK_HOOK.format(title=final_title)})
            fb_caption = fb_dat.get('FB_Hook', final_title) if fb_dat else final_title
            yt_update_text = f"👇 Read the full technical analysis:\n{published_url}"
            if vid_main_id: safe_execute(youtube_manager.update_video_description, None, "youtube.update_main_desc", 0, 0.0, vid_main_id, yt_update_text)
            if vid_short_id: safe_execute(youtube_manager.update_video_description, None, "youtube.update_short_desc", 0, 0.0, vid_short_id, yt_update_text)
            if img_url: safe_execute(social_manager.distribute_content, None, "social_manager.distribute_content", 0, 0.0, fb_caption, published_url, img_url)
            if local_fb_video: safe_execute(social_manager.post_reel_to_facebook, None, "social_manager.post_reel_to_facebook", 0, 0.0, local_fb_video, fb_caption, published_url)
        except Exception as e:
            log(f"   ⚠️ Social Distribution Error: {e}")

        return True

    except Exception as e:
        log(f"❌ PIPELINE CRASHED: {e}")
        traceback.print_exc()
        return False


def main():
    try:
        with open('config_advanced.json','r', encoding='utf-8') as f: 
            cfg = json.load(f)

        log("--- Starting Maintenance Phase ---")
        try:
            gardener.run_daily_maintenance(cfg)
            log("--- Maintenance Phase Complete ---")
        except Exception as e:
            log(f"   ⚠️ Gardener maintenance run failed: {e}")

        cats = list(cfg['categories'].keys())
        
        # ==============================================================================
        # ROUND 1: THE STRATEGIC CLUSTER (MASTER SERIES)
        # ==============================================================================
        log("\n🔵 [ROUND 1] Hunting for Strategic Cluster/Series Article...")
        random.shuffle(cats) # Mix categories
        cluster_published = False

        for cat in cats:
            if cluster_published: break
            
            topic, is_c = cluster_manager.get_strategic_topic(cat, cfg)
            
            if topic and is_c: # Condition: Must be a topic AND is_c=True (Plan active)
                log(f"   💎 Found Cluster Topic in {cat}: {topic}")
                if run_pipeline(cat, cfg, forced_keyword=topic, is_cluster_topic=True):
                    cluster_published = True
                    log("   ✅ Round 1 Success: Cluster Article Published.")
                else:
                    cluster_manager.mark_topic_failed(topic)
            else:
                log(f"   ℹ️ No active cluster queue for {cat}. Moving next.")

        if not cluster_published:
            log("   ⚠️ Round 1 skipped: No active clusters found in any category.")

        # ==============================================================================
        # ROUND 2: THE FRESH TREND (NEWS / VIRAL)
        # ==============================================================================
        log("\n🟠 [ROUND 2] Hunting for Fresh Trend/News Article...")
        random.shuffle(cats) # Shuffle again for diversity
        trend_published = False

        for cat in cats:
            if trend_published: break
            
            fresh_trends = safe_execute(trend_watcher.get_verified_trend, [], "trend_watcher.get_verified_trend", 0, 0.0, cat, cfg)
            
            if fresh_trends:
                for trend in fresh_trends:
                    if trend_published: break
                    
                    if history_manager.check_semantic_duplication(trend, cat, cfg):
                        log(f"      ⏭️ Skipping duplicate trend: '{trend}'")
                        continue
                    
                    is_valid, official_url, verified_title = safe_execute(truth_verifier.verify_topic_existence, (False, None, None), "truth_verifier.verify_topic_existence", 0, 0.0, trend, cfg['settings']['model_name'])
                    
                    if is_valid:
                        log(f"      ✅ Trend Verified: {verified_title}")
                        forced_tag = f"{verified_title} ||OFFICIAL_SOURCE={official_url}||"
                        
                        if run_pipeline(cat, cfg, forced_keyword=forced_tag, is_cluster_topic=False):
                            trend_published = True
                            log("   ✅ Round 2 Success: Trend Article Published.")
                    else:
                        log(f"      ⛔ Trend Rejected (No Official Source): {trend}")
            
            if not trend_published and cfg['categories'][cat].get('trending_focus'):
                raw_topics = [t.strip() for t in cfg['categories'][cat]['trending_focus'].split(',')]
                random.shuffle(raw_topics)
                for potential_topic in raw_topics:
                    if trend_published: break
                    if history_manager.check_semantic_duplication(potential_topic, cat, cfg): continue
                    
                    log(f"      🚀 Attempting manual topic: {potential_topic}")
                    if run_pipeline(cat, cfg, forced_keyword=potential_topic, is_cluster_topic=False):
                        trend_published = True
                        log("   ✅ Round 2 Success: Manual Topic Published.")

        # ==============================================================================
        # FINAL REPORT
        # ==============================================================================
        log("\n📊 --- DAILY RUN REPORT ---")
        log(f"   1. Cluster Article: {'✅ Published' if cluster_published else '❌ Skipped/Failed'}")
        log(f"   2. Trend Article:   {'✅ Published' if trend_published else '❌ Skipped/Failed'}")

    except Exception as e:
        log(f"❌ CRITICAL MAIN ERROR: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
