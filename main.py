# FILE: main.py
# DESCRIPTION: The main orchestrator for the AI Blogger Automation project.
#              This script runs the entire pipeline from topic selection to publishing.

import os
import json
import time
import random
import sys
import datetime
import urllib.parse
import traceback
import re

# استيراد الوحدات الجديدة المنطقية
from config import log, FORBIDDEN_PHRASES, ARTICLE_STYLE
import api_manager
import news_fetcher
import scraper
import image_processor
import history_manager
import publisher

# استيراد الوحدات الموجودة مسبقاً (الطرفية)
import content_validator_pro
import reddit_manager
import social_manager
import video_renderer
import youtube_manager
from prompts import *

def run_pipeline(category, config, forced_keyword=None):
    model_name = config['settings'].get('model_name', "gemini-3-flash-preview")
    
    # --------------------------------------------------------------------------
    # 1. STRATEGY: Define the target keyword
    # --------------------------------------------------------------------------
    target_keyword = ""
    is_manual_mode = False

    if forced_keyword:
        log(f"\n🔄 RETRY MODE: Trying fallback keyword in '{category}': '{forced_keyword}'")
        target_keyword = forced_keyword
        is_manual_mode = True
    else:
        log(f"\n🚀 INIT PIPELINE: {category} (AI Strategist Mode)")
        recent_titles = history_manager.get_recent_titles_string(category=category, limit=100)
        try:
            seo_prompt = PROMPT_ZERO_SEO.format(category=category, date=datetime.date.today(), history=recent_titles)
            seo_plan = api_manager.generate_step_strict(model_name, seo_prompt, "Step 0 (SEO Strategy)", required_keys=["target_keyword"])
            target_keyword = seo_plan.get('target_keyword')
            log(f"   🎯 Strategy Defined: Targeting '{target_keyword}'")
        except Exception as e:
            log(f"   ⚠️ AI Strategy failed: {e}. Switching to manual list.")
            return False

    if not target_keyword:
        log("   ❌ No target keyword defined. Aborting.")
        return False
        
    # --------------------------------------------------------------------------
    # 2. SEMANTIC GUARD: Prevent topic cannibalization
    # --------------------------------------------------------------------------
    days_lookback = 7 if is_manual_mode else 60
    history_string = history_manager.get_recent_titles_string(limit=days_lookback * 5)
    if history_manager.check_semantic_duplication(target_keyword, history_string):
        log(f"   🚫 ABORTING: Topic '{target_keyword}' covered in last {days_lookback} days.")
        return False

    # --------------------------------------------------------------------------
    # 3. SMART MULTI-SOURCE HUNTING: Gather intelligence
    # --------------------------------------------------------------------------
    collected_sources = []
    main_headline, main_link = "", ""
    words = target_keyword.split()
    significant_word = max(words, key=len) if words else category
    
    search_strategies = [
        f'"{target_keyword}"', 
        f'{target_keyword} (breakthrough OR revealed OR "hands-on" OR review)',
        f'{significant_word} vs (Sora OR ChatGPT OR Gemini OR Claude)',
        f'{category} update 2026'
    ]

    for attempt_idx, query in enumerate(search_strategies):
        if len(collected_sources) >= 3: break
        log(f"   🕵️‍♂️ Hunting (Level {attempt_idx + 1}): '{query}'")
        
        items = news_fetcher.get_gnews_api_sources(query, category)
        if not items: items = news_fetcher.get_real_news_rss(query)

        for item in items:
            if len(collected_sources) >= 3: break
            if 'link' not in item or not item['link']: continue
            if any('url' in s and s['url'] == item['link'] for s in collected_sources): continue
            
            final_url, final_title, text = scraper.resolve_and_scrape(item['link'])
            if text:
                log(f"         ✅ Source Captured! ({len(text)} chars)")
                collected_sources.append({
                    "title": final_title or item['title'], 
                    "url": final_url, 
                    "text": text,
                    "date": item.get('date', 'Today'), 
                    "source_image": item.get('image'),
                    "domain": urllib.parse.urlparse(final_url).netloc
                })
                if not main_headline: main_headline, main_link = item['title'], item['link']
            time.sleep(1.5)

    if len(collected_sources) < 2:
        log(f"   ❌ Insufficient source depth ({len(collected_sources)}). Aborting.")
        return False
        
    # --------------------------------------------------------------------------
    # 4. COMMUNITY INTEL: Gather Reddit opinions
    # --------------------------------------------------------------------------
    reddit_context = reddit_manager.get_community_intel(target_keyword)
    
    # --------------------------------------------------------------------------
    # 5. EXECUTION: Generate, Validate, and Publish
    # --------------------------------------------------------------------------
    try:
        log(f"\n✍️ Synthesizing Content...")
        combined_text = ""
        for i, src in enumerate(collected_sources):
            combined_text += f"\n--- SOURCE {i+1}: {src['domain']} ---\nURL: {src['url']}\nTitle: {src['title']}\nCONTENT:\n{src['text'][:9000]}\n"
        if reddit_context: combined_text += f"\n\n{reddit_context}\n"
        
        json_ctx = {"keyword": target_keyword, "citation_policy": "MANDATORY: Hyperlink every quote/claim to its specific URL."}
        payload = f"METADATA: {json.dumps(json_ctx)}\n\n*** RESEARCH DATA ***\n{combined_text}"
        
        # --- Generation Chain ---
        json_b = api_manager.generate_step_strict(model_name, PROMPT_B_TEMPLATE.format(json_input=payload, forbidden_phrases=str(FORBIDDEN_PHRASES)), "Step B (Writer)")
        
        kg_links = history_manager.get_relevant_kg_for_linking(json_b.get('headline', target_keyword), category)
        input_c = {"draft_content": json_b, "sources_data": [{"title": s['title'], "url": s['url']} for s in collected_sources]}
        json_c = api_manager.generate_step_strict(model_name, PROMPT_C_TEMPLATE.format(json_input=json.dumps(input_c), knowledge_graph=kg_links), "Step C (SEO)")
        json_d = api_manager.generate_step_strict(model_name, PROMPT_D_TEMPLATE.format(json_input=json.dumps(json_c)), "Step D (Humanizer)")
        final = api_manager.generate_step_strict(model_name, PROMPT_E_TEMPLATE.format(json_input=json.dumps(json_d)), "Step E (Final Polish)")
        
        title, content_html = final['finalTitle'], final['finalContent']
        seo_data = final.get('seo', {})
        
        # --- Multimedia Asset Generation ---
        log("   🧠 Generating Multimedia Assets...")
        yt_meta = api_manager.generate_step_strict(model_name, PROMPT_YOUTUBE_METADATA.format(draft_title=title), "YT Meta", required_keys=["title", "description", "tags"])
        fb_dat = api_manager.generate_step_strict(model_name, PROMPT_FACEBOOK_HOOK.format(title=title), "FB Hook", required_keys=["FB_Hook"])
        fb_cap = fb_dat.get('FB_Hook', title)
        
        log("   🖼️ Image Strategy...")
        candidate_images = [{'url': src['source_image']} for src in collected_sources if src.get('source_image')]
        
        selected_source_image = None
        if candidate_images: selected_source_image = image_processor.select_best_image_with_gemini(model_name, title, candidate_images)
        
        img_url = None
        if selected_source_image:
            img_url = image_processor.process_source_image(selected_source_image, final.get('imageOverlayText'), title)
        if not img_url:
            img_url = image_processor.generate_and_upload_image(final.get('imageGenPrompt', title), final.get('imageOverlayText'))

        # --- Video Generation ---
        summ_clean = re.sub('<[^<]+?>','', content_html)[:2500]
        script_json = None
        try:
            raw_result = api_manager.generate_step_strict(model_name, PROMPT_VIDEO_SCRIPT.format(title=title, text_summary=summ_clean), "Video Script")
            script_json = raw_result.get('video_script') or raw_result.get('script')
        except Exception as e:
            log(f"   ⚠️ Video script generation failed: {e}")

        vid_main, vid_short, vid_html, fb_path = None, None, "", None
        if script_json and len(script_json) > 0:
            ts = int(time.time())
            out_dir = os.path.abspath("output")
            os.makedirs(out_dir, exist_ok=True)
            
            try:
                rr = video_renderer.VideoRenderer(output_dir=out_dir, width=1920, height=1080)
                main_p = os.path.join(out_dir, f"main_{ts}.mp4")
                pm = rr.render_video(script_json, title, main_p)
                if pm and os.path.exists(pm):
                    desc = f"{yt_meta.get('description','')}\n\n🚀 Full Story: {main_link}\n\n#{category.replace(' ','')}"
                    vid_main, _ = youtube_manager.upload_video_to_youtube(pm, yt_meta.get('title',title)[:100], desc, yt_meta.get('tags',[]))
                    if vid_main: 
                        vid_html = f'''
                        <div class="video-container" style="position:relative;padding-bottom:56.25%;height:0;overflow:hidden;margin:30px 0;border-radius:10px;box-shadow:0 4px 12px rgba(0,0,0,0.1);">
                            <iframe 
                                style="position:absolute;top:0;left:0;width:100%;height:100%;" 
                                src="https://www.youtube.com/embed/{vid_main}" 
                                frameborder="0" 
                                allowfullscreen 
                                loading="lazy"
                                width="1280" 
                                height="720"
                                title="{title}">
                            </iframe>
                        </div>
                        '''
            except Exception as e: log(f"      ⚠️ Main Video Error: {e}")

            try:
                rs = video_renderer.VideoRenderer(output_dir=out_dir, width=1080, height=1920)
                short_p = os.path.join(out_dir, f"short_{ts}.mp4")
                ps = rs.render_video(script_json, title, short_p)
                if ps and os.path.exists(ps):
                    fb_path = ps
                    vid_short, _ = youtube_manager.upload_video_to_youtube(ps, f"{yt_meta.get('title',title)[:90]} #Shorts", desc, yt_meta.get('tags',[])+['shorts'])
            except Exception as e: log(f"      ⚠️ Short Video Error: {e}")
        
        # --- Self-Healing Validation ---
        log("   🛡️ Initiating Self-Healing Validation...")
        try:
            val_client = api_manager.genai.Client(api_key=api_manager.key_manager.get_current_key())
            healer = content_validator_pro.AdvancedContentValidator(val_client)
            full_text = "\n".join([s['text'] for s in collected_sources])
            content_html = healer.run_professional_validation(content_html, full_text, collected_sources)
        except Exception as e: log(f"   ⚠️ Validation Error (Non-Fatal): {e}")

        # --- Final Assembly & Publishing ---
        log("   🚀 Assembling final post for publishing...")
        author_box = """
        <div style="margin-top:50px; padding:30px; background:#f9f9f9; border-left: 6px solid #2ecc71; border-radius:12px; font-family:sans-serif; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">
            <div style="display:flex; align-items:flex-start; flex-wrap:wrap; gap:25px;">
                <img src="https://blogger.googleusercontent.com/img/a/AVvXsEiB6B0pK8PhY0j0JrrYCSG_QykTjsbxbbdePdNP_nRT_39FW4SGPPqTrAjendimEUZdipHUiYJfvHVjTBH7Eoz8vEjzzCTeRcDlIcDrxDnUhRJFJv4V7QHtileqO4wF-GH39vq_JAe4UrSxNkfjfi1fDS9_T4mPmwEC71VH9RJSEuSFrNb2ZRQedyA61iQ=s1017-rw" 
                     style="width:90px; height:90px; border-radius:50%; object-fit:cover; border:4px solid #fff; box-shadow:0 2px 8px rgba(0,0,0,0.1);">
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
        
        final_content = content_html.replace('href=\\"', 'href="').replace('\\">', '">')
        final_content = re.sub(r'href=["\']\\?["\']?(http[^"\']+)\\?["\']?["\']', r'href="\1"', final_content)
        final_content_with_author = final_content + author_box
        
        img_html = ""
        if img_url: 
            alt_text = seo_data.get("imageAltText", title)
            img_html = f'''<div class="separator" style="clear:both;text-align:center;margin-bottom:30px;"><a href="{img_url}" style="margin-left:1em; margin-right:1em;"><img border="0" src="{img_url}" alt="{alt_text}" width="1200" height="630" style="max-width:100%; height:auto; border-radius:10px; box-shadow:0 5px 15px rgba(0,0,0,0.1);" /></a></div>'''

        full_body = ARTICLE_STYLE + img_html + vid_html + final_content_with_author
        if 'schemaMarkup' in final and final['schemaMarkup']:
            try: 
                full_body += f'\n<script type="application/ld+json">{json.dumps(final["schemaMarkup"])}</script>'
            except: pass
        
        published_url = publisher.publish_post(title, full_body, [category, "Tech News", "Explainers"])
        
        if published_url:
            history_manager.update_kg(title, published_url, category)
            new_desc = f"{yt_meta.get('description','')}\n\n👇 READ THE FULL ARTICLE:\n{published_url}\n\n#AI"
            if vid_main: youtube_manager.update_video_description(vid_main, new_desc)
            if vid_short: youtube_manager.update_video_description(vid_short, new_desc)
            
            try:
                log("   📢 Distributing to Social Media...")
                if fb_path and os.path.exists(fb_path): 
                    social_manager.post_reel_to_facebook(fb_path, f"{fb_cap}\n\n{published_url}")
                elif img_url:
                    social_manager.distribute_content(f"{fb_cap}\n\n{published_url}", published_url, img_url)
            except Exception as e: log(f"   ⚠️ Social Distribution Error: {e}")
            
            return True

    except Exception as e:
        log(f"❌ PIPELINE CRASHED: {e}")
        traceback.print_exc()
        return False
    return False

def main():
    try:
        with open('config_advanced.json','r') as f: cfg = json.load(f)
    except FileNotFoundError:
        log("❌ CRITICAL: config_advanced.json not found. Aborting.")
        return
    
    all_categories = list(cfg['categories'].keys())
    random.shuffle(all_categories)
    log(f"🎲 Session Categories: {all_categories}")
    
    success = False
    for category in all_categories:
        log(f"\n📁 SWITCHING TO CATEGORY: {category}")
        if run_pipeline(category, cfg):
            success = True
            break 
        
        log(f"   ⚠️ AI Strategy failed for {category}. Switching to Manual List...")
        trending_text = cfg['categories'][category].get('trending_focus', '')
        if trending_text:
            manual_topics = [t.strip() for t in trending_text.split(',') if t.strip()]
            random.shuffle(manual_topics)
            for topic in manual_topics:
                log(f"   👉 Trying Manual Topic: '{topic}'")
                if run_pipeline(category, cfg, forced_keyword=topic):
                    success = True
                    break 
            if success: break 
            
    if success:
        log("\n✅ MISSION ACCOMPLISHED.")
        history_manager.perform_maintenance_cleanup()
    else:
        log("\n❌ MISSION FAILED. Exhausted all categories and keywords.")

if __name__ == "__main__":
    main()
