# FILE: main.py
# ROLE: Orchestrator V9.3 (The Unstoppable Research Engine)
# DESCRIPTION: The complete, final, and stable version integrating all modules and fixes.
#              Features a multi-layered, intelligent research strategy that guarantees
#              source acquisition or gracefully aborts, enforcing a strict 3-source quality rule.
#              UPDATES: Contextual Visual Injection, Timeline Paradox Fix, Variable Name Corrections.

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
                    if text: collected_sources.append({"title": f_title or item['title'], "url": f_url, "text": text, "source_image": f_image, "domain": urllib.parse.urlparse(f_url).netloc, "media": media})
        except Exception as e: log(f"   ⚠️ AI Search (General) Error: {e}")

        # --- Layer 2: AI Authority Search (Official Docs/GitHub) ---
        if len(collected_sources) < 3:
            log("   🔎 Not enough sources. Hunting for Official Authority...")
            try:
                official_results = ai_researcher.smart_hunt(target_keyword, config, mode="official")
                for item in official_results:
                    if len(collected_sources) >= 3: break
                    if any(s['url'] == item['link'] for s in collected_sources): continue
                    f_url, f_title, text, _, media = scraper.resolve_and_scrape(item['link'])
                    if text: collected_sources.append({"title": f_title or item['title'], "url": f_url, "text": text, "source_image": None, "domain": "official", "media": media})
            except Exception as e: log(f"   ⚠️ AI Search (Official) Error: {e}")

        # --- Layer 3: AI-Powered Legacy Fallback (The Unstoppable Emergency Plan) ---
        if len(collected_sources) < 3:
            log("   ⚠️ AI Research failed. Activating Intelligent Legacy Fallback...")
            core_entity = target_keyword
            try:
                extraction_prompt = f"Extract the full official name of the product or technology from this title: '{target_keyword}'. Return ONLY the name (e.g., 'Luma AI Dream Machine'), no extra text."
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
                    f_url, f_title, text, _, media = scraper.resolve_and_scrape(item['link'])
                    if text: collected_sources.append({"title": f_title or item['title'], "url": f_url, "text": text, "source_image": None, "domain": "legacy-rss", "media": media})

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
        log("   ✍️ Synthesizing Content & Preparing Visual Assets...")
        
        # --- SMART CONTEXTUAL INJECTION LOGIC ---
        # 1. Collect and Filter Media
        all_media = []
        for s in collected_sources:
            if s.get('media'): all_media.extend(s['media'])
        if official_media: all_media.extend(official_media)
        if reddit_media: all_media.extend(reddit_media)
        
        # Deduplicate
        unique_media = {m['url']: m for m in all_media}.values()
        
        # Separate Videos and Images
        videos = [m for m in unique_media if m['type'] in ['video', 'embed']]
        images = [m for m in unique_media if m['type'] in ['image', 'gif']]
        images = sorted(images, key=lambda x: x.get('score', 0), reverse=True)

        # 2. Build Asset Map (Tag -> HTML)
        asset_map = {}
        available_tags = []

        # A) Process Main Video (Need at least one)
        if videos:
            main_vid = videos[0]
            tag = "[[VIDEO_MAIN]]"
            if main_vid['type'] == 'embed':
                html = f'''<div class="video-wrapper" style="position:relative;padding-bottom:56.25%;height:0;overflow:hidden;margin:30px 0;border-radius:12px;box-shadow:0 4px 15px rgba(0,0,0,0.1);"><iframe src="{main_vid['url']}" style="position:absolute;top:0;left:0;width:100%;height:100%;border:0;" allowfullscreen title="Video Demo"></iframe></div>'''
            else:
                html = f'''<div class="video-wrapper" style="margin:30px 0;"><video controls style="width:100%;border-radius:12px;box-shadow:0 4px 15px rgba(0,0,0,0.1);"><source src="{main_vid['url']}" type="video/mp4">Your browser does not support the video tag.</video></div>'''
            
            asset_map[tag] = html
            available_tags.append(tag)

        # B) Process Images (Batch Mode)
        # 1. PREPARATION PHASE: Identify needs and collect candidates
        batch_requests = {} # لتخزين المرشحين لكل فقرة
        final_urls_map = {} # لتخزين الروابط النهائية (سواء الأصلية الصالحة أو المختارة)
        
        clean_keyword = target_keyword.split(':')[0].split('?')[0].strip()
        
        # تعريف السياقات للفقرات الأربعة
        contexts = [
            {"ctx": f"A clear dashboard user interface of {clean_keyword}", "q": f"{clean_keyword} dashboard interface"},
            {"ctx": f"A workflow demonstration of {clean_keyword}", "q": f"{clean_keyword} workflow demo"},
            {"ctx": f"An example result created by {clean_keyword}", "q": f"{clean_keyword} result example"},
            {"ctx": f"Comparison of {clean_keyword} vs competitors", "q": f"{clean_keyword} comparison"}
        ]

        for i, img in enumerate(images[:4]):
            target_url = img['url']
            needs_replacement = False
            
            # فحص هل الرابط محمي أو مكسور؟
            if "vertexaisearch" in target_url or "googleusercontent" in target_url or not target_url:
                needs_replacement = True
            
            if needs_replacement:
                log(f"   🔍 Collecting candidates for Image {i+1} ({contexts[i]['q']})...")
                # نقلل العدد لـ 3 صور لكل فقرة لتخفيف الحمل على الشبكة (3x4=12 صورة إجمالاً)
                candidates = scraper.get_google_image_candidates(contexts[i]['q'], limit=3)
                
                if candidates:
                    batch_requests[i] = {
                        "context": contexts[i]['ctx'],
                        "urls": candidates
                    }
                else:
                    # إذا لم نجد مرشحين، للأسف لا يوجد صورة
                    final_urls_map[i] = None
            else:
                # الرابط الأصلي سليم، نعتمد عليه
                final_urls_map[i] = target_url

        # 2. AI SELECTION PHASE: Send batch to Gemini
        if batch_requests:
            selected_urls = image_processor.select_best_images_batch(model_name, batch_requests)
            # دمج النتائج المختارة مع الخريطة النهائية
            for idx, url in selected_urls.items():
                final_urls_map[idx] = url

        # 3. PROCESSING PHASE: Download, Edit, Upload
        for i in range(len(images[:4])):
            tag = f"[[IMAGE_{i+1}]]"
            final_url = final_urls_map.get(i)
            
            if not final_url:
                log(f"      ❌ No valid image for tag {tag}. Removing.")
                asset_map[tag] = ""
                continue

            log(f"   🎨 Processing Final Image {i+1}...")
            
            overlay_txt = clean_keyword 
            safe_filename = f"{clean_keyword.replace(' ', '_')}_visual_{i+1}"
            
            # المعالجة والرفع
            new_img_url = image_processor.process_source_image(final_url, overlay_txt, safe_filename)
            
            if new_img_url:
                # تحديد النص البديل المناسب
                if i in batch_requests: # إذا كانت صورة بديلة
                    alt_text = f"{clean_keyword} - {['Interface', 'Workflow', 'Result', 'Comparison'][min(i, 3)]}"
                else: # إذا كانت أصلية
                    alt_text = images[i].get('description', target_keyword).replace('"', '')

                html = f'''
                <figure style="margin:30px 0; text-align:center;">
                    <img src="{new_img_url}" alt="{alt_text}" style="max-width:100%; height:auto; border-radius:10px; border:1px solid #eee; box-shadow:0 2px 8px rgba(0,0,0,0.05);">
                    <figcaption style="font-size:14px; color:#666; margin-top:8px; font-style:italic;">📸 {alt_text}</figcaption>
                </figure>
                '''
                asset_map[tag] = html
                available_tags.append(tag)
            else:
                asset_map[tag] = ""
                        

        # 3. Prepare Payload for Writer
        combined_text = "\n".join([f"SOURCE: {s['url']}\n{s['text'][:8000]}" for s in collected_sources]) + reddit_context
        
        payload = {
            "keyword": target_keyword, 
            "research_data": combined_text, 
            "visual_strategy_directive": visual_strategy,
            "AVAILABLE_VISUAL_TAGS": available_tags, # Pass the tags to AI
            "TODAY_DATE": str(datetime.date.today()) # Fix Timeline Paradox
        }
        
        json_b = api_manager.generate_step_strict(model_name, PROMPT_B_TEMPLATE.format(json_input=json.dumps(payload), forbidden_phrases="[]"), "Writer", ["headline", "article_body"])
        
        # 4. Perform Contextual Replacement (Python Side)
        final_body_draft = json_b['article_body']
        
        for tag, html_code in asset_map.items():
            if tag in final_body_draft:
                final_body_draft = final_body_draft.replace(tag, html_code)
            else:
                # Fallback: If AI forgot the video, force inject it at the end
                if "VIDEO" in tag: 
                    final_body_draft += f"\n<h3>Watch the Demo</h3>{html_code}"
        
        json_b['article_body'] = final_body_draft

        # --- Continue Pipeline ---
        sources_data = [{"title": s['title'], "url": s['url']} for s in collected_sources if s.get('url')]
        kg_links = history_manager.get_relevant_kg_for_linking(json_b['headline'], category)
        
        json_c = api_manager.generate_step_strict(model_name, PROMPT_C_TEMPLATE.format(json_input=json.dumps({"draft_content": json_b, "sources_data": sources_data}), knowledge_graph=kg_links), "SEO", ["finalTitle", "finalContent"])
        final_article = api_manager.generate_step_strict(model_name, PROMPT_D_TEMPLATE.format(json_input=json.dumps(json_c)), "Humanizer", ["finalTitle", "finalContent"])
        
        title, full_body_html = final_article['finalTitle'], final_article['finalContent']

        log("   🎨 Generating Assets...")
        img_url = image_processor.generate_and_upload_image(final_article.get('imageGenPrompt', title))
        
        log("   🎬 Video Production & Upload...")
        
        # Initialize variables to avoid UnboundLocalError
        vid_main_id, vid_main_url = None, None
        vid_short_id, vid_short_url = None, None
        local_fb_video = None
        
        # Generate Script
        summ = re.sub('<[^<]+?>', '', full_body_html)[:1000]
        vs = api_manager.generate_step_strict(model_name, PROMPT_VIDEO_SCRIPT.format(title=title, text_summary=summ), "Video Script")
        script_json = vs.get('video_script', [])

        rr = video_renderer.VideoRenderer(output_dir="output")
        ts = int(time.time())
        
        # Main Video (YouTube)
        pm = rr.render_video(script_json, title, f"main_{ts}.mp4")
        if pm:
            vid_main_id, vid_main_url = youtube_manager.upload_video_to_youtube(pm, title, "Technical Analysis", ["tech", category])
        
        # Shorts Video (YouTube + Facebook)
        rs = video_renderer.VideoRenderer(output_dir="output", width=1080, height=1920)
        ps = rs.render_video(script_json, title, f"short_{ts}.mp4")
        if ps:
            local_fb_video = ps
            vid_short_id, vid_short_url = youtube_manager.upload_video_to_youtube(ps, f"{title[:50]} #Shorts", "Quick Review", ["shorts", category])

        # ======================================================================
        # 7. ASSET INJECTION & PUBLISHING
        # ======================================================================
        log("   🔗 Injecting Assets into HTML...")

        # Note: Videos and Research Images are already injected via Contextual Replacement.
        # We only need to inject the "Featured Image" (Thumbnail) at the top.

        image_html = ""
        if img_url:
            image_html = f'<div class="featured-image" style="text-align: center; margin-bottom: 35px;"><img src="{img_url}" style="width: 100%; border-radius: 15px;" alt="{title}"></div>'

        # Combine Featured Image + Body (Video is inside Body)
        full_body_html = image_html + full_body_html

        log("   🚀 [Publishing] Initial Draft...")
        pub_result = publisher.publish_post(title, full_body_html, [category])
        published_url, post_id = (pub_result if isinstance(pub_result, tuple) else (pub_result, None))

        if not published_url or not post_id:
            log("   ❌ CRITICAL FAILURE: Could not publish the initial draft.")
            return False

        # ======================================================================
        # 7.5 QUALITY IMPROVEMENT LOOP (AUDIT -> REMEDY -> UPDATE)
        # ======================================================================
        quality_score, attempts, MAX_RETRIES = 0, 0, 3 
        
        while quality_score < 9.5 and attempts < MAX_RETRIES:
            attempts += 1
            log(f"   🔄 [Quality Loop] Audit Round {attempts}...")
            
            # 1. Auditor visits the LIVE URL
            audit_report = live_auditor.audit_live_article(published_url, target_keyword, iteration=attempts)
            
            if not audit_report:
                log("      ⚠️ Quality Audit failed to return a report. Skipping loop.")
                break
            
            quality_score = float(audit_report.get('quality_score', 0))
            
            if quality_score >= 9.5:
                log(f"      🌟 Excellence Achieved! Score: {quality_score}/10. No further fixes needed.")
                break
            
            log(f"      ⚠️ Score {quality_score}/10. Auditor found issues. Starting surgery...")
            
            # 2. Remedy Agent fixes the content
            fixed_html = remedy.fix_article_content(
                full_body_html, 
                audit_report, 
                target_keyword, 
                combined_text, 
                iteration=attempts
            )
            
            # 3. Update on Blogger
            if fixed_html and len(fixed_html) > 1000:
                if publisher.update_existing_post(post_id, title, fixed_html):
                    full_body_html = fixed_html
                    log(f"      ✅ Article updated on Blogger. Waiting for sync...")
                    time.sleep(10) 
                else:
                    log("      ❌ Failed to update the post on Blogger. Breaking loop.")
                    break
            else:
                log("      ⚠️ Remedy agent failed to produce a valid fix. Breaking loop.")
                break

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
            
            # Use IDs for updating description (Fixed Variable Name Bug)
            if vid_main_id: youtube_manager.update_video_description(vid_main_id, yt_update_text)
            if vid_short_id: youtube_manager.update_video_description(vid_short_id, yt_update_text)
            
            social_manager.distribute_content(fb_caption, published_url, img_url)
            if local_fb_video:
                social_manager.post_reel_to_facebook(local_fb_video, fb_caption, published_url)
        except Exception as e: 
            log(f"   ⚠️ Social Distribution Error: {e}")
        
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
