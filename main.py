# FILE: main.py
# ROLE: The Ultimate Orchestrator V13.0 (The Hybrid Empire)
# DESCRIPTION: Merges the robust multi-layered hunt of V9.2 with the full 25-file integration.
#              Features: Omni-Hunt, Tech Surgeon, Quality Loop, and Global Distribution.

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
    تنفيذ دورة حياة المحتوى الكاملة باستخدام استراتيجية البحث متعددة الطبقات (V9.2) 
    مع دمج نظام التدقيق والجراحة التقنية.
    """
    model_name = config['settings'].get('model_name', "gemini-2.5-flash")
    client = ai_researcher.genai.Client(api_key=api_manager.key_manager.get_current_key())
    tech_surgeon = content_validator_pro.AdvancedContentValidator(model_name=model_name)
    
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
                log(f"   🚫 Duplication detected for '{target_keyword}'. Pivoting...")
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
        # 4. OMNI-HUNT (V13.0 - THE UNSTOPPABLE MULTI-LAYERED SEARCH)
        # ======================================================================
        log(f"   🕵️‍♂️ Starting Omni-Hunt for: {target_keyword} (Strict: 3+ Sources)")
        collected_sources = []
        
        # --- Layer 1: AI Smart Search (General News & Reviews) ---
        try:
            # نستخدم خطة البحث الزمنية لضمان الحداثة
            search_plan = ai_researcher.generate_search_plan(target_keyword, client, model_name)
            ai_results = ai_researcher.smart_hunt(search_plan['fresh_query'], mode="general")
            if ai_results:
                vetted = news_fetcher.ai_vet_sources(ai_results, model_name)
                for item in vetted:
                    if len(collected_sources) >= 3: break
                    f_url, f_title, text, f_image, media = scraper.resolve_and_scrape(item['link'])
                    if text: collected_sources.append({"title": f_title or item['title'], "url": f_url, "text": text, "source_image": f_image})
        except Exception as e: log(f"   ⚠️ Layer 1 Error: {e}")

        # --- Layer 2: AI Authority Search (Official Docs/GitHub) ---
        if len(collected_sources) < 3:
            log("   🔎 Layer 2: Hunting for Official Authority...")
            try:
                official_results = ai_researcher.smart_hunt(search_plan.get('official_query', target_keyword), mode="official")
                for item in official_results:
                    if len(collected_sources) >= 3: break
                    if any(s['url'] == item['link'] for s in collected_sources): continue
                    f_url, f_title, text, _, _ = scraper.resolve_and_scrape(item['link'])
                    if text: collected_sources.append({"title": f_title or item['title'], "url": f_url, "text": text, "source_image": None})
            except Exception as e: log(f"   ⚠️ Layer 2 Error: {e}")

        # --- Layer 3: Legacy Fallback (GNews API & RSS) ---
        if len(collected_sources) < 3:
            log("   ⚠️ Layer 3: Activating Legacy Fallback (GNews/RSS)...")
            core_entity = target_keyword
            try:
                extraction_prompt = f"Extract the full official name of the product from: '{target_keyword}'. Return ONLY the name."
                entity_response = api_manager.generate_step_strict(model_name, extraction_prompt, "Entity Extraction")
                core_entity = str(entity_response).strip('"{}\n: ')
            except: core_entity = " ".join(target_keyword.split()[:3])

            legacy_queries = [f'"{core_entity}" when:7d', core_entity]
            for q in legacy_queries:
                if len(collected_sources) >= 3: break
                raw_items = news_fetcher.get_gnews_api_sources(q, category) or news_fetcher.get_real_news_rss(q, category)
                vetted_items = news_fetcher.ai_vet_sources(raw_items, model_name)
                for item in vetted_items:
                    if len(collected_sources) >= 3: break
                    f_url, f_title, text, _, _ = scraper.resolve_and_scrape(item['link'])
                    if text: collected_sources.append({"title": f_title or item['title'], "url": f_url, "text": text, "source_image": None})

        # --- FINAL QUALITY GATE ---
        if len(collected_sources) < 3:
            log(f"   ❌ CRITICAL FAILURE: Found only {len(collected_sources)}/3 sources. Pivoting...")
            return False
        
        log(f"   ✅ Research Complete. Found {len(collected_sources)} high-quality sources.")

        # ======================================================================
        # 5. VISUAL HUNT & REDDIT INTEL
        # ======================================================================
        visual_evidence_html = ""
        # قنص الصور من البحث البصري الذكي
        visual_results = ai_researcher.smart_hunt(search_plan.get('visual_query', target_keyword), mode="visual")
        for vr in visual_results:
            f_url, f_title, _, f_image, _ = scraper.resolve_and_scrape(vr['link'])
            if f_image:
                visual_evidence_html += f'<div style="text-align:center; margin:25px 0;"><img src="{f_image}" style="max-width:100%; border-radius:12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);" alt="Evidence"><p><i>📸 Visual Proof: {f_title}</i></p></div>'

        reddit_context, reddit_media = reddit_manager.get_community_intel(target_keyword)

        # ======================================================================
        # 6. WRITING & TECH SURGERY
        # ======================================================================
        log("   ✍️ Synthesizing & Validating Content...")
        combined_text = "\n".join([f"SOURCE: {s['url']}\n{s['text'][:6000]}" for s in collected_sources]) + reddit_context
        payload = {"keyword": target_keyword, "research_data": combined_text, "visual_strategy_directive": visual_strategy, "PRE_GENERATED_VISUAL_HTML": visual_evidence_html}
        
        json_b = api_manager.generate_step_strict(model_name, PROMPT_B_TEMPLATE.format(json_input=json.dumps(payload), forbidden_phrases="[]"), "Writer")
        sources_data = [{"title": s['title'], "url": s['url']} for s in collected_sources]
        kg_links = history_manager.get_relevant_kg_for_linking(json_b['headline'], category)
        
        json_c = api_manager.generate_step_strict(model_name, PROMPT_C_TEMPLATE.format(json_input=json.dumps({"draft_content": json_b, "sources_data": sources_data}), knowledge_graph=kg_links), "SEO")
        final_article = api_manager.generate_step_strict(model_name, PROMPT_D_TEMPLATE.format(json_input=json.dumps(json_c)), "Humanizer")
        
        title, full_body_html = final_article['finalTitle'], final_article['finalContent']

        # الجراحة التقنية (إصلاح الروابط والـ HTML) قبل النشر
        full_body_html = tech_surgeon.run_professional_validation(full_body_html, combined_text, collected_sources)

        # ======================================================================
        # 7. ASSETS & VIDEO PRODUCTION
        # ======================================================================
        log("   🎨 Generating Assets...")
        img_url = image_processor.generate_and_upload_image(final_article.get('imageGenPrompt', title))
        
        log("   🎬 Video Studio: Rendering Main & Shorts...")
        summ = re.sub('<[^<]+?>', '', full_body_html)[:1000]
        vs = api_manager.generate_step_strict(model_name, PROMPT_VIDEO_SCRIPT.format(title=title, text_summary=summ), "Video Script")
        script_json = vs.get('video_script', [])
        
        ts = int(time.time())
        rr = video_renderer.VideoRenderer(output_dir="output")
        pm = rr.render_video(script_json, title, f"main_{ts}.mp4")
        vid_main_id, vid_main_url = None, None
        if pm: vid_main_id, vid_main_url = youtube_manager.upload_video_to_youtube(pm, title, "Technical Review", ["tech", category])
        
        rs = video_renderer.VideoRenderer(output_dir="output", width=1080, height=1920)
        ps = rs.render_video(script_json, title, f"short_{ts}.mp4")
        local_fb_video = ps
        vid_short_id, _ = None, None
        if ps: vid_short_id, _ = youtube_manager.upload_video_to_youtube(ps, f"{title[:50]} #Shorts", "Quick Review", ["shorts", category])

        # ======================================================================
        # 8. ASSET INJECTION & PUBLISHING
        # ======================================================================
        log("   🔗 Injecting Assets into HTML...")
        image_html = f'<div class="main-cover" style="text-align:center; margin-bottom:35px;"><img src="{img_url}" style="width:100%; border-radius:15px; box-shadow: 0 6px 20px rgba(0,0,0,0.15);" alt="{title}"></div>'
        video_html = f'<div class="yt-video" style="margin:30px 0; text-align:center;"><iframe width="100%" height="480" src="{vid_main_url}" frameborder="0" allowfullscreen style="border-radius:12px;"></iframe></div>' if vid_main_url else ""
        
        full_body_html = image_html + video_html + full_body_html
        
        log("   🚀 Publishing Initial Draft...")
        pub_result = publisher.publish_post(title, full_body_html, [category])
        published_url, post_id = (pub_result if isinstance(pub_result, tuple) else (pub_result, None))

        if not published_url or not post_id: return False

        # ======================================================================
        # 9. QUALITY LOOP (AUDIT -> REMEDY -> UPDATE)
        # ======================================================================
        quality_score, attempts, MAX_RETRIES = 0, 0, 3
        while quality_score < 9.5 and attempts < MAX_RETRIES:
            attempts += 1
            log(f"   🔄 [Quality Loop] Audit Round {attempts}...")
            audit_report = live_auditor.audit_live_article(published_url, target_keyword, iteration=attempts)
            if not audit_report: break
            
            quality_score = float(audit_report.get('quality_score', 0))
            if quality_score >= 9.5:
                log(f"      🌟 Excellence Achieved! Score: {quality_score}/10.")
                break
            
            log(f"      ⚠️ Score {quality_score}/10. Starting surgery...")
            fixed_html = remedy.fix_article_content(full_body_html, audit_report, target_keyword, combined_text, iteration=attempts)
            
            if fixed_html and len(fixed_html) > 1000:
                if publisher.update_existing_post(post_id, title, fixed_html):
                    full_body_html = fixed_html
                    log(f"      ✅ Article updated. Re-auditing...")
                    time.sleep(10)
                else: break
            else: break

        # ======================================================================
        # 10. FINALIZATION & DISTRIBUTION
        # ======================================================================
        history_manager.update_kg(title, published_url, category, post_id)
        indexer.submit_url(published_url)
        
        # تحديث وصف اليوتيوب برابط المقال
        yt_desc = f"👇 Full Technical Analysis & Screenshots:\n{published_url}"
        if vid_main_id: youtube_manager.update_video_description(vid_main_id, yt_desc)
        if vid_short_id: youtube_manager.update_video_description(vid_short_id, yt_desc)
        
        # فيسبوك
        fb_hook = api_manager.generate_step_strict(model_name, PROMPT_FACEBOOK_HOOK.format(title=title), "FB Hook")
        social_manager.distribute_content(fb_hook.get('FB_Hook', title), published_url, img_url)
        if local_fb_video:
            social_manager.post_reel_to_facebook(local_fb_video, fb_hook.get('FB_Hook', title), published_url)
            
        return True

    except Exception as e:
        log(f"❌ Pipeline Crashed: {e}")
        traceback.print_exc()
        return False

def main():
    try:
        with open('config_advanced.json','r') as f: cfg = json.load(f)
        gardener.run_daily_maintenance(cfg)
        
        cats = list(cfg['categories'].keys())
        random.shuffle(cats)
        
        for cat in cats:
            log(f"\n📂 CATEGORY: {cat}")
            # 1. محاولة العناقيد
            topic, is_c = cluster_manager.get_strategic_topic(cat, cfg)
            if topic and run_pipeline(cat, cfg, forced_keyword=topic, is_cluster_topic=is_c):
                break
            
            # 2. محاولة التريندات
            trending = cfg['categories'][cat].get('trending_focus', '').split(',')
            success = False
            for t in trending:
                if t.strip() and run_pipeline(cat, cfg, forced_keyword=t.strip()):
                    success = True; break
            if success: break
            
            # 3. البحث الحر
            if run_pipeline(cat, cfg): break
            
        log("\n✅ MISSION COMPLETE.")
    except Exception as e:
        log(f"❌ CRITICAL MAIN ERROR: {e}")

if __name__ == "__main__":
    main()
