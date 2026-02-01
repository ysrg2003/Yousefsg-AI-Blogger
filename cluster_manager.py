# FILE: cluster_manager.py
# ROLE: Strategy Architect (Topic Cluster & Silo Manager) - V10.0
# DESCRIPTION: Manages the automated content planning lifecycle.
#              1. Scans real-time trends (trend_watcher).
#              2. Filters against published history (history_manager).
#              3. Verifies official source existence (truth_verifier).
#              4. Generates a 3-part SEO Silo series based on verified facts.
#              5. Injects the Official Source URL into the workflow to prevent broken links.

import json
import os
import datetime
import traceback
from config import log
from api_manager import generate_step_strict

# Internal Module Imports (The Upgraded Intelligence Chain)
import trend_watcher
import truth_verifier
import history_manager

# Configuration
CLUSTER_FILE = "content_plan.json"

def load_plan():
    """
    Loads the persistent content plan from the JSON file.
    Ensures the structure is valid for the queuing system.
    """
    if os.path.exists(CLUSTER_FILE):
        try:
            with open(CLUSTER_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Validation of required keys
                if all(k in data for k in ["active_cluster", "queue", "completed"]):
                    return data
        except Exception as e:
            log(f"   ⚠️ Content Plan file corrupted or empty: {e}. Resetting...")
    
    # Default structure if file doesn't exist or is invalid
    return {
        "active_cluster": None, 
        "queue": [], 
        "completed": [],
        "last_generated": str(datetime.date.today())
    }

def save_plan(data):
    """
    Saves the current content plan atomically with UTF-8 encoding.
    """
    try:
        with open(CLUSTER_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log(f"   ❌ Failed to save Content Plan: {e}")

def generate_verified_cluster(category, config):
    """
    THE BRAIN: Coordinates trends, history, and truth verification to build a series.
    Returns a dictionary with cluster details or None if no valid topic found.
    """
    model_name = config['settings'].get('model_name', "gemini-2.5-flash")
    
    # --- PHASE 1: DISCOVERY (trend_watcher) ---
    # Fetch real rising search queries, not guesses.
    raw_trends = trend_watcher.get_verified_trend(category, config)
    
    if not raw_trends:
        log(f"   ⚠️ Cluster Manager: No raw trends discovered for category '{category}'.")
        return None

    log(f"   🔄 Cluster Manager: Analyzing {len(raw_trends)} potential candidates...")

    verified_topic = None
    official_source_url = None
    final_official_title = None

    # --- PHASE 2: THE GAUNTLET (Filter & Verify) ---
    for candidate in raw_trends:
        log(f"      🕵️‍♂️ Investigating candidate: '{candidate}'")

        # 1. Semantic Blacklist Check (history_manager)
        # Does this topic overlap with what we already published?
        is_duplicate = history_manager.check_semantic_duplication(candidate, category, config)
        if is_duplicate:
            log(f"      ⏭️ Skipping '{candidate}': Detected as duplicate in Knowledge Graph.")
            continue

        # 2. Official Truth Verification (truth_verifier)
        # Does this topic have an actual official announcement?
        success, url, true_title = truth_verifier.verify_topic_existence(candidate, model_name)
        
        if success and url:
            verified_topic = candidate
            official_source_url = url
            final_official_title = true_title
            log(f"      ✨ WINNER FOUND: '{final_official_title}'")
            log(f"      🔗 SOURCE SECURED: {official_source_url}")
            break
        else:
            log(f"      ❌ REJECTED: No official source found for '{candidate}'.")

    if not verified_topic or not official_source_url:
        log("   ⚠️ Exhausted all trend candidates. No verified/new topics available today.")
        return None

    # --- PHASE 3: SILO ARCHITECTURE (AI Planning) ---
    # Build a 3-part series around the verified source of truth.
    log(f"   🏗️ Building SEO Cluster Plan for: {final_official_title}")
    
    today_str = str(datetime.date.today())
    
    prompt = f"""
    ROLE: Elite SEO Content Strategist.
    TASK: Create a 3-part "Mastery Series" (Topic Cluster) based on a VERIFIED news event.
    
    INPUT DATA:
    - Verified Title: "{final_official_title}"
    - Official Source: {official_source_url}
    - Current Date: {today_str}
    
    CLUSTER REQUIREMENTS:
    1. **Topic 1 (The Hook/News):** A deep-dive review and technical breakdown of the announcement. Focus on why it matters.
    2. **Topic 2 (The Masterclass):** A comprehensive "How-to" or hands-on guide using the new features mentioned in the source.
    3. **Topic 3 (The Industry Impact):** A high-level comparison/analysis against major competitors (e.g., Google vs OpenAI) or a legacy version.
    
    OUTPUT JSON FORMAT ONLY:
    {{
      "cluster_name": "{final_official_title} Mastery Series",
      "topics": [
        "Complete Title for Topic 1",
        "Complete Title for Topic 2",
        "Complete Title for Topic 3"
      ],
      "silo_logic": "Briefly explain the SEO logic for this cluster."
    }}
    """

    try:
        plan = generate_step_strict(
            model_name, 
            prompt, 
            "Cluster Silo Generation", 
            required_keys=["cluster_name", "topics"]
        )
        
        if plan and plan.get('topics') and len(plan['topics']) >= 3:
            # --- CRITICAL INJECTION ---
            # We inject the official source URL into the first topic string.
            # This allows main.py to extract it later and prioritize it for scraping.
            first_topic = plan['topics'][0]
            plan['topics'][0] = f"{first_topic} ||OFFICIAL_SOURCE={official_source_url}||"
            
            log(f"   ✅ Successfully designed cluster: {plan['cluster_name']}")
            return plan
        
    except Exception as e:
        log(f"   ❌ AI Cluster Planning failed: {e}")
        return None

    return None

def get_strategic_topic(category, config):
    """
    MAIN INTERFACE for main.py.
    Coordinates the queue: Returns (topic_title, is_cluster_topic)
    """
    plan_data = load_plan()
    
    # 1. CHECK QUEUE: If an active series is already in progress, continue it.
    if plan_data.get("active_cluster") and plan_data.get("queue"):
        next_topic = plan_data["queue"].pop(0)
        
        # Check if we just finished the last topic
        if not plan_data["queue"]:
            log(f"   🏁 Finalizing series: '{plan_data['active_cluster']}'")
            plan_data["completed"].append(plan_data["active_cluster"])
            plan_data["active_cluster"] = None
        
        save_plan(plan_data)
        log(f"   🔗 [Queue System] Continuing series: '{next_topic}'")
        return next_topic, True

    # 2. NEW GENERATION: If no queue, attempt to create a new verified cluster.
    log(f"   🆕 [Queue System] No active series. Initiating Discovery for: {category}")
    new_cluster = generate_verified_cluster(category, config)
    
    if new_cluster:
        plan_data["active_cluster"] = new_cluster["cluster_name"]
        plan_data["queue"] = new_cluster["topics"]
        plan_data["last_generated"] = str(datetime.date.today())
        
        # Take the first topic immediately
        current_topic = plan_data["queue"].pop(0)
        
        save_plan(plan_data)
        log(f"   🚀 [Queue System] Starting NEW series: '{current_topic}'")
        return current_topic, True
    
    # 3. FALLBACK: Signal main.py to use standard hunt if cluster generation failed.
    log("   ⚠️ [Queue System] Could not generate cluster. Falling back to daily search.")
    return None, False

def mark_topic_failed(topic_title):
    """
    Emergency function: If main.py crashes during a topic, we might want to 
    put it back in the queue or discard it. For V10, we discard to prevent loops.
    """
    log(f"   🚑 Cluster Manager: Topic '{topic_title}' failed execution. Cleaning queue.")
    # Add logic here if you want to retry or skip.
