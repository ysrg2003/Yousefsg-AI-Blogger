# FILE: main.py
# ROLE: Orchestrator V7.2 (Final Integrity Version)
# DESCRIPTION: The complete, final version integrating all modules and fixes, 
# including the restored Author Box with social links.

import os
import json
import time
import random
import sys
import datetime
import urllib.parse
import traceback
import re

# --- Core Configurations ---
from config import log, FORBIDDEN_PHRASES, ARTICLE_STYLE, BORING_KEYWORDS

# --- Standard Modules ---
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

# --- NEW GENERATION MODULES (V6/V7) ---
import cluster_manager
import indexer
import gardener
import ai_researcher

def run_pipeline(category, config, forced_keyword=None, is_cluster_topic=False):
    """
    Executes the full content lifecycle:
    Strategy -> Smart Research -> Synthesis -> Media Production -> Publishing -> Distribution.
    """
    model_name = config['settings'].get('model_name', "gemini-3-flash-preview")
    
    try:
        # ======================================================================
        # 1. STRATEGY & KEYWORD SELECTION
        # ======================================================================
        target_keyword = ""
        
        if forced_keyword:
            strategy_type = "Cluster Strategy" if is_cluster_topic else "Manual Fallback"
            log(f"   👉 [Strategy: {strategy_type}] Target: '{forced_keyword}'")
            target_keyword = forced_keyword
        else:
            log(f"   👉 [Strategy: AI Daily Hunt] Scanning Category: {category}")
            recent_history = history_manager.get_recent_titles_string(category=category)
            try:
                seo_p = PROMPT_ZERO_SEO.format(category=category, date=datetime.date.today(), history=recent_history)
                seo_plan = api_manager.generate_step_strict(
                    model_name, seo_p, "SEO Strategy", required_keys=["target_keyword"]
                )
                target_keyword = seo_plan.get('target_keyword')
                log(f"   🎯 AI SEO Goal: {target_keyword}")
            except Exception as e:
                log(f"   ❌ SEO Strategy failed: {e}")
                return False

        if not target_keyword: return False

        # ======================================================================
        # 2. SEMANTIC GUARD (Anti-Repetition)
        # ======================================================================
        if not is_cluster_topic:
            log("   🧠 Checking memory to avoid repetition...")
            history_str = history_manager.get_recent_titles_string(limit=200)
            if history_manager.check_semantic_duplication(target_keyword, history_str):
                log(f"   🚫 Duplication detected for '{target_keyword}'. Stopping.")
                return False
        else:
            log("   🛡️ Cluster Topic detected. Bypassing semantic guard.")

        # ======================================================================
        # 3. CREATIVE DIRECTOR (Visual Strategy)
        # ======================================================================
        log("   🎬 [Creative Director] Deciding on visual strategy...")
        try:
            strategy_prompt = PROMPT_VISUAL_STRATEGY.format(target_keyword=target_keyword, category=category)
            strategy_decision = api_manager.generate_step_strict(
                model_name, strategy_prompt, "Visual Strategy", required_keys=["visual_strategy"]
            )
            visual_strategy = strategy_decision.get("visual_strategy", "generate_comparison_table")
            log(f"      👉 Directive Received: '{visual_strategy}'")
        except Exception as e:
            visual_strategy = "generate_comparison_table"

        # ======================================================================
        # 4. OMNI-HUNT (Robust, Multi-Phase Research)
        # ======================================================================
        log("   🕵️‍♂️ Starting Omni-Hunt Mission...")
        
        collected_sources = []
        media_from_news = []
        
        # --- Phase A: AI Grounding Research (Primary) ---
        try:
            raw_ai_leads = ai_researcher.smart_hunt(target_keyword, config, mode="general")
            if raw_ai_leads:
                vetted_items = news_fetcher.ai_vet_sources(raw_ai_leads, model_name)
                for item in vetted_items:
                    if len(collected_sources) >= 3: break
                    f_url, f_title, text, f_image, media_in_source = scraper.resolve_and_scrape(item['link'])
                    if text:
                        collected_sources.append({"title": f_title or item['title'], "url": f_url, "text": text, "date": item.get('date', 'Today'), "source_image": f_image, "domain": urllib.parse.urlparse(f_url).netloc})
                        if media_in_source: media_from_news.extend(media_in_source)
        except Exception as e:
            log(f"   ⚠️ AI Researcher module encountered an issue: {e}")

        # --- Phase B: Legacy Keyword Fallback ---
        if len(collected_sources) < 2:
            log("   ⚠️ AI Research yielded low results. Switching to Keyword Extraction Strategies...")
            core_topic = news_fetcher.clean_search_query(target_keyword)
            legacy_strategies = [f'"{target_keyword}"', f'{core_topic} news', core_topic]
            
            for strategy in legacy_strategies:
                if len(collected_sources) >= 2: break
                raw_items = news_fetcher.get_gnews_api_sources(strategy, category)
                if not raw_items: raw_items = news_fetcher.get_real_news_rss(strategy, category)
                if not raw_items: continue
                vetted_items = news_fetcher.ai_vet_sources(raw_items, model_name)
                for item in vetted_items:
                    if len(collected_sources) >= 2: break
                    if any(s['url'] == item['link'] for s in collected_sources): continue
                    f_url, f_title, text, f_image, media_in_source = scraper.resolve_and_scrape(item['link'])
                    if text:
                        collected_sources.append({"title": f_title or item['title'], "url": f_url, "text": text, "date": item.get('date', 'Today'), "source_image": f_image, "domain": urllib.parse.urlparse(f_url).netloc})
                        if media_in_source: media_from_news.extend(media_in_source)
                time.sleep(1)

        # --- Phase C: Official Authority Fallback ---
        if len(collected_sources) == 0:
            log("   ⚠️ News search failed. Switching to Authority Search (Docs/GitHub)...")
            official_sources = ai_researcher.smart_hunt(target_keyword, config, mode="official")
            if official_sources:
                for src in official_sources:
                    collected_sources.append({"title": src.get('title', 'Official Doc'), "url": src['url'], "text": f"OFFICIAL SOURCE: {src.get('snippet','')}", "source_image": None, "domain": "official-authority"})

        # --- Phase D: Internal Knowledge Overdrive (Last Resort) ---
        if len(collected_sources) == 0:
            if is_cluster_topic:
                log("   ⚠️ Total Research Failure. Utilizing AI Internal Knowledge Base...")
                collected_sources.append({"title": "Expert Knowledge", "url": "", "text": f"SYSTEM OVERRIDE: Write a deep technical guide about '{target_keyword}'.", "source_image": None, "domain": "internal"})
            else:
                log("   ❌ Failed to collect sufficient sources. Aborting.")
                return False

        # ======================================================================
        # 5. VISUAL HUNT & REDDIT INTEL
        # ======================================================================
        official_media = []
        if visual_strategy.startswith("hunt_for_"):
            official_media = scraper.smart_media_hunt(target_keyword, category, visual_strategy)
        
        reddit_context, reddit_media = reddit_manager.get_community_intel(target_keyword)

        # ======================================================================
        # 6. VISUAL SELECTION & HTML PREP
        # ======================================================================
        all_visuals = media_from_news + official_media + reddit_media
        unique_visuals = list({v['url']:v for v in all_visuals}.values())
        unique_visuals.sort(key=lambda x: x.get('score', 0), reverse=True)
        
        visual_evidence_html = ""
        if unique_visuals:
            clean_visuals = [v for v in unique_visuals if not any(bad in v['url'].lower() for bad in scraper.MEDIA_LINK_BLACKLIST)]
            if clean_visuals:
                best_visual = clean_visuals[0]
                v_type, v_url = best_visual['type'], best_visual['url']
                caption = f"<figcaption>Source: {urllib.parse.urlparse(v_url).netloc}</figcaption>"
                if v_type == "embed":
                    visual_evidence_html = f'<div class="video-container"><iframe src="{v_url}" frameborder="0" allowfullscreen loading="lazy"></iframe></div>{caption}'
                elif v_type in ["gif", "image"]:
                    visual_evidence_html = f'<div class="gif-container"><img src="{v_url}" alt="Visual Evidence">{caption}</div>'

        if not visual_evidence_html and visual_strategy.startswith("hunt_for_"):
            visual_strategy = "generate_comparison_table"

        # ======================================================================
        # 7. SYNTHESIS (Writer -> SEO -> Humanizer)
        # ======================================================================
        log("   ✍️ Synthesizing Content...")
        
        combined_text_data = ""
        for i, src in enumerate(collected_sources):
            combined_text_data += f"\n--- SOURCE {i+1}: {src['domain']} ---\nURL: {src['url']}\nCONTENT:\n{src['text'][:9000]}\n"
        if reddit_context: combined_text_data += f"\n\n{reddit_context}\n"
        
        payload = {"keyword": target_keyword, "category": category, "visual_strategy_directive": visual_strategy, "pre_generated_visual_html": visual_evidence_html, "source_count": len(collected_sources), "research_data": combined_text_data}
        
        json_b = api_manager.generate_step_strict(model_name, PROMPT_B_TEMPLATE.format(json_input=json.dumps(payload), forbidden_phrases=str(FORBIDDEN_PHRASES)), "Step B (Writer)", required_keys=["headline", "article_body"])
        kg_links = history_manager.get_relevant_kg_for_linking(json_b.get('headline', target_keyword), category)
        input_c = {"draft_content": json_b, "sources_data": [{"title": s['title'], "url": s['url']} for s in collected_sources if s.get('url')]}
        json_c = api_manager.generate_step_strict(model_name, PROMPT_C_TEMPLATE.format(json_input=json.dumps(input_c), knowledge_graph=kg_links), "Step C (SEO)", required_keys=["finalTitle", "finalContent"])
        final_article = api_manager.generate_step_strict(model_name, PROMPT_D_TEMPLATE.format(json_input=json.dumps(json_c)), "Step D (Humanizer)", required_keys=["finalTitle", "finalContent"])
        
        title, content_html = final_article.get('finalTitle', target_keyword), final_article.get('finalContent', '')

        # ======================================================================
        # 8. ASSETS GENERATION (Images & Video)
        # ======================================================================
        log("   🖼️ [Image Mission] Starting...")
        img_url = None
        candidate_images = [{'url': src['source_image']} for src in collected_sources if src.get('source_image')]
        if candidate_images:
            selected_img_url = image_processor.select_best_image_with_gemini(model_name, title, candidate_images)
            if selected_img_url:
                img_url = image_processor.process_source_image(selected_img_url, final_article.get('imageOverlayText'), title)
        if not img_url:
            img_url = image_processor.generate_and_upload_image(final_article.get('imageGenPrompt', title), final_article.get('imageOverlayText'))

        log("   🎬 [Video Mission] Producing YouTube & Shorts...")
        vid_main, vid_short, vid_html_block, local_fb_video = None, None, "", None
        clean_summary = re.sub('<[^<]+?>','', content_html)[:2500]
        try:
            v_script_data = api_manager.generate_step_strict(model_name, PROMPT_VIDEO_SCRIPT.format(title=title, text_summary=clean_summary), "Video Script")
            script_json = v_script_data.get('video_script')
            if script_json:
                v_meta = api_manager.generate_step_strict(model_name, PROMPT_YOUTUBE_METADATA.format(draft_title=title), "YT Meta", required_keys=["title"])
                ts = int(time.time())
                out_dir = os.path.abspath("output")
                os.makedirs(out_dir, exist_ok=True)
                rr = video_renderer.VideoRenderer(output_dir=out_dir, width=1920, height=1080)
                path_main = rr.render_video(script_json, title, f"main_{ts}.mp4")
                if path_main:
                    v_desc = f"{v_meta.get('description','')}\n\n#{category.replace(' ','')}"
                    vid_main, _ = youtube_manager.upload_video_to_youtube(path_main, title[:100], v_desc, v_meta.get('tags',[]))
                    if vid_main: vid_html_block = f'<div class="video-container"><iframe src="https://www.youtube.com/embed/{vid_main}" frameborder="0" allowfullscreen></iframe></div>'
                rs = video_renderer.VideoRenderer(output_dir=out_dir, width=1080, height=1920)
                path_short = rs.render_video(script_json, title, f"short_{ts}.mp4")
                if path_short:
                    local_fb_video = path_short
                    vid_short, _ = youtube_manager.upload_video_to_youtube(path_short, f"{title[:90]} #Shorts", v_desc, v_meta.get('tags',[])+['shorts'])
        except Exception as ve: log(f"      ⚠️ Video Production Error: {ve}")

        # ======================================================================
        # 9. VALIDATION & FINAL ASSEMBLY
        # ======================================================================
        log("   🛡️ [Validation] Performing Core Surgery...")
        try:
            healer = content_validator_pro.AdvancedContentValidator()
            content_html = healer.run_professional_validation(content_html, combined_text_data, collected_sources)
        except Exception as he: log(f"      ⚠️ Validator skipped: {he}")

        # --- AUTHOR BOX (RESTORED & FINAL) ---
        author_box_html = """
        <div style="margin-top:50px; padding:30px; background:#f9f9f9; border-left: 6px solid #2ecc71; border-radius:12px; font-family:sans-serif; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">
            <div style="display:flex; align-items:flex-start; flex-wrap:wrap; gap:25px;">
                <img src="https://blogger.googleusercontent.com/img/a/AVvXsEiB6B0pK8PhY0j0JrrYCSG_QykTjsbxbbdePdNP_nRT_39FW4SGPPqTrAjendimEUZdipHUiYJfvHVjTBH7Eoz8vEjzzCTeRcDlIcDrxDnUhRJFJv4V7QHtileqO4wF-GH39vq_JAe4UrSxNkfjfi1fDS9_T4mPmwEC71VH9RJSEuSFrNb2ZRQedyA61iQ=s1017-rw" 
                     style="width:90px; height:90px; border-radius:50%; object-fit:cover; border:4px solid #fff; box-shadow:0 2px 8px rgba(0,0,0,0.1);" alt="Yousef S.">
                <div style="flex:1;">
                    <h4 style="margin:0; font-size:22px; color:#2c3e50; font-weight:800;">Yousef S. | Latest AI</h4>
                    <span style="font-size:12px; background:#e8f6ef; color:#2ecc71; padding:4px 10px; border-radius:6px; font-weight:bold;">TECH EDITOR</span>
                    <p style="margin:15px 0; color:#555; line-height:1.7;">Testing AI tools so you don't break your workflow. Brutally honest reviews, simple explainers, and zero fluff.</p>
                    <div style="display:flex; gap:15px; margin-top:10px; flex-wrap:wrap;">
                        <a href="https://www.facebook.com/share/1AkVHBNbV1/" target="_blank" style="text-decoration:none; opacity:0.8; transition:0.3s;" title="Facebook"><img src="https://cdn-icons-png.flaticon.com/512/5968/5968764.png" width="24" height="24" alt="FB"></a>
                        <a href="https://x.com/latestaime" target="_blank" style="text-decoration:none; opacity:0.8; transition:0.3s;" title="X (Twitter)"><img src="https://cdn-icons-png.flaticon.com/512/5969/5969020.png" width="24" height="24" alt="X"></a>
                        <a href="https://www.instagram.com/latestai.me" target="_blank" style="text-decoration:none; opacity:0.8; transition:0.3s;" title="Instagram"><img src="https://cdn-icons-png.flaticon.com/512/3955/3955024.png" width="24" height="24" alt="IG"></a>
                        <a href="https://m.youtube.com/@0latestai" target="_blank" style="text-decoration:none; opacity:0.8; transition:0.3s;" title="YouTube"><img src="https://cdn-icons-png.flaticon.com/512/1384/1384060.png" width="24" height="24" alt="YT"></a>
                        <a href="https://pinterest.com/latestaime" target="_blank" style="text-decoration:none; opacity:0.8; transition:0.3s;" title="Pinterest"><img src="https://cdn-icons-png.flaticon.com/512/145/145808.png" width="24" height="24" alt="Pin"></a>
                        <a href="https://reddit.com/user/Yousefsg/" target="_blank" style="text-decoration:none; opacity:0.8; transition:0.3s;" title="Reddit"><img src="https://cdn-icons-png.flaticon.com/512/3536/3536761.png" width="24" height="24" alt="Reddit"></a>
                        <a href="https://www.latestai.me" target="_blank" style="text-decoration:none; opacity:0.8; transition:0.3s;" title="Website"><img src="https://cdn-icons-png.flaticon.com/512/1006/1006771.png" width="24" height="24" alt="Web"></a>
                    </div>
                </div>
            </div>
        </div>
        """
        schema_json = f'\n<script type="application/ld+json">{json.dumps(final_article["schemaMarkup"])}</script>' if 'schemaMarkup' in final_article and final_article['schemaMarkup'] else ""
        primary_img_html = f'<div class="separator"><a href="{img_url}"><img src="{img_url}" width="1200" height="630"/></a></div>' if img_url else ""
        full_article_body = ARTICLE_STYLE + primary_img_html + vid_html_block + content_html + author_box_html + schema_json

        # ======================================================================
        # 10. PUBLISHING & DISTRIBUTION
        # ======================================================================
        log(f"   🚀 [Publishing] Sending to Blogger...")
        pub_result = publisher.publish_post(title, full_article_body, [category, "Tech Insights", "AI Evolution"])
        
        published_url, post_id = (pub_result if isinstance(pub_result, tuple) else (pub_result, None))

        if published_url:
            log(f"   ✅ [SUCCESS] Article live at: {published_url}")
            
            history_manager.update_kg(title, published_url, category, post_id)
            
            try: indexer.submit_url(published_url)
            except: pass
            
            try:
                fb_hook_data = api_manager.generate_step_strict(model_name, PROMPT_FACEBOOK_HOOK.format(title=title), "FB Hook", required_keys=["FB_Hook"])
                fb_caption = fb_hook_data.get('FB_Hook', title)
                yt_update_text = f"👇 Read the full technical analysis:\n{published_url}"
                if vid_main: youtube_manager.update_video_description(vid_main, yt_update_text)
                if vid_short: youtube_manager.update_video_description(vid_short, yt_update_text)
                social_manager.distribute_content(fb_caption, published_url, img_url)
                if local_fb_video:
                    social_manager.post_reel_to_facebook(local_fb_video, fb_caption, published_url)
            except Exception as social_e:
                log(f"   ⚠️ Distribution update failed: {social_e}")
            
            return True
        else:
            log("   ❌ Blogger API failed to publish.")
            return False

    except Exception as e:
        log(f"❌ PIPELINE CRASHED: {e}")
        traceback.print_exc()
        return False

