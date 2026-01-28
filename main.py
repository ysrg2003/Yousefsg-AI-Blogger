# FILE: main.py
# ROLE: Orchestrator V9.2 (The Unstoppable Research Engine)
# DESCRIPTION: The complete, final, and stable version integrating all modules and fixes.
#              Features a multi-layered, intelligent research strategy that guarantees
#              source acquisition or gracefully aborts, enforcing a strict 3-source quality rule.

import os
import json
import time
import random
import sys
import datetime
import urllib.parse
import traceback
import re

# --- Core Configurations & Modules ---
from config import log, FORBIDDEN_PHRASES, ARTICLE_STYLE, BORING_KEYWORDS
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
from prompts import *
import cluster_manager
import indexer
import gardener
import ai_researcher
import live_auditor
import remedy

def run_pipeline(category, config, forced_keyword=None, is_cluster_topic=False):
    """
    Executes the full content lifecycle using a robust, multi-layered Gemini-powered strategy.
    """
    model_name = config['settings'].get('model_name', "gemini-1.5-pro-latest") # Use a powerful model for writing
    
    try:
        # ======================================================================
        # 1. STRATEGY & KEYWORD SELECTION
        # ======================================================================
        target_keyword = ""
        if forced_keyword:
            target_keyword = forced_keyword
        else:
            log(f"   👉 [Strategy: AI Daily Hunt] Scanning Category: {category}")
            recent_history = history_manager.get_recent_titles_string(category=category)
            try:
                seo_p = PROMPT_ZERO_SEO.format(category=category, date=datetime.date.today(), history=recent_history)
                seo_plan = api_manager.generate_step_strict(model_name, seo_p, "SEO Strategy", ["target_keyword"])
                target_keyword = seo_plan.get('target_keyword')
            except Exception as e: return False
        if not target_keyword: return False

        # ======================================================================
        # 2. SEMANTIC GUARD (ANTI-DUPLICATION)
        # ======================================================================
        if not is_cluster_topic:
            history_str = history_manager.get_recent_titles_string(limit=200)
            if history_manager.check_semantic_duplication(target_keyword, history_str):
                log(f"   🚫 Duplication detected for '{target_keyword}'. Aborting.")
                return False

        # ======================================================================
        # 3. CREATIVE DIRECTOR (VISUAL STRATEGY)
        # ======================================================================
        try:
            strategy_prompt = PROMPT_VISUAL_STRATEGY.format(target_keyword=target_keyword, category=category)
            strategy_decision = api_manager.generate_step_strict(model_name, strategy_prompt, "Visual Strategy", ["visual_strategy"])
            visual_strategy = strategy_decision.get("visual_strategy", "generate_comparison_table")
        except: visual_strategy = "generate_comparison_table"

        # ======================================================================
        # 4. OMNI-HUNT (V9.2 - MULTI-LAYERED & FAIL-PROOF)
        # ======================================================================
        log("   🕵️‍♂️ Starting Omni-Hunt (Strict: 3+ Sources)...")
        collected_sources = []
        
        # --- Layer 1: AI Smart Search (General News & Reviews) ---
        try:
            ai_results = ai_researcher.smart_hunt(target_keyword, config, mode="general")
            if ai_results:
                vetted = news_fetcher.ai_vet_sources(ai_results, model_name)
                for item in vetted:
                    if len(collected_sources) >= 3: break
                    f_url, f_title, text, f_image, media = scraper.resolve_and_scrape(item['link'])
                    if text: collected_sources.append({"title": f_title or item['title'], "url": f_url, "text": text, "source_image": f_image, "domain": urllib.parse.urlparse(f_url).netloc})
        except Exception as e: log(f"   ⚠️ AI Search (General) Error: {e}")

        # --- Layer 2: AI Authority Search (Official Docs/GitHub) ---
        if len(collected_sources) < 3:
            log("   🔎 Not enough sources. Hunting for Official Authority...")
            try:
                official_results = ai_researcher.smart_hunt(target_keyword, config, mode="official")
                for item in official_results:
                    if len(collected_sources) >= 3: break
                    if any(s['url'] == item['link'] for s in collected_sources): continue
                    f_url, f_title, text, _, _ = scraper.resolve_and_scrape(item['link'])
                    if text: collected_sources.append({"title": f_title or item['title'], "url": f_url, "text": text, "source_image": None, "domain": "official"})
            except Exception as e: log(f"   ⚠️ AI Search (Official) Error: {e}")

        # --- Layer 3: AI-Powered Legacy Fallback (The Unstoppable Emergency Plan) ---
        if len(collected_sources) < 3:
            log("   ⚠️ AI Research failed. Activating Intelligent Legacy Fallback...")
            core_entity = target_keyword
            try:
                extraction_prompt = f"From this long title, extract only the primary product or technology name (2-3 words max): '{target_keyword}'"
                entity_response = api_manager.generate_step_strict("gemini-2.5-flash", extraction_prompt, "Core Entity Extraction")
                core_entity = str(next(iter(entity_response.values())) if isinstance(entity_response, dict) else entity_response).strip('"{}\n:key_value ')
                log(f"      🔍 Extracted Core Entity for search: '{core_entity}'")
            except:
                core_entity = " ".join(target_keyword.split()[:3])

            legacy_strategies = [f'"{core_entity}"', f'{core_entity} news', core_entity]
            for strategy in legacy_strategies:
                if len(collected_sources) >= 3: break
                raw_items = news_fetcher.get_gnews_api_sources(strategy, category) or news_fetcher.get_real_news_rss(strategy, category)
                vetted_items = news_fetcher.ai_vet_sources(raw_items, model_name)
                for item in vetted_items:
                    if len(collected_sources) >= 3: break
                    f_url, f_title, text, _, _ = scraper.resolve_and_scrape(item['link'])
                    if text: collected_sources.append({"title": f_title or item['title'], "url": f_url, "text": text, "source_image": None, "domain": "legacy-rss"})

        # --- FINAL QUALITY GATE ---
        if len(collected_sources) < 3:
            log(f"   ❌ CRITICAL FAILURE: Found only {len(collected_sources)}/3 required sources. Aborting for quality control.")
            return False
        
        log(f"   ✅ Research Complete. Found {len(collected_sources)} high-quality sources.")

        # ======================================================================
        # 5. VISUAL HUNT & REDDIT INTEL
        # ======================================================================
        official_media, reddit_media = [], []
        if visual_strategy.startswith("hunt"):
            official_media = scraper.smart_media_hunt(target_keyword, category, visual_strategy)
        reddit_context, reddit_media = reddit_manager.get_community_intel(target_keyword)

        # ======================================================================
        # 6. WRITING, ASSETS, and VIDEO PRODUCTION
        # ======================================================================
        log("   ✍️ Synthesizing Content...")
        combined_text = "\n".join([f"SOURCE: {s['url']}\n{s['text'][:8000]}" for s in collected_sources]) + reddit_context
        payload = {"keyword": target_keyword, "research_data": combined_text, "visual_strategy_directive": visual_strategy}
        
        json_b = api_manager.generate_step_strict(model_name, PROMPT_B_TEMPLATE.format(json_input=json.dumps(payload), forbidden_phrases="[]"), "Writer", ["headline", "article_body"])
        title, content = json_b['headline'], json_b['article_body']
        
        sources_data = [{"title": s['title'], "url": s['url']} for s in collected_sources if s.get('url')]
        kg_links = history_manager.get_relevant_kg_for_linking(title, category)
        json_c = api_manager.generate_step_strict(model_name, PROMPT_C_TEMPLATE.format(json_input=json.dumps({"draft_content": json_b, "sources_data": sources_data}), knowledge_graph=kg_links), "SEO", ["finalTitle", "finalContent"])
        final_article = api_manager.generate_step_strict(model_name, PROMPT_D_TEMPLATE.format(json_input=json.dumps(json_c)), "Humanizer", ["finalTitle", "finalContent"])
        
        title, full_body_html = final_article['finalTitle'], final_article['finalContent']

        log("   🎨 Generating Assets...")
        img_url = image_processor.generate_and_upload_image(final_article.get('imageGenPrompt', title))
        
        log("   🎬 GUARANTEED Video Production...")
        script_json = None
        try:
            summ = re.sub('<[^<]+?>', '', full_body_html)[:1000]
            vs = api_manager.generate_step_strict(model_name, PROMPT_VIDEO_SCRIPT.format(title=title, text_summary=summ), "Video Script")
            script_json = vs.get('video_script')
        except: pass
        if not script_json: # Fallback Script
            log("      ⚠️ AI Script failed. Using Fallback Script.")
            script_json = [{"type": "send", "text": f"News about {title[:20]}!"}, {"type": "receive", "text": "Tell me more!"}, {"type": "send", "text": "Full story in the article!"}]
        
        ts = int(time.time())
        out_dir = "output"
        os.makedirs(out_dir, exist_ok=True)
        rr = video_renderer.VideoRenderer(output_dir=out_dir)
        pm = rr.render_video(script_json, title, f"main_{ts}.mp4")
        vid_main, vid_short, local_fb_video = None, None, None
        if pm: vid_main, _ = youtube_manager.upload_video_to_youtube(pm, title, "Read more in link.", ["tech", category])
        
        rs = video_renderer.VideoRenderer(output_dir=out_dir, width=1080, height=1920)
        ps = rs.render_video(script_json, title, f"short_{ts}.mp4")
        if ps:
            local_fb_video = ps
            vid_short, _ = youtube_manager.upload_video_to_youtube(ps, f"{title[:50]} #Shorts", "Read more in link.", ["shorts", category])

        # ======================================================================
        # 7. PERFECTION LOOP (PUBLISH -> AUDIT -> FIX -> REPEAT)
        # ======================================================================
        log("   🚀 [Publishing] Initial Draft...")
        pub_result = publisher.publish_post(title, full_body_html, [category])
        published_url, post_id = (pub_result if isinstance(pub_result, tuple) else (pub_result, None))

        if not published_url or not post_id:
            log("   ❌ CRITICAL FAILURE: Could not publish the initial draft.")
            return False
        
        quality_score, attempts, MAX_RETRIES = 0, 0, 2
        while quality_score < 9.0 and attempts < MAX_RETRIES:
            attempts += 1
            log(f"   🔄 [Quality Loop] Audit Round {attempts}...")
            
            audit_report = live_auditor.audit_live_article(published_url, config, iteration=attempts)
            if not audit_report: break
            
            quality_score = float(audit_report.get('quality_score', 0))
            if quality_score >= 9.0:
                log(f"      🌟 Excellence Achieved! Score: {quality_score}/10.")
                break
            
            log(f"      ⚠️ Score {quality_score}/10. Applying fixes...")
            fixed_html = remedy.fix_article_content(full_body_html, audit_report, target_keyword, iteration=attempts)
            
            if fixed_html:
                if publisher.update_existing_post(post_id, title, fixed_html):
                    full_body_html = fixed_html
                    time.sleep(5)
                else: break
            else: break

        # ======================================================================
        # 8. FINALIZATION & DISTRIBUTION
        # ======================================================================
        history_manager.update_kg(title, published_url, category, post_id)
        try: indexer.submit_url(published_url)
        except: pass
        
        try:
            fb_dat = api_manager.generate_step_strict(model_name, PROMPT_FACEBOOK_HOOK.format(title=title), "FB Hook", ["FB_Hook"])
            fb_caption = fb_dat.get('FB_Hook', title)
            yt_update_text = f"👇 Read the full technical analysis:\n{published_url}"
            if vid_main: youtube_manager.update_video_description(vid_main, yt_update_text)
            if vid_short: youtube_manager.update_video_description(vid_short, yt_update_text)
            social_manager.distribute_content(fb_caption, published_url, img_url)
            if local_fb_video:
                social_manager.post_reel_to_facebook(local_fb_video, fb_caption, published_url)
        except: pass
        
        return True

    except Exception as e:
        log(f"❌ PIPELINE CRASHED: {e}")
        traceback.print_exc()
        return False

