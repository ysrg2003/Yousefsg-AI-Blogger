# FILE: main.py
# ROLE: Orchestrator V9.4 (The Unstoppable Research Engine - Fixed Edition)
# DESCRIPTION: Integrates 3-image re-hosting, dual-video injection, and fixed variable scoping.

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
    Executes the full content lifecycle with fixed variable scoping and asset management.
    """
    model_name = config['settings'].get('model_name', "gemini-1.5-pro-latest")
    
    # --- 0. Initialize Variables (To avoid UnboundLocalError) ---
    vid_main_id, vid_main_url = None, None
    vid_short_id, vid_short_url = None, None
    local_fb_video = None
    img_url = None
    
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
        # 4. OMNI-HUNT (RESEARCH)
        # ======================================================================
        log("   🕵️‍♂️ Starting Omni-Hunt (Strict: 3+ Sources)...")
        collected_sources = []
        ai_results = ai_researcher.smart_hunt(target_keyword, config, mode="general")
        if ai_results:
            vetted = news_fetcher.ai_vet_sources(ai_results, model_name)
            for item in vetted:
                if len(collected_sources) >= 3: break
                f_url, f_title, text, f_image, media = scraper.resolve_and_scrape(item['link'])
                if text: collected_sources.append({"title": f_title or item['title'], "url": f_url, "text": text, "source_image": f_image, "media": media})

        if len(collected_sources) < 3:
            log("   ⚠️ Not enough sources. Aborting.")
            return False

        # ======================================================================
        # 5. VISUAL ASSET PREPARATION (3 Images + Video Production)
        # ======================================================================
        log("   ✍️ Processing Visual Assets (Re-hosting & Video Production)...")
        
        # A) Collect all found media
        all_media = []
        for s in collected_sources:
            if s.get('media'): all_media.extend(s['media'])
        
        unique_media = {m['url']: m for m in all_media}.values()
        source_videos = [m for m in unique_media if m['type'] in ['video', 'embed']]
        source_images = [m for m in unique_media if m['type'] in ['image', 'gif']]

        # B) Produce System Videos FIRST (So we have the URLs for the article)
        log("   🎬 Producing System Videos...")
        summ_for_vid = collected_sources[0]['text'][:1000]
        vs = api_manager.generate_step_strict(model_name, PROMPT_VIDEO_SCRIPT.format(title=target_keyword, text_summary=summ_for_vid), "Video Script")
        script_json = vs.get('video_script', [])
        
        rr = video_renderer.VideoRenderer(output_dir="output")
        ts = int(time.time())
        pm = rr.render_video(script_json, target_keyword, f"main_{ts}.mp4")
        if pm:
            vid_main_id, vid_main_url = youtube_manager.upload_video_to_youtube(pm, target_keyword, "Analysis", ["tech", category])
        
        rs = video_renderer.VideoRenderer(output_dir="output", width=1080, height=1920)
        ps = rs.render_video(script_json, target_keyword, f"short_{ts}.mp4")
        if ps:
            local_fb_video = ps
            vid_short_id, vid_short_url = youtube_manager.upload_video_to_youtube(ps, f"{target_keyword[:50]} #Shorts", "Quick Review", ["shorts", category])

        # C) Build Asset Map for Injection
        asset_map = {}
        available_tags = []

        # Inject System Video
        if vid_main_url:
            tag = "[[VIDEO_SYSTEM]]"
            asset_map[tag] = f'<div class="video-wrapper" style="margin:30px 0;"><iframe src="{vid_main_url}" width="100%" height="450" frameborder="0" allowfullscreen></iframe></div>'
            available_tags.append(tag)

        # Inject Source Video (if exists)
        if source_videos:
            tag = "[[VIDEO_SOURCE]]"
            v = source_videos[0]
            asset_map[tag] = f'<div class="video-wrapper" style="margin:30px 0;"><iframe src="{v["url"]}" width="100%" height="450" frameborder="0" allowfullscreen></iframe></div>'
            available_tags.append(tag)

        # Re-host and Inject 3 Images
        processed_img_count = 0
        for i, img_data in enumerate(source_images):
            if processed_img_count >= 3: break
            new_url = image_processor.download_and_upload_to_github(img_data['url'], f"article_img_{i}")
            if new_url:
                tag = f"[[IMAGE_{processed_img_count+1}]]"
                asset_map[tag] = f'<figure style="margin:30px 0; text-align:center;"><img src="{new_url}" style="max-width:100%; border-radius:10px;"><figcaption>📸 {img_data.get("description", "Visual Evidence")}</figcaption></figure>'
                available_tags.append(tag)
                processed_img_count += 1

        # Fallback AI Images if sources are missing
        while processed_img_count < 3:
            ai_img = image_processor.generate_and_upload_image(target_keyword)
            if ai_img:
                tag = f"[[IMAGE_{processed_img_count+1}]]"
                asset_map[tag] = f'<figure style="margin:30px 0; text-align:center;"><img src="{ai_img}" style="max-width:100%; border-radius:10px;"><figcaption>🤖 AI Visualization</figcaption></figure>'
                available_tags.append(tag)
            processed_img_count += 1

        # ======================================================================
        # 6. WRITING & FINAL ASSEMBLY
        # ======================================================================
        log("   ✍️ Writing Article Content...")
        reddit_context, _ = reddit_manager.get_community_intel(target_keyword)
        combined_text = "\n".join([f"SOURCE: {s['url']}\n{s['text'][:8000]}" for s in collected_sources]) + reddit_context
        
        payload = {
            "keyword": target_keyword, 
            "research_data": combined_text, 
            "AVAILABLE_VISUAL_TAGS": available_tags,
            "TODAY_DATE": str(datetime.date.today())
        }
        
        json_b = api_manager.generate_step_strict(model_name, PROMPT_B_TEMPLATE.format(json_input=json.dumps(payload), forbidden_phrases="[]"), "Writer", ["headline", "article_body"])
        
        # Contextual Replacement
        final_body = json_b['article_body']
        for tag, html in asset_map.items():
            final_body = final_body.replace(tag, html)
        
        json_b['article_body'] = final_body

        # SEO & Humanizer
        sources_data = [{"title": s['title'], "url": s['url']} for s in collected_sources]
        kg_links = history_manager.get_relevant_kg_for_linking(json_b['headline'], category)
        json_c = api_manager.generate_step_strict(model_name, PROMPT_C_TEMPLATE.format(json_input=json.dumps({"draft_content": json_b, "sources_data": sources_data}), knowledge_graph=kg_links), "SEO", ["finalTitle", "finalContent"])
        final_article = api_manager.generate_step_strict(model_name, PROMPT_D_TEMPLATE.format(json_input=json.dumps(json_c)), "Humanizer", ["finalTitle", "finalContent"])
        
        title, full_body_html = final_article['finalTitle'], final_article['finalContent']

        # Featured Image (Thumbnail)
        img_url = image_processor.generate_and_upload_image(final_article.get('imageGenPrompt', title), final_article.get('imageOverlayText', ''))
        if img_url:
            full_body_html = f'<div style="text-align:center; margin-bottom:30px;"><img src="{img_url}" style="width:100%; border-radius:15px;"></div>' + full_body_html

        # ======================================================================
        # 7. PUBLISHING
        # ======================================================================
        log("   🚀 [Publishing] Initial Draft...")
        pub_result = publisher.publish_post(title, full_body_html, [category])
        published_url, post_id = (pub_result if isinstance(pub_result, tuple) else (pub_result, None))

        if published_url:
            history_manager.update_kg(title, published_url, category, post_id)
            indexer.submit_url(published_url)
            
            # Social Distribution
            fb_dat = api_manager.generate_step_strict(model_name, PROMPT_FACEBOOK_HOOK.format(title=title), "FB Hook", ["FB_Hook"])
            social_manager.distribute_content(fb_dat.get('FB_Hook', title), published_url, img_url)
            if local_fb_video:
                social_manager.post_reel_to_facebook(local_fb_video, fb_dat.get('FB_Hook', title), published_url)
            
            # Update YouTube Descriptions
            yt_text = f"👇 Read the full analysis:\n{published_url}"
            if vid_main_id: youtube_manager.update_video_description(vid_main_id, yt_text)
            if vid_short_id: youtube_manager.update_video_description(vid_short_id, yt_text)

        return True

    except Exception as e:
        log(f"❌ PIPELINE CRASHED: {e}")
        traceback.print_exc()
        return False

def main():
    try:
        with open('config_advanced.json','r') as f: cfg = json.load(f)
        cats = list(cfg['categories'].keys())
        random.shuffle(cats)
        
        for cat in cats:
            log(f"\n📂 CATEGORY: {cat}")
            topic, is_c = cluster_manager.get_strategic_topic(cat, cfg)
            if topic and run_pipeline(cat, cfg, forced_keyword=topic, is_cluster_topic=is_c):
                break
    except Exception as e: log(f"❌ CRITICAL MAIN ERROR: {e}")

if __name__ == "__main__":
    main()
