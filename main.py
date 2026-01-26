# FILE: main.py
import os
import json
import time
import random
import sys
import datetime
import urllib.parse
import traceback
import re

from config import log, FORBIDDEN_PHRASES, ARTICLE_STYLE
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
    model_name = config['settings'].get('model_name', "gemini-3-flash-preview")
    
    # 1. STRATEGY
    target_keyword = ""
    is_manual_mode = False
    if forced_keyword:
        log(f"\n🔄 RETRY MODE: Topic: '{forced_keyword}'")
        target_keyword, is_manual_mode = forced_keyword, True
    else:
        log(f"\n🚀 INIT PIPELINE: {category}")
        recent = history_manager.get_recent_titles_string(category=category)
        try:
            seo_p = PROMPT_ZERO_SEO.format(category=category, date=datetime.date.today(), history=recent)
            seo_plan = api_manager.generate_step_strict(model_name, seo_p, "SEO Strategy", required_keys=["target_keyword"])
            target_keyword = seo_plan.get('target_keyword')
        except: return False

    # 2. SEMANTIC GUARD
    days = 7 if is_manual_mode else 60
    history_str = history_manager.get_recent_titles_string(limit=days*5)
    if history_manager.check_semantic_duplication(target_keyword, history_str): return False

    # 3. SOURCE HUNTING
    collected_sources = []
    significant_word = max(target_keyword.split(), key=len)
    search_strategies = [
        f'"{target_keyword}"', 
        f'{target_keyword} (breakthrough OR revealed OR review)',
        f'{significant_word} vs (Sora OR ChatGPT OR Gemini OR Claude)',
        f'{category} update 2026'
    ]
    for attempt_idx, query in enumerate(search_strategies):
        if len(collected_sources) >= 3: break
        items = news_fetcher.get_gnews_api_sources(query, category)
        if not items: items = news_fetcher.get_real_news_rss(query)
        for item in items:
            if len(collected_sources) >= 3: break
            if any(s['url'] == item['link'] for s in collected_sources): continue
            f_url, f_title, text = scraper.resolve_and_scrape(item['link'])
            if text:
                collected_sources.append({
                    "title": f_title or item['title'], "url": f_url, "text": text,
                    "date": item.get('date', 'Today'), "source_image": item.get('image'),
                    "domain": urllib.parse.urlparse(f_url).netloc
                })
        time.sleep(1)
    if len(collected_sources) < 2: return False

    # 4. REDDIT
    reddit_context = reddit_manager.get_community_intel(target_keyword)

    # 5. GENERATION
    try:
        combined_text = ""
        for i, src in enumerate(collected_sources):
            combined_text += f"\n--- SOURCE {i+1}: {src['domain']} ---\nURL: {src['url']}\nCONTENT:\n{src['text'][:9000]}\n"
        if reddit_context: combined_text += f"\n\n{reddit_context}\n"
        
        payload = f"METADATA: {json.dumps({'keyword': target_keyword})}\n\nDATA:\n{combined_text}"
        json_b = api_manager.generate_step_strict(model_name, PROMPT_B_TEMPLATE.format(json_input=payload, forbidden_phrases=str(FORBIDDEN_PHRASES)), "Step B")
        kg_links = history_manager.get_relevant_kg_for_linking(json_b.get('headline'), category)
        input_c = {"draft_content": json_b, "sources_data": [{"title": s['title'], "url": s['url']} for s in collected_sources]}
        json_c = api_manager.generate_step_strict(model_name, PROMPT_C_TEMPLATE.format(json_input=json.dumps(input_c), knowledge_graph=kg_links), "Step C")
        json_d = api_manager.generate_step_strict(model_name, PROMPT_D_TEMPLATE.format(json_input=json.dumps(json_c)), "Step D")
        final = api_manager.generate_step_strict(model_name, PROMPT_E_TEMPLATE.format(json_input=json.dumps(json_d)), "Step E")
        
        title, content_html = final['finalTitle'], final['finalContent']
        seo_data = final.get('seo', {})

        # MULTIMEDIA
        yt_meta = api_manager.generate_step_strict(model_name, PROMPT_YOUTUBE_METADATA.format(draft_title=title), "YT Meta")
        fb_dat = api_manager.generate_step_strict(model_name, PROMPT_FACEBOOK_HOOK.format(title=title), "FB Hook")
        fb_cap = fb_dat.get('FB_Hook', title)
        
        c_imgs = [{'url': src['source_image']} for src in collected_sources if src.get('source_image')]
        sel_img = image_processor.select_best_image_with_gemini(model_name, title, c_imgs) if c_imgs else None
        img_url = image_processor.process_source_image(sel_img, final.get('imageOverlayText'), title) if sel_img else None
        if not img_url: img_url = image_processor.generate_and_upload_image(final.get('imageGenPrompt', title), final.get('imageOverlayText'))

        # VIDEO
        vid_main, vid_short, vid_html, fb_path = None, None, "", None
        summ = re.sub('<[^<]+?>','', content_html)[:2500]
        try:
            v_script = api_manager.generate_step_strict(model_name, PROMPT_VIDEO_SCRIPT.format(title=title, text_summary=summ), "Video Script")
            script_json = v_script.get('video_script') or v_script.get('script')
            if script_json:
                ts, out = int(time.time()), os.path.abspath("output")
                os.makedirs(out, exist_ok=True)
                # Main
                rr = video_renderer.VideoRenderer(output_dir=out, width=1920, height=1080)
                pm = rr.render_video(script_json, title, f"main_{ts}.mp4")
                if pm:
                    v_desc = f"{yt_meta.get('description','')}\n\n#{category.replace(' ','')}"
                    vid_main, _ = youtube_manager.upload_video_to_youtube(pm, title[:100], v_desc, yt_meta.get('tags',[]))
                    if vid_main: vid_html = f'<div class="video-container" style="position:relative;padding-bottom:56.25%;height:0;overflow:hidden;margin:30px 0;"><iframe style="position:absolute;top:0;left:0;width:100%;height:100%;" src="https://www.youtube.com/embed/{vid_main}" frameborder="0" allowfullscreen></iframe></div>'
                # Short
                rs = video_renderer.VideoRenderer(output_dir=out, width=1080, height=1920)
                ps = rs.render_video(script_json, title, f"short_{ts}.mp4")
                if ps:
                    fb_path = ps
                    vid_short, _ = youtube_manager.upload_video_to_youtube(ps, title[:90]+" #Shorts", v_desc, yt_meta.get('tags',[])+['shorts'])
        except: pass

        # VALIDATION
        try:
            val_client = genai.Client(api_key=api_manager.key_manager.get_current_key())
            healer = content_validator_pro.AdvancedContentValidator(val_client)
            content_html = healer.run_professional_validation(content_html, combined_text, collected_sources)
        except: pass

        # PUBLISHauthor_box = """
        <div style="margin-top:50px; padding:30px; background:#f9f9f9; border-left: 6px solid #2ecc71; border-radius:12px; font-family:sans-serif; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">
            <div style="display:flex; align-items:flex-start; flex-wrap:wrap; gap:25px;">
                <img src="https://blogger.googleusercontent.com/img/a/AVvXsEiB6B0pK8PhY0j0JrrYCSG_QykTjsbxbbdePdNP_nRT_39FW4SGPPqTrAjendimEUZdipHUiYJfvHVjTBH7Eoz8vEjzzCTeRcDlIcDrxDnUhRJFJv4V7QHtileqO4wF-GH39vq_JAe4UrSxNkfjfi1fDS9_T4mPmwEC71VH9RJSEuSFrNb2ZRQedyA61iQ=s1017-rw" 
                     style="width:90px; height:90px; border-radius:50%; object-fit:cover; border:4px solid #fff; box-shadow:0 2px 8px rgba(0,0,0,0.1);">
                <div style="flex:1;">
                    <h4 style="margin:0; font-size:22px; color:#2c3e50; font-weight:800;">Yousef S. | Latest AI</h4>
                    <span style="font-size:12px; background:#e8f6ef; color:#2ecc71; padding:4px 10px; border-radius:6px; font-weight:bold;">TECH EDITOR</span>
                    <p style="margin:15px 0; color:#555; line-height:1.7;">Testing AI tools so you don't break your workflow. Brutally honest reviews, simple explainers, and zero fluff.</p>
             <div style="display:flex; gap:15px;"><a href="https://www.facebook.com/share/1AkVHBNbV1/"><img src="https://cdn-icons-png.flaticon.com/512/5968/5968764.png" width="24"></a><a href="https://x.com/latestaime"><img src="https://cdn-icons-png.flaticon.com/512/5969/5969020.png" width="24"></a><a href="https://www.instagram.com/latestai.me"><img src="https://cdn-icons-png.flaticon.com/512/3955/3955024.png" width="24"></a><a href="https://m.youtube.com/@0latestai"><img src="https://cdn-icons-png.flaticon.com/512/1384/1384060.png" width="24"></a><a href="https://pinterest.com/latestaime"><img src="https://cdn-icons-png.flaticon.com/512/145/145808.png" width="24"></a><a href="https://www.latestai.me"><img src="https://cdn-icons-png.flaticon.com/512/1006/1006771.png" width="24"></a></div></div></div></div>"""
        
        final_c = content_html.replace('href=\\"', 'href="').replace('\\">', '">')
        final_c = re.sub(r'href=["\']\\?["\']?(http[^"\']+)\\?["\']?["\']', r'href="\1"', final_c)
        img_h = f'<div class="separator" style="clear:both;text-align:center;margin-bottom:30px;"><a href="{img_url}"><img src="{img_url}" width="1200" height="630" style="max-width:100%; border-radius:10px;" /></a></div>' if img_url else ""
        
        full_body = img_h + vid_html + final_c + author_box
        if 'schemaMarkup' in final: full_body += f'\n<script type="application/ld+json">{json.dumps(final["schemaMarkup"])}</script>'

        p_url = publisher.publish_post(title, full_body, [category, "Tech News"])
        if p_url:
            history_manager.update_kg(title, p_url, category)
            try: social_manager.distribute_content(f"{fb_cap}\n\n{p_url}", p_url, img_url)
            except: pass
            if fb_path: social_manager.post_reel_to_facebook(fb_path, fb_cap)
            return True
    except Exception as e:
        log(f"❌ PIPELINE CRASHED: {e}")
        return False
    return False

def main():
    try:
        with open('config_advanced.json','r') as f: cfg = json.load(f)
        all_cats = list(cfg['categories'].keys())
        random.shuffle(all_cats)
        success = False
        for cat in all_cats:
            if run_pipeline(cat, cfg): success = True; break
            trending = cfg['categories'][cat].get('trending_focus', '')
            if trending:
                manual = [t.strip() for t in trending.split(',') if t.strip()]
                random.shuffle(manual)
                for m in manual:
                    if run_pipeline(cat, cfg, forced_keyword=m): success = True; break
                if success: break
        if success: history_manager.perform_maintenance_cleanup()
    except Exception as e: log(f"❌ Main Error: {e}")

if __name__ == "__main__":
    main()