def main():
    try:
        with open('config_advanced.json','r') as f: cfg = json.load(f)
        try: gardener.run_daily_maintenance(cfg)
        except: pass
        
        cats = list(cfg['categories'].keys())
        random.shuffle(cats)
        
        published = False
        for cat in cats:
            log(f"\n📂 CATEGORY: {cat}")
            
            # Tiered Strategy: Cluster -> Manual -> AI Daily Hunt
            try:
                topic, is_c = cluster_manager.get_strategic_topic(cat, cfg)
                if topic and run_pipeline(cat, cfg, forced_keyword=topic, is_cluster_topic=is_c):
                    published = True
            except: pass
            if published: break
            
            if cfg['categories'][cat].get('trending_focus'):
                topics = [t.strip() for t in cfg['categories'][cat]['trending_focus'].split(',')]
                for topic in topics:
                    if run_pipeline(cat, cfg, forced_keyword=topic, is_cluster_topic=False):
                        published = True; break
            if published: break
            
            if run_pipeline(cat, cfg, is_cluster_topic=False):
                published = True
            if published: break
        
        if published: log("\n✅ MISSION COMPLETE.")
        else: log("\n❌ MISSION FAILED: No topics met the quality threshold today.")
            
    except Exception as e: log(f"❌ CRITICAL MAIN ERROR: {e}")

if __name__ == "__main__":
    main()
