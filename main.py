# FILE: main.py
# ROLE: Orchestrator V10.0 (Safe Mode: No Auto-Correction)
# DESCRIPTION: Full pipeline BUT skips the Live Auditor & Remedy steps 
#              to prevent accidental deletion of assets.

import os
import json
import time
import random
import datetime
import urllib.parse
import traceback
import re

# --- Core Configurations & Modules ---
from config import log
import api_manager
import news_fetcher
import scraper
import image_processor
import history_manager
import publisher
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
import reddit_manager

def run_pipeline(category, config, forced_keyword=None, is_cluster_topic=False):
    """
    Executes the full content lifecycle.
    NOTE: Quality Loop (Auditor/Remedy) is DISABLED in this version.
    """
    model_name = config['settings'].get('model_name', "gemini-2.5-flash")
    
    try:
        # ======================================================================
        # 1. STRATEGY & KEYWORD SELECTION
        # ======================================================================
        target_keyword = ""
        if forced_keyword:
            target_keyword = forced_keyword
        else:
            log(f"   👉 [Strategy] Scanning Category: {category}")
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
            visual_strategy = strategy_decision.get("visual_strategy", "hunt_for_video")
        except: visual_strategy = "hunt_for_video"

        # ======================================================================
        # 4. OMNI-HUNT (MULTI-LAYERED RESEARCH)
        # ======================================================================
        log("   🕵️‍♂️ Starting Omni-Hunt (Strict Sources)...")
        collected_sources = []
        
        # --- Layer 1: AI Smart Search ---
        try:
            ai_results = ai_researcher.smart_hunt(target_keyword, config, mode="general")
            if ai_results:
                vetted = news_fetcher.ai_vet_sources(ai_results, model_name)
                for item in vetted:
                    if len(collected_sources) >= 3: break
                    f_url, f_title, text, f_image, media = scraper.resolve_and_scrape(item['link'])
                    if text: collected_sources.append({"title": f_title or item['title'], "url": f_url, "text": text, "source_image": f_image, "media": media})
        except Exception as e: log(f"   ⚠️ AI Search Error: {e}")

        # --- Layer 2: Official Authority ---
        if len(collected_sources) < 2:
            try:
                official_results = ai_researcher.smart_hunt(target_keyword, config, mode="official")
                for item in official_results:
                    if len(collected_sources) >= 3: break
                    f_url, f_title, text, _, media = scraper.resolve_and_scrape(item['link'])
                    if text: collected_sources.append({"title": f_title or item['title'], "url": f_url, "text": text, "source_image": None, "media": media})
            except: pass

        # --- Layer 3: RSS Fallback ---
        if len(collected_sources) < 2:
            log("   ⚠️ Activating RSS Fallback...")
            raw_items = news_fetcher.get_real_news_rss(target_keyword, category)
            for item in raw_items:
                if len(collected_sources) >= 3: break
                f_url, f_title, text, f_image, media = scraper.resolve_and_scrape(item['link'])
                if text: collected_sources.append({"title": f_title or item['title'], "url": f_url, "text": text, "source_image": f_image, "media": media})

        if not collected_sources:
            log("   ❌ CRITICAL FAILURE: No sources found. Aborting.")
            return False

        # ======================================================================
        # 5. VISUAL ENFORCEMENT (STRICT: 3 IMAGES + 1 VIDEO)
        # ======================================================================
        log("   📸 Enforcing Visual Requirements (3 Images + 1 External Video)...")
        
        all_media = []
        for s in collected_sources: all_media.extend(s.get('media', []))
        
        # Filter valid ones
        valid_images = [m for m in all_media if m['type'] == 'image']
        valid_videos = [m for m in all_media if m['type'] == 'embed'] 
        
        # If missing, HUNT!
        if len(valid_images) < 3 or len(valid_videos) < 1:
            log("      ⚠️ Missing visuals. Launching Aggressive Hunt...")
            if len(valid_videos) < 1:
                hunted_vids = scraper.smart_media_hunt(target_keyword, category, "hunt_for_video")
                all_media.extend(hunted_vids)
            
            if len(valid_images) < 3:
                hunted_imgs = scraper.smart_media_hunt(target_keyword, category, "hunt_for_screenshot")
                all_media.extend(hunted_imgs)
            
            # Re-filter
            valid_images = [m for m in all_media if m['type'] == 'image']
            valid_videos = [m for m in all_media if m['type'] == 'embed']

        # Deduplicate
        unique_images = list({v['url']:v for v in valid_images}.values())
        unique_videos = list({v['url']:v for v in valid_videos}.values())
        
        log(f"      ✅ Final Count: {len(unique_images)} Images, {len(unique_videos)} External Videos.")

        # ======================================================================
        # 6. REDDIT INTEL
        # ======================================================================
        reddit_context, reddit_media = reddit_manager.get_community_intel(target_keyword)
        if reddit_media:
            for rm in reddit_media:
                if rm['type'] == 'embed': unique_videos.append(rm)
                elif rm['type'] == 'image': unique_images.append(rm)

        # ======================================================================
        # 7. ASSET PREPARATION & MAPPING
        # ======================================================================
        asset_map = {}
        available_tags = []
        
        # A) External Video (Source Video)
        if unique_videos:
            vid = unique_videos[0]
            tag = "[[VIDEO_SOURCE_1]]"
            html = f'<div class="video-wrapper"><iframe src="{vid["url"]}" allowfullscreen title="Source Video"></iframe></div>'
            asset_map[tag] = html
            available_tags.append(tag)
        else:
            tag = "[[VIDEO_SOURCE_1]]"
            asset_map[tag] = "" 
            
        # B) Images (Up to 3)
        for i, img in enumerate(unique_images[:3]):
            tag = f"[[IMAGE_{i+1}]]"
            html = f'''
            <figure style="margin:30px 0; text-align:center;">
                <img src="{img['url']}" alt="{img['description']}" style="max-width:100%; height:auto; border-radius:10px; border:1px solid #eee;">
                <figcaption style="font-size:14px; color:#666; margin-top:8px;">📸 {img['description']}</figcaption>
            </figure>
            '''
            asset_map[tag] = html
            available_tags.append(tag)

        # ======================================================================
        # 8. WRITING & SYNTHESIS
        # ======================================================================
        log("   ✍️ Writing Content...")
        combined_text = "\n".join([f"SOURCE: {s['url']}\n{s['text'][:8000]}" for s in collected_sources]) + reddit_context
        
        payload = {
            "keyword": target_keyword, 
            "research_data": combined_text, 
            "visual_strategy_directive": visual_strategy,
            "AVAILABLE_VISUAL_TAGS": available_tags,
            "TODAY_DATE": str(datetime.date.today())
        }
        
        json_b = api_manager.generate_step_strict(model_name, PROMPT_B_TEMPLATE.format(json_input=json.dumps(payload), forbidden_phrases="[]"), "Writer", ["headline", "article_body"])
        
        # Contextual Replacement
        final_body_draft = json_b['article_body']
        for tag, html_code in asset_map.items():
            if tag in final_body_draft:
                final_body_draft = final_body_draft.replace(tag, html_code)
            else:
                if "VIDEO" in tag and html_code: 
                    final_body_draft += f"\n<h3>Watch the Demo</h3>{html_code}"
        
        json_b['article_body'] = final_body_draft

        # ======================================================================
        # 9. SEO & HUMANIZER
        # ======================================================================
        sources_data = [{"title": s['title'], "url": s['url']} for s in collected_sources if s.get('url')]
        kg_links = history_manager.get_relevant_kg_for_linking(json_b['headline'], category)
        
        json_c = api_manager.generate_step_strict(model_name, PROMPT_C_TEMPLATE.format(json_input=json.dumps({"draft_content": json_b, "sources_data": sources_data}), knowledge_graph=kg_links), "SEO", ["finalTitle", "finalContent"])
        final_article = api_manager.generate_step_strict(model_name, PROMPT_D_TEMPLATE.format(json_input=json.dumps(json_c)), "Humanizer", ["finalTitle", "finalContent"])
        
        title, full_body_html = final_article['finalTitle'], final_article['finalContent']

        # ======================================================================
        # 10. THUMBNAIL (SOURCE FIRST STRATEGY)
        # ======================================================================
        log("   🎨 Processing Thumbnail (Source First)...")
        best_source_img = None
        for s in collected_sources:
            if s.get('source_image'): 
                best_source_img = s['source_image']
                break
        
        overlay_txt = final_article.get('imageOverlayText', 'REVIEW')
        img_url = image_processor.generate_and_upload_image(
            final_article.get('imageGenPrompt', title), 
            overlay_text=overlay_txt,
            source_url=best_source_img,
            title=title
        )

        # ======================================================================
        # 11. SYSTEM VIDEO PRODUCTION
        # ======================================================================
        log("   🎬 Producing System Video...")
        vid_main_id, vid_main_url = None, None
        vid_short_id, vid_short_url = None, None
        local_fb_video = None
        
        summ = re.sub('<[^<]+?>', '', full_body_html)[:1000]
        vs = api_manager.generate_step_strict(model_name, PROMPT_VIDEO_SCRIPT.format(title=title, text_summary=summ), "Video Script")
        script_json = vs.get('video_script', [])

        # Main Video
        rr = video_renderer.VideoRenderer(output_dir="output")
        pm = rr.render_video(script_json, title, f"main_{int(time.time())}.mp4")
        if pm:
            vid_main_id, vid_main_url = youtube_manager.upload_video_to_youtube(pm, title, "Tech Review", ["tech", category])
        
        # Shorts Video
        rs = video_renderer.VideoRenderer(output_dir="output", width=1080, height=1920)
        ps = rs.render_video(script_json, title, f"short_{int(time.time())}.mp4")
        if ps:
            local_fb_video = ps
            vid_short_id, vid_short_url = youtube_manager.upload_video_to_youtube(ps, f"{title} #Shorts", "Quick Review", ["shorts", category])

        # ======================================================================
        # 12. FINAL INJECTION (THUMBNAIL + SYSTEM VIDEO)
        # ======================================================================
        log("   🔗 Injecting Final Assets...")

        # A) Inject Thumbnail
        if img_url:
            full_body_html = f'<div class="featured-image" style="text-align: center; margin-bottom: 35px;"><img src="{img_url}" style="width: 100%; border-radius: 15px;" alt="{title}"></div>' + full_body_html

        # B) Inject System Video
        if vid_main_url:
            sys_vid_html = f'''
            <div class="video-wrapper system-video" style="margin: 30px 0; border: 2px solid #008069; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.1);">
                <p style="background: #008069; color: white; padding: 8px 15px; margin: 0; font-weight: bold; font-family: sans-serif;">📺 Watch Our Summary</p>
                <div style="position:relative;padding-bottom:56.25%;height:0;overflow:hidden;">
                    <iframe src="{vid_main_url}" style="position:absolute;top:0;left:0;width:100%;height:100%;border:0;" allowfullscreen title="Video Summary"></iframe>
                </div>
            </div>
            '''
            if "</h2>" in full_body_html:
                full_body_html = full_body_html.replace("</h2>", "</h2>" + sys_vid_html, 1)
            else:
                full_body_html = sys_vid_html + full_body_html

        # ======================================================================
        # 13. PUBLISH (INITIAL DRAFT)
        # ======================================================================
        log("   🚀 [Publishing] Initial Draft...")
        pub_result = publisher.publish_post(title, full_body_html, [category])
        if not pub_result:
            log("   ❌ CRITICAL FAILURE: Could not publish.")
            return False
            
        published_url, post_id = pub_result

        # ======================================================================
        # 14. QUALITY IMPROVEMENT LOOP (DISABLED)
        # ======================================================================
        # تم تعطيل هذا الجزء بناءً على طلبك لتجنب مشاكل الحذف
        log("   🛑 Skipping Quality Loop (Auditor/Remedy) as requested.")
        
        # quality_score, attempts, MAX_RETRIES = 0, 0, 3 
        # while quality_score < 9.5 and attempts < MAX_RETRIES:
        #     attempts += 1
        #     log(f"   🔄 [Quality Loop] Audit Round {attempts}...")
        #     audit_report = live_auditor.audit_live_article(published_url, target_keyword, iteration=attempts)
        #     if not audit_report: break
        #     quality_score = float(audit_report.get('quality_score', 0))
        #     if quality_score >= 9.5: break
        #     fixed_html = remedy.fix_article_content(full_body_html, audit_report, target_keyword, combined_text, iteration=attempts)
        #     if fixed_html and len(fixed_html) > 1000:
        #         if publisher.update_existing_post(post_id, title, fixed_html):
        #             full_body_html = fixed_html
        #             time.sleep(10) 
        #         else: break
        #     else: break

        # ======================================================================
        # 15. FINALIZATION & DISTRIBUTION
        # ======================================================================
        history_manager.update_kg(title, published_url, category, post_id)
        try: indexer.submit_url(published_url)
        except: pass
        
        try:
            fb_dat = api_manager.generate_step_strict(model_name, PROMPT_FACEBOOK_HOOK.format(title=title), "FB Hook", ["FB_Hook"])
            fb_caption = fb_dat.get('FB_Hook', title)
            
            yt_update_text = f"👇 Read the full technical analysis:\n{published_url}"
            
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
            
            # 1. Cluster Strategy
            try:
                topic, is_c = cluster_manager.get_strategic_topic(cat, cfg)
                if topic and run_pipeline(cat, cfg, forced_keyword=topic, is_cluster_topic=is_c):
                    published = True
            except: pass
            if published: break
            
            # 2. Trending Focus
            if cfg['categories'][cat].get('trending_focus'):
                topics = [t.strip() for t in cfg['categories'][cat]['trending_focus'].split(',')]
                for topic in topics:
                    if run_pipeline(cat, cfg, forced_keyword=topic, is_cluster_topic=False):
                        published = True; break
            if published: break
            
            # 3. General Hunt
            if run_pipeline(cat, cfg, is_cluster_topic=False):
                published = True
            if published: break
        
        if published: log("\n✅ MISSION COMPLETE.")
        else: log("\n❌ MISSION FAILED: No topics met the quality threshold today.")
            
    except Exception as e: log(f"❌ CRITICAL MAIN ERROR: {e}")

if __name__ == "__main__":
    main()
