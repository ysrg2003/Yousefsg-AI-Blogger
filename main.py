# FILE: main.py
# ROLE: Orchestrator V7.0 (The Empire Builder Edition)
# FEATURES: AI Grounding Research, Instant Indexing, Topic Clusters, Content Gardening.
# INTEGRITY: Full logic, no simplification.

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
import ai_researcher  # The New Smart Hunter

def run_pipeline(category, config, forced_keyword=None, is_cluster_topic=False):
    """
    The main autonomous pipeline.
    Strategy -> Smart AI Research -> Synthesis -> Multimedia -> Publishing -> Indexing.
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
            # Fallback: AI Daily Hunt (If Cluster Manager returned nothing)
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
        # If it's a Cluster Topic, we trust the plan and skip the check.
        # If it's a Daily Hunt, we must check for duplicates to prevent cannibalization.
        if not is_cluster_topic:
            log("   🧠 Checking memory to avoid repetition...")
            history_str = history_manager.get_recent_titles_string(limit=200)
            if history_manager.check_semantic_duplication(target_keyword, history_str):
                log(f"   🚫 Duplication detected for '{target_keyword}'. Stopping.")
                return False
        else:
            log("   🛡️ Cluster Topic detected. Bypassing semantic guard to ensure series continuity.")

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
            log(f"      ⚠️ Visual Strategy failed: {e}. Defaulting to 'generate_comparison_table'.")
            visual_strategy = "generate_comparison_table"

        # ======================================================================
        # 4. OMNI-HUNT (Phase A: AI Smart Research)
        # ======================================================================
        log("   🕵️‍♂️ Starting Omni-Hunt Mission (Powered by AI Grounding)...")
        
        collected_sources = []
        media_from_news = []
        
        # 1. AI Grounding Search (Priority #1)
        try:
            raw_ai_leads = ai_researcher.smart_hunt(target_keyword, config)
            
            if raw_ai_leads:
                # Vet sources found by AI (Just to be double sure)
                vetted_items = news_fetcher.ai_vet_sources(raw_ai_leads, model_name)
                
                for item in vetted_items:
                    if len(collected_sources) >= 3: break
                    
                    # Use Selenium to get full text
                    f_url, f_title, text, f_image, media_in_source = scraper.resolve_and_scrape(item['link'])
                    
                    if text:
                        collected_sources.append({
                            "title": f_title or item['title'],
                            "url": f_url,
                            "text": text,
                            "date": item.get('date', 'Today'),
                            "source_image": f_image,
                            "domain": urllib.parse.urlparse(f_url).netloc
                        })
                        if media_in_source: media_from_news.extend(media_in_source)
        except Exception as e:
            log(f"   ⚠️ AI Researcher module encountered an issue: {e}")

        # ======================================================================
        # 4. OMNI-HUNT (Phase B: Legacy Fallback)
        # ======================================================================
        # Only if AI Search returned nothing
        if len(collected_sources) < 1:
            log("   ⚠️ AI Research yielded low results. Switching to Keyword Extraction Strategies...")
            
            # Smart Keyword Extraction (Fixing the 'Keyword Stuffing' issue)
            # Remove "How to", "Guide", "News" to get the Core Entity
            stop_words = ["how to", "guide", "news", "update", "review", "analysis", "using", "build", "without", "writing", "code"]
            core_topic = target_keyword.replace('"', '').replace(":", "").lower()
            for sw in stop_words:
                core_topic = core_topic.replace(sw, "")
            
            core_topic = " ".join(core_topic.split()[:4]) # Limit to first 4 relevant words
            log(f"      🔍 Optimized Fallback Keyword: '{core_topic}'")

            legacy_strategies = [
                f'"{target_keyword}"',          # Exact match try
                f'{core_topic} news',           # Broad news
                f'{core_topic}'                 # Broadest fallback
            ]
            
            for strategy in legacy_strategies:
                if len(collected_sources) >= 2: break
                
                # Fetch raw links (GNews preferred here for robustness)
                raw_items = news_fetcher.get_gnews_api_sources(strategy, category)
                if not raw_items: raw_items = news_fetcher.get_real_news_rss(strategy, category)
                
                if not raw_items: continue
                
                # Filter through AI Auditor
                vetted_items = news_fetcher.ai_vet_sources(raw_items, model_name)

                for item in vetted_items:
                    if len(collected_sources) >= 2: break # We are okay with 2 sources in fallback mode
                    
                    if any(s['url'] == item['link'] for s in collected_sources): continue

                    # Scrape
                    f_url, f_title, text, f_image, media_in_source = scraper.resolve_and_scrape(item['link'])
                    
                    if text:
                        collected_sources.append({
                            "title": f_title or item['title'],
                            "url": f_url,
                            "text": text,
                            "date": item.get('date', 'Today'),
                            "source_image": f_image,
                            "domain": urllib.parse.urlparse(f_url).netloc
                        })
                        if media_in_source: media_from_news.extend(media_in_source)
                
                time.sleep(1)

        # ======================================================================
        # 4. OMNI-HUNT (Phase C: Internal Knowledge Overdrive)
        # ======================================================================
        # Absolute Last Resort for Cluster Topics
        if len(collected_sources) == 0:
            if is_cluster_topic:
                log("   ⚠️ Total Research Failure. Utilizing AI Internal Knowledge Base (Expert Mode)...")
                collected_sources.append({
                    "title": f"Expert Guide: {target_keyword}",
                    "url": "https://www.latestai.me", 
                    "text": f"SYSTEM INSTRUCTION: The researcher failed to find external links. You are now the primary expert source. Write a comprehensive, high-technical 2000-word guide about '{target_keyword}'. Focus on actionable steps, technical details, and solving the user problem deeply.",
                    "source_image": None,
                    "domain": "internal-knowledge"
                })
            else:
                log("   ❌ Failed to collect sources. Aborting.")
                return False

        # ======================================================================
        # 5. VISUAL HUNT & REDDIT INTEL
        # ======================================================================
        official_media = []
        reddit_media = []
        reddit_context = ""

        # Sniper Hunt (Google Images/Video for specific visual directive)
        if visual_strategy.startswith("hunt_for_"):
            log(f"   📸 Directive is 'Hunt'. Launching Dedicated Sniper...")
            official_media = scraper.smart_media_hunt(target_keyword, category, visual_strategy)
        
        # Reddit Hunt (Community Consensus)
        reddit_context, reddit_media = reddit_manager.get_community_intel(target_keyword)

        # ======================================================================
        # 6. VISUAL SELECTION & HTML PREP
        # ======================================================================
        all_visuals = media_from_news + official_media + reddit_media
        unique_visuals = list({v['url']:v for v in all_visuals}.values())
        unique_visuals.sort(key=lambda x: x.get('score', 0), reverse=True)
        
        visual_evidence_html = ""
        if unique_visuals:
            # Filter junk pixels/tracking scripts
            clean_visuals = [v for v in unique_visuals if not any(bad in v['url'].lower() for bad in scraper.MEDIA_LINK_BLACKLIST)]
            
            if clean_visuals:
                best_visual = clean_visuals[0]
                v_type = best_visual['type']
                v_url = best_visual['url']
                source_domain = urllib.parse.urlparse(v_url).netloc
                caption = f"<figcaption>Source: {source_domain}</figcaption>"
                
                if v_type == "embed":
                    visual_evidence_html = f'<div class="video-container" style="margin-bottom:10px;"><iframe src="{v_url}" frameborder="0" allowfullscreen loading="lazy"></iframe></div>{caption}'
                elif v_type == "video":
                     visual_evidence_html = f'''
                    <div class="prompt-card" style="text-align:center; padding:25px; background:#2c3e50; border-left:5px solid #3498db;">
                        <span class="prompt-label" style="color:#fff;">👁️ VIDEO DEMONSTRATION</span>
                        <p style="color:#ecf0f1; font-size:16px;">A video showcasing this feature is available from the official source.</p>
                        <a href="{v_url}" target="_blank" rel="noopener noreferrer" style="display:inline-block; padding:12px 24px; background:#3498db; color:white; text-decoration:none; border-radius:8px; margin-top:10px; font-weight:bold;">Watch Technical Demo</a>
                        {caption}
                    </div>'''
                elif v_type in ["gif", "image"]:
                    visual_evidence_html = f'<div class="gif-container" style="text-align:center; margin-bottom:20px;"><img src="{v_url}" alt="Demo" style="width:100%; border-radius:10px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);">{caption}</div>'

        if not visual_evidence_html and visual_strategy.startswith("hunt_for_"):
            visual_strategy = "generate_comparison_table" # Graceful degradation

        # ======================================================================
        # 7. SYNTHESIS (Writer -> SEO -> Humanizer)
        # ======================================================================
        log("   ✍️ Synthesizing Content...")
        
        combined_text_data = ""
        for i, src in enumerate(collected_sources):
            combined_text_data += f"\n--- SOURCE {i+1}: {src['domain']} ---\nURL: {src['url']}\nCONTENT:\n{src['text'][:9000]}\n"
        if reddit_context: combined_text_data += f"\n\n{reddit_context}\n"
        
        payload = {
            "keyword": target_keyword,
            "category": category,
            "visual_strategy_directive": visual_strategy,
            "pre_generated_visual_html": visual_evidence_html,
            "source_count": len(collected_sources),
            "research_data": combined_text_data
        }
        
        # Step B: Writer
        json_b = api_manager.generate_step_strict(
            model_name, 
            PROMPT_B_TEMPLATE.format(json_input=json.dumps(payload), forbidden_phrases=str(FORBIDDEN_PHRASES)), 
            "Step B (Writer)",
            required_keys=["headline", "article_body", "verdict"]
        )
        
        # Step C: SEO & Linking
        kg_links = history_manager.get_relevant_kg_for_linking(json_b.get('headline', target_keyword), category)
        input_c = {
            "draft_content": json_b, 
            "sources_data": [{"title": s['title'], "url": s['url']} for s in collected_sources if s['domain'] != 'internal-knowledge']
        }
        json_c = api_manager.generate_step_strict(
            model_name, 
            PROMPT_C_TEMPLATE.format(json_input=json.dumps(input_c), knowledge_graph=kg_links), 
            "Step C (SEO)",
            required_keys=["finalTitle", "finalContent"]
        )
        
        # Step D: Humanizer
        final_article = api_manager.generate_step_strict(
            model_name, 
            PROMPT_D_TEMPLATE.format(json_input=json.dumps(json_c)), 
            "Step D (Humanizing)",
            required_keys=["finalTitle", "finalContent"]
        )
        
        title = final_article.get('finalTitle', target_keyword)
        content_html = final_article.get('finalContent', '<p>Error generating content.</p>')

        # ======================================================================
        # 8. ASSETS GENERATION (Images & Video)
        # ======================================================================
        log("   🖼️ [Image Mission] Starting...")
        img_url = None
        candidate_images = [{'url': src['source_image']} for src in collected_sources if src.get('source_image')]
        
        # Smart Image Selection
        if candidate_images:
            selected_img_url = image_processor.select_best_image_with_gemini(model_name, title, candidate_images)
            if selected_img_url:
                img_url = image_processor.process_source_image(selected_img_url, final_article.get('imageOverlayText'), title)
        
        # Fallback to AI Image
        if not img_url:
            img_url = image_processor.generate_and_upload_image(final_article.get('imageGenPrompt', title), final_article.get('imageOverlayText'))

        # Video Production
        log("   🎬 [Video Mission] Producing YouTube & Shorts...")
        vid_main, vid_short, vid_html_block, local_fb_video = None, None, "", None
        clean_summary = re.sub('<[^<]+?>','', content_html)[:2500]
        
        try:
            v_script_data = api_manager.generate_step_strict(
                model_name, 
                PROMPT_VIDEO_SCRIPT.format(title=title, text_summary=clean_summary), 
                "Video Script"
            )
            script_json = v_script_data.get('video_script')
            
            if script_json:
                v_meta = api_manager.generate_step_strict(model_name, PROMPT_YOUTUBE_METADATA.format(draft_title=title), "YT Meta", required_keys=["title", "description"])
                ts_stamp = int(time.time())
                output_folder = os.path.abspath("output")
                os.makedirs(output_folder, exist_ok=True)
                
                # Render Main Video
                rr = video_renderer.VideoRenderer(output_dir=output_folder, width=1920, height=1080)
                path_main = rr.render_video(script_json, title, f"main_{ts_stamp}.mp4")
                if path_main:
                    v_desc = f"{v_meta.get('description','')}\n\n#{category.replace(' ','')}"
                    vid_main, _ = youtube_manager.upload_video_to_youtube(path_main, title[:100], v_desc, v_meta.get('tags',[]))
                    if vid_main:
                        vid_html_block = f'<div class="video-container" style="position:relative;padding-bottom:56.25%;height:0;overflow:hidden;margin:30px 0;border-radius:12px;"><iframe style="position:absolute;top:0;left:0;width:100%;height:100%;" src="https://www.youtube.com/embed/{vid_main}" frameborder="0" allowfullscreen></iframe></div>'
                
                # Render Shorts
                rs = video_renderer.VideoRenderer(output_dir=output_folder, width=1080, height=1920)
                path_short = rs.render_video(script_json, title, f"short_{ts_stamp}.mp4")
                if path_short:
                    local_fb_video = path_short
                    vid_short, _ = youtube_manager.upload_video_to_youtube(path_short, title[:90]+" #Shorts", v_desc, v_meta.get('tags',[])+['shorts'])
        except Exception as ve:
            log(f"      ⚠️ Video Production Error: {ve}")

        # ======================================================================
        # 9. VALIDATION & ASSEMBLY
        # ======================================================================
        log("   🛡️ [Validation] Performing Core Surgery...")
        try:
            healer = content_validator_pro.AdvancedContentValidator()
            content_html = healer.run_professional_validation(content_html, combined_text_data, collected_sources)
        except Exception as he:
            log(f"      ⚠️ Validator skipped: {he}")

        # Author Box
        author_box_html = """
        <div style="margin-top:60px; padding:35px; background:#fcfcfc; border-left: 6px solid #2ecc71; border-radius:15px; font-family:sans-serif; box-shadow: 0 5px 15px rgba(0,0,0,0.05);">
            <div style="display:flex; align-items:center; flex-wrap:wrap; gap:30px;">
                <img src="https://blogger.googleusercontent.com/img/a/AVvXsEiB6B0pK8PhY0j0JrrYCSG_QykTjsbxbbdePdNP_nRT_39FW4SGPPqTrAjendimEUZdipHUiYJfvHVjTBH7Eoz8vEjzzCTeRcDlIcDrxDnUhRJFJv4V7QHtileqO4wF-GH39vq_JAe4UrSxNkfjfi1fDS9_T4mPmwEC71VH9RJSEuSFrNb2ZRQedyA61iQ=s1017-rw" 
                     style="width:100px; height:100px; border-radius:50%; border:5px solid #fff; box-shadow:0 4px 12px rgba(0,0,0,0.1);" alt="Yousef S.">
                <div style="flex:1;">
                    <h4 style="margin:0; font-size:24px; color:#2c3e50; font-weight:900;">Yousef S. | Tech Editor</h4>
                    <span style="font-size:13px; background:#e8f6ef; color:#2ecc71; padding:5px 12px; border-radius:8px; font-weight:bold; letter-spacing:1px;">CRITICAL REVIEWER</span>
                    <p style="margin:15px 0; color:#444; line-height:1.8; font-size:16px;">I test the boundaries of AI so you don't have to. Brutally honest takes, deep technical dives, and zero marketing fluff.</p>
                </div>
            </div>
        </div>
        """

        # Schema JSON
        schema_json = ""
        if 'schemaMarkup' in final_article and final_article['schemaMarkup']:
            try: schema_json = f'\n<script type="application/ld+json">{json.dumps(final_article["schemaMarkup"])}</script>'
            except: pass

        # Final Body Assembly
        primary_img_html = f'<div class="separator" style="clear:both;text-align:center;margin-bottom:30px;"><a href="{img_url}"><img src="{img_url}" width="1200" height="630" style="max-width:100%; border-radius:12px; box-shadow:0 8px 25px rgba(0,0,0,0.15);" /></a></div>' if img_url else ""
        full_article_body = ARTICLE_STYLE + primary_img_html + vid_html_block + content_html + author_box_html + schema_json

        # ======================================================================
        # 10. PUBLISHING & DISTRIBUTION
        # ======================================================================
        log(f"   🚀 [Publishing] Sending to Blogger...")
        
        # Supports both single return (legacy) and tuple return (V6.0+)
        pub_result = publisher.publish_post(title, full_article_body, [category, "Tech Insights", "AI Evolution"])
        
        published_url = None
        post_id = None

        if isinstance(pub_result, tuple):
            published_url, post_id = pub_result
        else:
            published_url, post_id = pub_result, None

        if published_url:
            log(f"   ✅ [SUCCESS] Article live at: {published_url}")
            
            # 1. Update Knowledge Graph (With Post ID for Gardener)
            history_manager.update_kg(title, published_url, category, post_id)
            
            # 2. INSTANT INDEXING (Priority Feature)
            try: indexer.submit_url(published_url)
            except: pass
            
            # 3. Social Distribution
            try:
                fb_hook_data = api_manager.generate_step_strict(model_name, PROMPT_FACEBOOK_HOOK.format(title=title), "FB Hook", required_keys=["FB_Hook"])
                fb_caption = fb_hook_data.get('FB_Hook', title)
                
                # YouTube Update (Top of Description)
                yt_update_text = f"👇 Read the full technical analysis here:\n{published_url}"
                if vid_main: youtube_manager.update_video_description(vid_main, yt_update_text)
                if vid_short: youtube_manager.update_video_description(vid_short, yt_update_text)
                
                # Facebook & Reels
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
    EntryPoint V7.0:
    1. Gardener (Maintenance)
    2. Cluster Strategy (Priority #1)
    3. Manual Topics (Priority #2)
    4. AI Daily Hunt (Fallback #3)
    """
    try:
        if not os.path.exists('config_advanced.json'):
            log("❌ Error: config_advanced.json not found.")
            return
            
        with open('config_advanced.json','r') as f: 
            cfg = json.load(f)
            
        # --- PHASE 1: THE GARDENER (Maintenance) ---
        log("\n🌱 [Phase 1] Running Digital Gardener...")
        try: gardener.run_daily_maintenance(cfg)
        except Exception as ge: log(f"⚠️ Gardener failed: {ge}")
        
        # --- PHASE 2: CONTENT GENERATION ---
        all_categories = list(cfg['categories'].keys())
        random.shuffle(all_categories)
        log(f"🎲 Session Sequence: {all_categories}")
        
        published_successfully = False
        
        for current_cat in all_categories:
            log(f"\n📂 CATEGORY FOCUS: {current_cat}")
            
            # A. CLUSTER STRATEGY (Priority #1 - The Builder)
            try:
                cluster_topic, is_cluster = cluster_manager.get_strategic_topic(current_cat, cfg)
            except:
                cluster_topic, is_cluster = None, False

            if cluster_topic:
                # IMPORTANT: 'is_cluster_topic=True' activates the Knowledge Fallback
                if run_pipeline(current_cat, cfg, forced_keyword=cluster_topic, is_cluster_topic=is_cluster):
                    published_successfully = True
                    break # One article per run is standard
            
            # B. MANUAL FALLBACK (Priority #2)
            trending_topics = cfg['categories'][current_cat].get('trending_focus', '')
            if trending_topics and not is_cluster:
                log(f"   ⚠️ Cluster Strategy yielded no topic. Checking Manual List...")
                topics_list = [t.strip() for t in trending_topics.split(',') if t.strip()]
                random.shuffle(topics_list)
                
                for manual_topic in topics_list:
                    if run_pipeline(current_cat, cfg, forced_keyword=manual_topic, is_cluster_topic=False):
                        published_successfully = True
                        break
                if published_successfully: break

            # C. AI DAILY HUNT (Priority #3 - Absolute Last Resort)
            # Only if Cluster AND Manual failed
            if not published_successfully and not is_cluster:
                log(f"   ⚠️ Manual List exhausted. Attempting AI Daily Hunt...")
                if run_pipeline(current_cat, cfg, forced_keyword=None, is_cluster_topic=False):
                    published_successfully = True
                    break

        if published_successfully:
            log("\n✅ MISSION COMPLETE: Article published, indexed, and distributed.")
            history_manager.perform_maintenance_cleanup()
        else:
            log("\n❌ MISSION FAILED: No articles met the quality threshold today.")
            
    except Exception as e:
        log(f"❌ CRITICAL ERROR IN MAIN: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
