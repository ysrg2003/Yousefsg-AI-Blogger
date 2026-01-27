# FILE: main.py
# ROLE: Orchestrator
# FINAL VERSION: Implements the Dual-Hunt Strategy for maximum visual evidence acquisition.

import os
import json
import time
import random
import sys
import datetime
import urllib.parse
import traceback
import re
from google import genai 

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

def run_pipeline(category, config, forced_keyword=None):
    model_name = config['settings'].get('model_name', "gemini-2.5-flash")
    
    try:
        # 1. STRATEGY
        target_keyword = ""
        if forced_keyword:
            log(f"   👉 [Mode: Manual Fallback] Keyword: '{forced_keyword}'")
            target_keyword = forced_keyword
        else:
            log(f"   👉 [Mode: AI Strategist] Category: {category}")
            recent = history_manager.get_recent_titles_string(category=category)
            try:
                seo_p = PROMPT_ZERO_SEO.format(category=category, date=datetime.date.today(), history=recent)
                seo_plan = api_manager.generate_step_strict(
                    model_name, seo_p, "SEO Strategy", required_keys=["target_keyword"]
                )
                target_keyword = seo_plan.get('target_keyword')
                log(f"   🎯 AI Goal: {target_keyword}")
            except Exception as e:
                log(f"   ❌ SEO Strategy failed: {e}")
                return False

        if not target_keyword: return False

        # 2. CREATIVE DIRECTOR (Decides the visual approach)
        log("   🎬 [Creative Director] Deciding on visual strategy...")
        try:
            strategy_prompt = PROMPT_VISUAL_STRATEGY.format(target_keyword=target_keyword, category=category)
            strategy_decision = api_manager.generate_step_strict(
                model_name, strategy_prompt, "Visual Strategy", required_keys=["visual_strategy"]
            )
            visual_strategy = strategy_decision.get("visual_strategy", "generate_comparison_table")
            log(f"      👉 Directive Received: '{visual_strategy}'")
        except Exception as e:
            log(f"      ⚠️ Visual Strategy failed: {e}. Defaulting to fallback.")
            visual_strategy = "generate_comparison_table"

        # 3. SEMANTIC GUARD
        log("   🧠 Checking memory to avoid repetition...")
        history_str = history_manager.get_recent_titles_string(limit=200)
        if history_manager.check_semantic_duplication(target_keyword, history_str):
            log("   🚫 Duplication detected. Stopping this keyword.")
            return False

        # 4. OMNIVORE HUNT (TEXT + INCIDENTAL MEDIA from news articles)
        log("   🕵️‍♂️ Starting Omni-Hunt Mission (Text & Visuals from News)...")
        
        collected_sources = []
        media_from_news = []
        
        search_strategies = [
            f'"{target_keyword}"',
            f'{target_keyword} news update',
            f'{target_keyword} review OR analysis OR features',
        ]

        for strategy in search_strategies:
            if len(collected_sources) >= 3: break
            log(f"   🏹 Strategy: '{strategy}'")
            items = news_fetcher.get_real_news_rss(strategy, category)
            if not items: items = news_fetcher.get_gnews_api_sources(strategy, category)
            if not items: continue

            for item in items:
                if len(collected_sources) >= 3: break
                if any(b_word.lower() in item['title'].lower() for b_word in BORING_KEYWORDS): continue
                    
                # CRITICAL FIX: Now correctly unpacks 5 values
                f_url, f_title, text, f_image, media_in_source = scraper.resolve_and_scrape(item['link'])
                
                if not f_url or not text: continue

                f_domain = urllib.parse.urlparse(f_url).netloc.replace('www.', '')
                if any(s['domain'].replace('www.', '') == f_domain for s in collected_sources): continue
                
                log(f"         ✅ Source Captured! ({len(text)} chars) from {f_domain}")
                collected_sources.append({
                    "title": f_title or item['title'], "url": f_url, "text": text,
                    "date": item.get('date', 'Today'), "source_image": f_image or item.get('image'),
                    "domain": f_domain
                })
                
                if media_in_source:
                    media_from_news.extend(media_in_source)
            
            time.sleep(1)

        if len(collected_sources) < 2:
            log(f"   ❌ Failed to collect enough sources. Aborting.")
            return False

        # 5. DEDICATED VISUAL HUNT (SNIPER & REDDIT)
        official_media = []
        reddit_media = []
        reddit_context = ""

        # Execute hunt only if the director ordered it
        if visual_strategy.startswith("hunt_for_"):
            log("   📸 Directive is 'Hunt'. Launching dedicated visual hunt...")
            official_media = scraper.smart_media_hunt(target_keyword, category)
            reddit_context, reddit_media = reddit_manager.get_community_intel(target_keyword)
        else:
            log(f"   🎨 Directive is '{visual_strategy}'. Skipping dedicated media hunt.")
            reddit_context, _ = reddit_manager.get_community_intel(target_keyword)

        # --- MERGE ALL VISUALS ---
        all_visuals = media_from_news + official_media + reddit_media
        unique_visuals = list({v['url']:v for v in all_visuals}.values())
        unique_visuals.sort(key=lambda x: x.get('score', 0), reverse=True)
        
        log(f"   📸 Dual-Hunt Complete. Total Unique Visual Proofs: {len(unique_visuals)}")

        # --- FALLBACK LOGIC (CODE-ENFORCED) ---
        if not unique_visuals and visual_strategy.startswith("hunt_for_"):
            log("      ⚠️ Hunt failed. Overwriting directive to 'generate_comparison_table'.")
            visual_strategy = "generate_comparison_table"

        # 6. SYNTHESIS & GENERATION
        log("   ✍️ [Generation Started] Preparing research data...")
        combined_text = ""
        for i, src in enumerate(collected_sources):
            combined_text += f"\n--- SOURCE {i+1}: {src['domain']} ---\nURL: {src['url']}\nCONTENT:\n{src['text'][:9000]}\n"
        if reddit_context: combined_text += f"\n\n{reddit_context}\n"
        
        payload = f"METADATA: {json.dumps({'keyword': target_keyword, 'category': category})}\n"
        payload += f"VISUAL_STRATEGY_DIRECTIVE: \"{visual_strategy}\"\n"
        payload += f"VISUAL_EVIDENCE_LINKS: {json.dumps(unique_visuals)}\n"
        payload += f"\nDATA:\n{combined_text}"
        
        # ... (The rest of the file continues exactly as it was) ...
        
        json_b = api_manager.generate_step_strict(
            model_name, 
            PROMPT_B_TEMPLATE.format(json_input=payload, forbidden_phrases=str(FORBIDDEN_PHRASES)), 
            "Step B (Writer)",
            required_keys=["headline", "article_body"]
        )
        
        kg_links = history_manager.get_relevant_kg_for_linking(json_b.get('headline', target_keyword), category)
        input_c = {"draft_content": json_b, "sources_data": [{"title": s['title'], "url": s['url']} for s in collected_sources]}
        
        json_c = api_manager.generate_step_strict(
            model_name, 
            PROMPT_C_TEMPLATE.format(json_input=json.dumps(input_c), knowledge_graph=kg_links), 
            "Step C (SEO)",
            required_keys=["finalTitle", "finalContent"]
        )
        
        json_d = api_manager.generate_step_strict(
            model_name, 
            PROMPT_D_TEMPLATE.format(json_input=json.dumps(json_c)), 
            "Step D (Humanizing)",
            required_keys=["finalTitle", "finalContent"]
        )
        
        final = json_d
        title, content_html = final.get('finalTitle', 'Untitled'), final.get('finalContent', '<p>Error</p>')
        
        # --- MULTIMEDIA SECTION ---
        log("   🖼️ [Image Mission] Starting...")
        img_url = None
        c_imgs = [{'url': src['source_image']} for src in collected_sources if src.get('source_image')]
        
        if c_imgs:
            sel_img = image_processor.select_best_image_with_gemini(model_name, title, c_imgs)
            if sel_img:
                img_url = image_processor.process_source_image(sel_img, final.get('imageOverlayText'), title)
        
        if not img_url:
            img_url = image_processor.generate_and_upload_image(final.get('imageGenPrompt', title), final.get('imageOverlayText'))

        # --- VIDEO GENERATION ---
        log("   🎬 [Video Mission] Starting...")
        vid_main, vid_short, vid_html, fb_path = None, None, "", None
        summ = re.sub('<[^<]+?>','', content_html)[:2500]
        
        script_json = None
        try:
            v_script_data = api_manager.generate_step_strict(
                model_name, PROMPT_VIDEO_SCRIPT.format(title=title, text_summary=summ), "Video Script"
            )
            if 'video_script' in v_script_data and isinstance(v_script_data['video_script'], list):
                script_json = v_script_data['video_script']
        except Exception as e: log(f"      ⚠️ Script Gen Error: {e}")

        if script_json:
            try:
                v_meta = api_manager.generate_step_strict(model_name, PROMPT_YOUTUBE_METADATA.format(draft_title=title), "YT Meta", required_keys=["title", "description"])
                ts, out = int(time.time()), os.path.abspath("output")
                os.makedirs(out, exist_ok=True)
                
                rr = video_renderer.VideoRenderer(output_dir=out, width=1920, height=1080)
                pm = rr.render_video(script_json, title, f"main_{ts}.mp4")
                if pm:
                    v_desc = f"{v_meta.get('description','')}\n\n#{category.replace(' ','')}"
                    vid_main, _ = youtube_manager.upload_video_to_youtube(pm, title[:100], v_desc, v_meta.get('tags',[]))
                    if vid_main:
                        vid_html = f'<div class="video-container" style="position:relative;padding-bottom:56.25%;height:0;overflow:hidden;margin:30px 0;"><iframe style="position:absolute;top:0;left:0;width:100%;height:100%;" src="https://www.youtube.com/embed/{vid_main}" frameborder="0" allowfullscreen></iframe></div>'
                
                rs = video_renderer.VideoRenderer(output_dir=out, width=1080, height=1920)
                ps = rs.render_video(script_json, title, f"short_{ts}.mp4")
                if ps:
                    fb_path = ps
                    vid_short, _ = youtube_manager.upload_video_to_youtube(ps, title[:90]+" #Shorts", v_desc, v_meta.get('tags',[])+['shorts'])
            except Exception as ve: log(f"      ⚠️ Video Render/Upload Error: {ve}")

        # --- VALIDATION ---
        log("   🛡️ [Validation] Starting core surgery...")
        try:
            healer = content_validator_pro.AdvancedContentValidator()
            content_html = healer.run_professional_validation(content_html, combined_text, collected_sources)
        except Exception as he: log(f"      ⚠️ Validator skipped: {he}")

        # --- PUBLISHING ---
        log(f"   🚀 [Publishing] Final assembly...")
        fb_dat = api_manager.generate_step_strict(model_name, PROMPT_FACEBOOK_HOOK.format(title=title), "FB Hook", required_keys=["FB_Hook"])
        fb_cap = fb_dat.get('FB_Hook', title)

        author_box = """
        <div style="margin-top:50px; padding:30px; background:#f9f9f9; border-left: 6px solid #2ecc71; border-radius:12px; font-family:sans-serif; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">
            <div style="display:flex; align-items:flex-start; flex-wrap:wrap; gap:25px;">
                <img src="https://blogger.googleusercontent.com/img/a/AVvXsEiB6B0pK8PhY0j0JrrYCSG_QykTjsbxbbdePdNP_nRT_39FW4SGPPqTrAjendimEUZdipHUiYJfvHVjTBH7Eoz8vEjzzCTeRcDlIcDrxDnUhRJFJv4V7QHtileqO4wF-GH39vq_JAe4UrSxNkfjfi1fDS9_T4mPmwEC71VH9RJSEuSFrNb2ZRQedyA61iQ=s1017-rw" 
                     style="width:90px; height:90px; border-radius:50%; object-fit:cover; border:4px solid #fff; box-shadow:0 2px 8px rgba(0,0,0,0.1);" alt="Yousef S.">
                <div style="flex:1;">
                    <h4 style="margin:0; font-size:22px; color:#2c3e50; font-weight:800;">Yousef S. | Latest AI</h4>
                    <span style="font-size:12px; background:#e8f6ef; color:#2ecc71; padding:4px 10px; border-radius:6px; font-weight:bold;">TECH EDITOR</span>
                    <p style="margin:15px 0; color:#555; line-height:1.7;">Testing AI tools so you don't break your workflow. Brutally honest reviews, simple explainers, and zero fluff.</p>
                    <div style="display:flex; gap:15px; flex-wrap:wrap; margin-top:15px;">
                        <a href="https://www.facebook.com/share/1AkVHBNbV1/" target="_blank" title="Facebook"><img src="https://cdn-icons-png.flaticon.com/512/5968/5968764.png" width="24"></a>
                        <a href="https://x.com/latestaime" target="_blank" title="X (Twitter)"><img src="https://cdn-icons-png.flaticon.com/512/5969/5969020.png" width="24"></a>
                        <a href="https://www.instagram.com/latestai.me" target="_blank" title="Instagram"><img src="https://cdn-icons-png.flaticon.com/512/3955/3955024.png" width="24"></a>
                        <a href="https://m.youtube.com/@0latestai" target="_blank" title="YouTube"><img src="https://cdn-icons-png.flaticon.com/512/1384/1384060.png" width="24"></a>
                        <a href="https://pinterest.com/latestaime" target="_blank" title="Pinterest"><img src="https://cdn-icons-png.flaticon.com/512/145/145808.png" width="24"></a>
                        <a href="https://www.reddit.com/user/Yousefsg/" target="_blank" title="Reddit"><img src="https://cdn-icons-png.flaticon.com/512/3536/3536761.png" width="24"></a>
                        <a href="https://www.latestai.me" target="_blank" title="Website"><img src="https://cdn-icons-png.flaticon.com/512/1006/1006771.png" width="24"></a>
                    </div>
                </div>
            </div>
        </div>
        """
        
        final_c = content_html.replace('href=\\"', 'href="').replace('\\">', '">')
        final_c = re.sub(r'href=["\']\\?["\']?(http[^"\']+)\\?["\']?["\']', r'href="\1"', final_c)
        img_h = f'<div class="separator" style="clear:both;text-align:center;margin-bottom:30px;"><a href="{img_url}"><img src="{img_url}" width="1200" height="630" style="max-width:100%; border-radius:10px; box-shadow:0 5px 15px rgba(0,0,0,0.1);" /></a></div>' if img_url else ""
        
        full_body = ARTICLE_STYLE + img_h + vid_html + final_c + author_box
        
        if 'schemaMarkup' in final and final['schemaMarkup']: 
            full_body += f'\n<script type="application/ld+json">{json.dumps(final["schemaMarkup"])}</script>'

        p_url = publisher.publish_post(title, full_body, [category, "Tech News", "Reviews"])
        
        if p_url:
            history_manager.update_kg(title, p_url, category)
            log(f"   ✅ [SUCCESS] Published LIVE at: {p_url}")
            
            try:
                youtube_update_text = f"👇 Read the full, in-depth article here:\n{p_url}"
                if vid_main: youtube_manager.update_video_description(vid_main, youtube_update_text)
                if vid_short: youtube_manager.update_video_description(vid_short, youtube_update_text)
                social_manager.distribute_content(fb_cap, p_url, img_url)
                if fb_path: social_manager.post_reel_to_facebook(fb_path, fb_cap, p_url)
            except Exception as social_e: log(f"   ⚠️ Social media distribution/update failed: {social_e}")
            
            return True
        else:
            log("   ❌ Blogger API failed to publish.")
            return False

    except Exception as e:
        log(f"❌ PIPELINE CRASHED: {e}")
        traceback.print_exc()
        return False

def main():
    try:
        with open('config_advanced.json','r') as f: cfg = json.load(f)
        all_cats = list(cfg['categories'].keys())
        random.shuffle(all_cats)
        log(f"🎲 Session Categories: {all_cats}")
        
        success = False
        for cat in all_cats:
            log(f"\n📁 SWITCHING TO CATEGORY: {cat}")
            if run_pipeline(cat, cfg):
                success = True
                break
                
            trending = cfg['categories'][cat].get('trending_focus', '')
            if trending:
                log(f"   ⚠️ AI Strategy failed for {cat}. Trying Manual Topics...")
                manual = [t.strip() for t in trending.split(',') if t.strip()]
                random.shuffle(manual)
                for m in manual:
                    if run_pipeline(cat, cfg, forced_keyword=m):
                        success = True
                        break
                if success: break
        
        if success:
            log("\n✅ ARTICLE PUBLISHED SUCCESSFULLY.")
            history_manager.perform_maintenance_cleanup()
        else:
            log("\n❌ MISSION FAILED: No articles could be published today.")
            
    except Exception as e:
        log(f"❌ CRITICAL ERROR IN MAIN: {e}")

if __name__ == "__main__":
    main()
