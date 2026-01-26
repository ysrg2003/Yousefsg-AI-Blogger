# FILE: main.py
# DESCRIPTION: Orchestrator. RESTORED: Video Retry Loop, Strict Keyword Filtering.

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

# Local Modules
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

    # 2. SEMANTIC GUARD
    log("   🧠 Checking memory to avoid repetition...")
    history_str = history_manager.get_recent_titles_string(limit=200)
    if history_manager.check_semantic_duplication(target_keyword, history_str):
        log("   🚫 Duplication detected. Stopping this keyword.")
        return False

    # 3. SMART MULTI-SOURCE HUNTING
    log("   🕵️‍♂️ Starting Source Hunting Mission...")
    
    # RESTORED: Significant Keyword Logic
    required_terms = target_keyword.lower().split()
    significant_keyword = max(required_terms, key=len) if required_terms else ""
    
    rss_query = f"{target_keyword} when:2d"
    items = news_fetcher.get_real_news_rss(rss_query, category) # Uses the robust fetcher
    
    if not items:
        # Try GNews as backup
        items = news_fetcher.get_gnews_api_sources(target_keyword, category)

    collected_sources = []
    
    for item in items:
        if len(collected_sources) >= 3: break
        
        # RESTORED: Boring Filter
        if any(b_word.lower() in item['title'].lower() for b_word in BORING_KEYWORDS):
            log(f"         ⛔ Skipped Boring Corporate Topic: {item['title']}")
            continue
            
        # RESTORED: Strict Title Relevance
        if significant_keyword and len(significant_keyword) > 3:
            if significant_keyword not in item['title'].lower():
                log(f"         ⚠️ Skipped Irrelevant Title: '{item['title']}'")
                continue

        if any(s['url'] == item['link'] for s in collected_sources): continue
        
        f_url, f_title, text = scraper.resolve_and_scrape(item['link'])
        
        if text:
            # RESTORED: Strict Body Relevance Check
            if significant_keyword and significant_keyword not in text.lower():
                log(f"         ⚠️ Skipped: Text missing keyword '{significant_keyword}'")
                continue

            log(f"         ✅ Source Captured! ({len(text)} chars)")
            collected_sources.append({
                "title": f_title or item['title'], 
                "url": f_url, 
                "text": text,
                "date": item.get('date', 'Today'), 
                "source_image": item.get('image') if 'image' in item else None,
                "domain": urllib.parse.urlparse(f_url).netloc
            })
    
    if len(collected_sources) < 1: # Strictness: Need at least 1 good source
        log(f"   ❌ Insufficient source depth. Aborting.")
        return False

    # 4. REDDIT INTEL
    log("   📱 Harvesting Reddit opinions...")
    reddit_context = reddit_manager.get_community_intel(target_keyword)

    # 5. SYNTHESIS & GENERATION
    try:
        log("   ✍️ [Generation Started] Preparing research data...")
        combined_text = ""
        for i, src in enumerate(collected_sources):
            combined_text += f"\n--- SOURCE {i+1}: {src['domain']} ---\nURL: {src['url']}\nCONTENT:\n{src['text'][:9000]}\n"
        if reddit_context: combined_text += f"\n\n{reddit_context}\n"
        
        payload = f"METADATA: {json.dumps({'keyword': target_keyword})}\n\nDATA:\n{combined_text}"
        
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
        
        final = api_manager.generate_step_strict(
            model_name, 
            PROMPT_E_TEMPLATE.format(json_input=json.dumps(json_d)), 
            "Step E (Final Polish)",
            required_keys=["finalTitle", "finalContent"]
        )
        
        title, content_html = final['finalTitle'], final['finalContent']
        
        # --- MULTIMEDIA SECTION ---
        log("   🖼️ [Image Mission] Starting...")
        img_url = None
        c_imgs = [{'url': src['source_image']} for src in collected_sources if src.get('source_image')]
        
        if c_imgs:
            sel_img = image_processor.select_best_image_with_gemini(model_name, title, c_imgs)
            if sel_img:
                img_url = image_processor.process_source_image(sel_img, final.get('imageOverlayText'), title)
        
        if not img_url:
            log("      ⚠️ NO SOURCE IMAGE: Activating AI Generation Backup...")
            img_url = image_processor.generate_and_upload_image(final.get('imageGenPrompt', title), final.get('imageOverlayText'))

        # --- VIDEO GENERATION (RESTORED RETRY LOOP) ---
        log("   🎬 [Video Mission] Starting...")
        vid_main, vid_short, vid_html, fb_path = None, None, "", None
        summ = re.sub('<[^<]+?>','', content_html)[:2500]
        
        script_json = None
        # RESTORED: The 3-Attempt Loop
        for attempt in range(1, 4):
            log(f"      🎬 Generating Script (Attempt {attempt}/3)...")
            try:
                v_script_data = api_manager.generate_step_strict(
                    model_name, 
                    PROMPT_VIDEO_SCRIPT.format(title=title, text_summary=summ), 
                    f"Video Script (Att {attempt})"
                )
                # Flexible parsing logic from original code
                if isinstance(v_script_data, dict):
                    if 'video_script' in v_script_data and isinstance(v_script_data['video_script'], list):
                        script_json = v_script_data['video_script']
                        break
                    for key in ['script', 'dialogue', 'scenes']:
                        if key in v_script_data and isinstance(v_script_data[key], list):
                            script_json = v_script_data[key]
                            break
            except Exception as e:
                log(f"      ⚠️ Script Gen Error: {e}")

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
            except Exception as ve:
                log(f"      ⚠️ Video Render/Upload Error: {ve}")
        else:
            log("      ❌ Failed to generate video script after 3 attempts.")

        # --- VALIDATION ---
        log("   🛡️ [Validation] Starting core surgery...")
        try:
            val_client = genai.Client(api_key=api_manager.key_manager.get_current_key())
            healer = content_validator_pro.AdvancedContentValidator(val_client)
            content_html = healer.run_professional_validation(content_html, combined_text, collected_sources)
        except Exception as he:
            log(f"      ⚠️ Validator skipped: {he}")

        # --- PUBLISHING ---
        log(f"   🚀 [Publishing] Final assembly...")
        fb_dat = api_manager.generate_step_strict(model_name, PROMPT_FACEBOOK_HOOK.format(title=title), "FB Hook", required_keys=["FB_Hook"])
        fb_cap = fb_dat.get('FB_Hook', title)

        author_box = """
        <div style="margin-top:50px; padding:30px; background:#f9f9f9; border-left: 6px solid #2ecc71; border-radius:12px; font-family:sans-serif; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">
            <div style="display:flex; align-items:flex-start; flex-wrap:wrap; gap:25px;">
                <img src="https://blogger.googleusercontent.com/img/a/AVvXsEiB6B0pK8PhY0j0JrrYCSG_QykTjsbxbbdePdNP_nRT_39FW4SGPPqTrAjendimEUZdipHUiYJfvHVjTBH7Eoz8vEjzzCTeRcDlIcDrxDnUhRJFJv4V7QHtileqO4wF-GH39vq_JAe4UrSxNkfjfi1fDS9_T4mPmwEC71VH9RJSEuSFrNb2ZRQedyA61iQ=s1017-rw" 
                     style="width:90px; height:90px; border-radius:50%; object-fit:cover; border:4px solid #fff; box-shadow:0 2px 8px rgba(0,0,0,0.1);">
                <div style="flex:1;">
                    <h4 style="margin:0; font-size:22px; color:#2c3e50; font-weight:800;">Yousef S. | Latest AI</h4>
                    <span style="font-size:12px; background:#e8f6ef; color:#2ecc71; padding:4px 10px; border-radius:6px; font-weight:bold;">TECH EDITOR</span>
                    <p style="margin:15px 0; color:#555; line-height:1.7;">Testing AI tools so you don't break your workflow. Brutally honest reviews, simple explainers, and zero fluff.</p>
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
                social_manager.distribute_content(f"{fb_cap}\n\n{p_url}", p_url, img_url)
                if fb_path: social_manager.post_reel_to_facebook(fb_path, fb_cap)
            except: pass
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