def main():
    """
    EntryPoint V7.2: Gardener -> Cluster -> Manual/Daily Hunt.
    """
    try:
        with open('config_advanced.json','r') as f: cfg = json.load(f)
            
        log("\n🌱 [Phase 1] Running Digital Gardener...")
        try: gardener.run_daily_maintenance(cfg)
        except Exception as ge: log(f"⚠️ Gardener failed: {ge}")
        
        all_categories = list(cfg['categories'].keys())
        random.shuffle(all_categories)
        log(f"🎲 Session Sequence: {all_categories}")
        
        published_successfully = False
        
        for current_cat in all_categories:
            log(f"\n📂 CATEGORY FOCUS: {current_cat}")
            
            # A. Cluster Strategy
            cluster_topic, is_cluster = None, False
            try:
                cluster_topic, is_cluster = cluster_manager.get_strategic_topic(current_cat, cfg)
            except Exception as ce:
                log(f"⚠️ Cluster manager failed: {ce}")

            if cluster_topic:
                if run_pipeline(current_cat, cfg, forced_keyword=cluster_topic, is_cluster_topic=is_cluster):
                    published_successfully = True
                    break
            
            # B. Manual Fallback
            trending_topics = cfg['categories'][current_cat].get('trending_focus', '')
            if trending_topics and not is_cluster:
                log(f"   ⚠️ Cluster failed. Checking Manual List...")
                topics_list = [t.strip() for t in trending_topics.split(',') if t.strip()]
                random.shuffle(topics_list)
                for manual_topic in topics_list:
                    if run_pipeline(current_cat, cfg, forced_keyword=manual_topic, is_cluster_topic=False):
                        published_successfully = True
                        break
                if published_successfully: break

            # C. AI Daily Hunt (Last Resort)
            if not published_successfully and not is_cluster:
                log(f"   ⚠️ Manual list exhausted. Attempting AI Daily Hunt...")
                if run_pipeline(current_cat, cfg, forced_keyword=None, is_cluster_topic=False):
                    published_successfully = True
                    break

        if published_successfully:
            log("\n✅ MISSION COMPLETE.")
            history_manager.perform_maintenance_cleanup()
        else:
            log("\n❌ MISSION FAILED: No articles met the quality threshold today.")
            
    except Exception as e:
        log(f"❌ CRITICAL ERROR IN MAIN: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
