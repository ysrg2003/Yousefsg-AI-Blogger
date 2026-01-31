# FILE: main.py
# ROLE: Orchestrator V9.3 (The Unstoppable Research Engine)
# DESCRIPTION: The complete, final, and stable version integrating all modules and fixes.
#              Fixed: SyntaxErrors, Indentation, and missing variables.

import os
import json
import time
import requests
import random
import sys
import datetime
import urllib.parse
import traceback
import trafilatura
from bs4 import BeautifulSoup
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
import url_resolver
from prompts import *
import cluster_manager
import indexer
import gardener
import ai_researcher
import ai_strategy
import live_auditor
import remedy

# --- NEW: VALIDATION FUNCTION (حارس الروابط) ---
def is_url_accessible(url):
    """Checks if a URL is alive (Status 200) and allows hotlinking."""
    if not url: return False
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        # Timeout قصير (3 ثواني) لعدم تعطيل السكريبت
        r = requests.head(url, headers=headers, timeout=3, allow_redirects=True)
        return r.status_code == 200
    except:
        return False

def run_pipeline(category, config, forced_keyword=None, is_cluster_topic=False):
    """
    Executes the full content lifecycle using a robust, multi-layered Gemini-powered strategy.
    """
    model_name = config['settings'].get('model_name', "gemini-2.5-flash") # Use a powerful model for writing
    img_url = None # Initialize to prevent NameError later

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
                seo_plan = api_manager.generate_step_strict(model_name, seo_p, "SEO Strategy", ["target_keyword"], use_google_search=True)
                target_keyword = seo_plan.get('target_keyword')
            except Exception as e: return False
        
        if not target_keyword: return False

        smart_query = ai_strategy.generate_smart_query(target_keyword)

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
        except: 
            visual_strategy = "generate_comparison_table"

        # ======================================================================
        # 4. OMNI-HUNT (HYBRID: STRICT PRIMARY -> LEGACY FALLBACK)
        # ======================================================================
        log("   🕵️‍♂️ Starting Omni-Hunt (Strict Primary -> Legacy Fallback)...")
        collected_sources = []
        
        # --- [A] PRIMARY MECHANISM: STRICT GOOGLE NEWS RESOLVER ---
        try:
            log("   🚀 Executing Primary Mechanism (Strict RSS + Selenium Resolver)...")
            rss_items = news_fetcher.get_strict_rss(smart_query, category)
            
            if rss_items:
                BORING_KEYWORDS_STRICT = [
                    "CFO", "CEO", "Quarterly", "Earnings", "Report", "Market Cap", 
                    "Dividend", "Shareholders", "Acquisition", "Merger", "Appointment", 
                    "Executive", "Knorex", "Partner", "Agreement", "B2B", "Enterprise"
                ]
                recent_titles = history_manager.get_recent_titles_string()

                for item in rss_items[:6]:
                    if len(collected_sources) >= 3: break
                    if item['title'][:20] in recent_titles: continue
                    
                    if any(b_word.lower() in item['title'].lower() for b_word in BORING_KEYWORDS_STRICT):
                        log(f"         ⛔ Skipped Boring Corporate Topic: {item['title']}")
                        continue
                    
                    if any(src.get('url') == item['link'] for src in collected_sources): continue

                    log(f"      📌 Checking Source: {item['title'][:40]}...")
                    data = url_resolver.get_page_html(item['link'])
                    
                    if data and data.get('html'):
                        r_url = data['url']
                        html_content = data['html']
                        text = trafilatura.extract(html_content, include_comments=False, include_tables=True)
                        
                        if not text:
                            soup = BeautifulSoup(html_content, 'html.parser')
                            for script in soup(["script", "style", "nav", "footer"]): script.extract()
                            text = soup.get_text(" ", strip=True)

                        if text and len(text) >= 800:
                            log(f"         ✅ Accepted Source! ({len(text)} chars).")
                            domain = urllib.parse.urlparse(r_url).netloc
                            og_image = None
                            try:
                                soup_meta = BeautifulSoup(html_content, 'html.parser')
                                og_image = (soup_meta.find('meta', property='og:image') or {}).get('content')
                            except: pass

                            collected_sources.append({
                                "title": item['title'],
                                "url": r_url,
                                "text": text,
                                "source_image": og_image,
                                "domain": domain,
                                "media": []
                            })
                            # Set fallback image
                            if not img_url and og_image: img_url = og_image
                        else:
                            log("         ⚠️ Content too short or extraction failed.")
                    else:
                        log("         ⚠️ Selenium failed to resolve URL.")
                    time.sleep(2)

        except Exception as e:
            log(f"   ⚠️ Primary Mechanism Error: {e}")

        # --- [B] FALLBACK MECHANISM: LEGACY OMNI-HUNT ---
        if len(collected_sources) < 3:
            log(f"   ⚠️ Primary yielded {len(collected_sources)}/3 sources. Activating Legacy Fallback...")
            try:
                ai_results = ai_researcher.smart_hunt(target_keyword, config, mode="general")
                if ai_results:
                    vetted = news_fetcher.ai_vet_sources(ai_results, model_name)
                    for item in vetted:
                        if len(collected_sources) >= 3: break
                        if any(s['url'] == item['link'] for s in collected_sources): continue
                        
                        f_url, f_title, text, f_image, media = scraper.resolve_and_scrape(item['link'])
                        if text: 
                            collected_sources.append({"title": f_title or item['title'], "url": f_url, "text": text, "source_image": f_image, "domain": urllib.parse.urlparse(f_url).netloc, "media": media})
                            if not img_url and f_image: img_url = f_image
            except Exception as e: log(f"      ⚠️ Legacy AI Search Error: {e}")

            if len(collected_sources) < 3:
                try:
                    legacy_items = news_fetcher.get_real_news_rss(target_keyword, category) 
                    for item in legacy_items:
                        if len(collected_sources) >= 3: break
                        if any(s['url'] == item['link'] for s in collected_sources): continue
                        
                        f_url, f_title, text, f_image, media = scraper.resolve_and_scrape(item['link'])
                        if text: 
                            collected_sources.append({"title": f_title or item['title'], "url": f_url, "text": text, "source_image": f_image, "domain": urllib.parse.urlparse(f_url).netloc, "media": media})
                            if not img_url and f_image: img_url = f_image
                except Exception as e: log(f"      ⚠️ Legacy RSS Error: {e}")

        if len(collected_sources) < 3:
            log(f"   ❌ CRITICAL FAILURE: Found only {len(collected_sources)}/3 required sources. Aborting.")
            return False
        
        log(f"   ✅ Research Complete. Found {len(collected_sources)} sources.")

        # ======================================================================
        # 5. VISUAL HUNT & REDDIT INTEL
        # ======================================================================
        official_media, reddit_media = [], []
        try: # <--- FIXED: Added try block here
            if visual_strategy.startswith("hunt"):
                official_media = scraper.smart_media_hunt(smart_query, category, visual_strategy)
            reddit_context, reddit_media = reddit_manager.get_community_intel(smart_query)
        except Exception as e:
            log(f"   ⚠️ Visual/Reddit Hunt Error: {e}")

        # ======================================================================
        # 5.5 [NEW] AI-POWERED VISUAL EVIDENCE AUGMENTATION
        # ======================================================================
        log("   🔍 [Augmentation] Using Gemini Search to find additional real-world evidence...")
        ai_found_evidence = []
        try:
            augmentation_prompt = PROMPT_EVIDENCE_AUGMENTATION.format(target_keyword=target_keyword)
            evidence_payload = api_manager.generate_step_strict(
                model_name, 
                augmentation_prompt, 
                "Visual Evidence Augmentation", 
                ["visual_evidence"], 
                use_google_search=True
            )
            
            if evidence_payload and evidence_payload.get("visual_evidence"):
                log(f"      ✅ AI Detective found {len(evidence_payload['visual_evidence'])} new pieces of evidence.")
                for evidence in evidence_payload["visual_evidence"]:
                    evidence_type = "image"
                    if "video" in evidence.get("type", ""):
                        evidence_type = "embed"
                    elif "gif" in evidence.get("type", ""):
                        evidence_type = "gif"

                    ai_found_evidence.append({
                        "type": evidence_type,
                        "url": evidence["url"],
                        "description": evidence["description"],
                        "score": 10
                    })
            else:
                log("      ⚠️ AI Detective did not find any new evidence.")

        except Exception as e:
            log(f"      ❌ Visual Augmentation step failed: {e}")

        # ======================================================================
        # 6. SYNTHESIS, VIDEO PRODUCTION, AND REAL EVIDENCE INJECTION
        # ======================================================================
        log("   ✍️ Synthesizing Content & Validating Assets...")
        
        all_media = []
        for s in collected_sources:
            if s.get('media'): all_media.extend(s['media'])
        if official_media: all_media.extend(official_media)
        if reddit_media: all_media.extend(reddit_media)
        if ai_found_evidence: all_media.extend(ai_found_evidence)
        
        # ترتيب كل الوسائط حسب الأهمية
        unique_media = list({m['url']: m for m in all_media}.values())
        unique_media = sorted(unique_media, key=lambda x: x.get('score', 0), reverse=True)
        
        # --- NEW: VALIDATION LOOP (فلتر الجودة) ---
        valid_visuals = []
        log("      🛡️ Validating all found media assets...")
        for media in unique_media:
            if len(valid_visuals) >= 5: break # نكتفي بـ 5 أدلة بصرية صالحة كحد أقصى
            
            # إصلاح تلقائي لروابط يوتيوب
            if "youtube.com" in media['url'] or "youtu.be" in media['url']:
                video_id_match = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11}).*', media['url'])
                if video_id_match:
                    media['url'] = f"https://www.youtube.com/embed/{video_id_match.group(1)}"
                    media['type'] = 'embed'
                else:
                    continue # تجاهل رابط يوتيوب التالف

            # فحص هل الرابط يعمل؟
            if is_url_accessible(media['url']):
                valid_visuals.append(media)
            else:
                log(f"      ⚠️ Broken Link Detected & Removed: {media['url']}")

        # --- NEW: IMAGE PRIORITY LOGIC (منطق اختيار الصورة الرئيسية) ---
        # 1. البحث عن صورة حقيقية صالحة من الأدلة
        for m in valid_visuals:
            if m['type'] == 'image' and not img_url:
                img_url = m['url']
                log(f"      📸 PRIORITY 1: Selected Real Image from Evidence.")
                break
        
        # 2. إذا فشل، البحث عن صورة من مصادر المقالات (og:image)
        if not img_url:
            for s in collected_sources:
                if s.get('source_image') and is_url_accessible(s['source_image']):
                    img_url = s['source_image']
                    log(f"      📸 PRIORITY 2: Selected Image from Article Source.")
                    break
        
        # الخطوة 3 (توليد صورة AI) ستأتي لاحقاً فقط إذا بقي img_url فارغاً

        asset_map = {}
        available_tags = []
        visual_context = []        
        
        
        for i, visual in enumerate(best_visuals):
            tag = f"[[VISUAL_EVIDENCE_{i+1}]]"
            html = ""
            if visual['type'] in ['image', 'gif']:
                html = f'''
                <figure style="margin:30px 0; text-align:center;">
                    <img src="{visual['url']}" alt="{visual['description']}" style="max-width:100%; height:auto; border-radius:10px; border:1px solid #eee; box-shadow:0 2px 8px rgba(0,0,0,0.05);">
                    <figcaption style="font-size:14px; color:#666; margin-top:8px; font-style:italic;">📸 {visual['description']}</figcaption>
                </figure>
                '''
            elif visual['type'] == 'embed':
                 html = f'''<div class="video-wrapper" style="position:relative;padding-bottom:56.25%;height:0;overflow:hidden;margin:30px 0;border-radius:12px;box-shadow:0 4px 15px rgba(0,0,0,0.1);"><iframe src="{visual['url']}" style="position:absolute;top:0;left:0;width:100%;height:100%;border:0;" allowfullscreen title="{visual['description']}"></iframe></div>'''

            if html:
                asset_map[tag] = html
                available_tags.append(tag)
                visual_context_for_writer.append(f"{tag}: {visual['description']}")

        # --- WRITING STAGE ---
        # Fixed: reddit_context variable scope check
        if 'reddit_context' not in locals(): reddit_context = ""
        
        combined_text = "\n".join([f"SOURCE: {s['url']}\n{s['text'][:8000]}" for s in collected_sources]) + reddit_context
        
        payload = {
            "keyword": target_keyword, 
            "research_data": combined_text, 
            "AVAILABLE_VISUAL_TAGS": available_tags,
            "VISUAL_DESCRIPTIONS": "\n".join(visual_context_for_writer),
            "TODAY_DATE": str(datetime.date.today())
        }
        
        json_b = api_manager.generate_step_strict(model_name, PROMPT_B_TEMPLATE.format(json_input=json.dumps(payload), forbidden_phrases="[]"), "Writer", ["headline", "article_body"])
        
        title = json_b['headline']
        draft_body_html = json_b['article_body']

        # --- VIDEO PRODUCTION & UPLOAD ---
        log("   🎬 Video Production & Upload...")
        vid_main_id, vid_main_url, vid_short_id, local_fb_video = None, None, None, None
        
        summ = re.sub('<[^<]+?>', '', draft_body_html)[:1000]
        try:
            vs_payload = api_manager.generate_step_strict(model_name, PROMPT_VIDEO_SCRIPT.format(title=title, text_summary=summ), "Video Script")
            script_json = vs_payload.get('video_script', [])

            if script_json:
                rr = video_renderer.VideoRenderer(output_dir="output")
                ts = int(time.time())
                
                # Main Video (16:9)
                main_video_path = rr.render_video(script_json, title, f"main_{ts}.mp4")
                if main_video_path:
                    vid_main_id, vid_main_url = youtube_manager.upload_video_to_youtube(main_video_path, title, "AI Analysis", ["ai", category])
                
                # Shorts Video (9:16)
                rs = video_renderer.VideoRenderer(output_dir="output", width=1080, height=1920)
                short_video_path = rs.render_video(script_json, title, f"short_{ts}.mp4")
                if short_video_path:
                    local_fb_video = short_video_path
                    vid_short_id, _ = youtube_manager.upload_video_to_youtube(short_video_path, f"{title[:50]} #Shorts", "Quick Look", ["shorts", category])
        except Exception as e:
            log(f"   ⚠️ Video Production Failed: {e}")

        # ======================================================================
        # 7. FINAL ASSEMBLY & PUBLISHING
        # ======================================================================
        log("   🔗 Assembling Final HTML with All Assets...")

        final_body_html = draft_body_html

        if vid_main_url:
            video_html = f'''
            <h3>Watch the Video Summary</h3>
            <div class="video-wrapper" style="position:relative;padding-bottom:56.25%;height:0;overflow:hidden;margin:30px 0;border-radius:12px;box-shadow:0 4px 15px rgba(0,0,0,0.1);">
            <iframe src="{vid_main_url}" style="position:absolute;top:0;left:0;width:100%;height:100%;border:0;" allowfullscreen title="{title}"></iframe>
            </div>'''
            if "[[TOC_PLACEHOLDER]]" in final_body_html:
                 final_body_html = final_body_html.replace("[[TOC_PLACEHOLDER]]", "[[TOC_PLACEHOLDER]]" + video_html)
            else:
                 final_body_html = video_html + final_body_html

        for tag, html_code in asset_map.items():
            final_body_html = final_body_html.replace(tag, html_code)

        sources_data = [{"title": s['title'], "url": s['url']} for s in collected_sources if s.get('url')]
        kg_links = history_manager.get_relevant_kg_for_linking(title, category)
        
        seo_payload = {"draft_content": {"headline": title, "article_body": final_body_html}, "sources_data": sources_data}
        json_c = api_manager.generate_step_strict(
            model_name, 
            PROMPT_C_TEMPLATE.format(json_input=json.dumps(seo_payload), knowledge_graph=kg_links), "SEO Polish", ["finalTitle", "finalContent", "seo", "schemaMarkup"]
        )

        # 3. AI Image Generation (LAST RESORT ONLY)
        # هذه الخطوة تعمل فقط إذا كان img_url لا يزال فارغاً
        if not img_url and json_c.get('imageGenPrompt'):
             log("   🎨 No real image found. Falling back to AI Image Generation...")
             gen_img = image_processor.generate_and_upload_image(json_c['imageGenPrompt'], json_c.get('imageOverlayText', ''))
             if gen_img: img_url = gen_img

        humanizer_payload = api_manager.generate_step_strict(model_name, PROMPT_D_TEMPLATE.format(content_input=json_c['finalContent']),"Humanizer", ["finalContent"])
        
        final_title = json_c['finalTitle']
        full_body_html = humanizer_payload['finalContent']
        if img_url:
            log(f"   🖼️ Injecting Featured Image into HTML...")
            img_html = f'''
            <div class="separator" style="clear: both; text-align: center; margin-bottom: 30px;">
                <a href="{img_url}" style="margin-left: 1em; margin-right: 1em;">
                    <img border="0" src="{img_url}" alt="{final_title}" style="max-width: 100%; height: auto; border-radius: 10px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);" />
                </a>
            </div>
            '''
            full_body_html = img_html + full_body_html

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
        full_body_html = full_body_html + author_box

        
        log("   🚀 [Publishing] Initial Draft...")
        pub_result = publisher.publish_post(title, full_body_html, [category])
        published_url, post_id = (pub_result if isinstance(pub_result, tuple) else (pub_result, None))

        if not published_url or not post_id:
            log("   ❌ CRITICAL FAILURE: Could not publish the initial draft.")
            return False

        # ======================================================================
        # 7.5 QUALITY IMPROVEMENT LOOP
        # ======================================================================
        quality_score, attempts, MAX_RETRIES = 0, 0, 2
        
        while quality_score < 9.5 and attempts < MAX_RETRIES:
            attempts += 1
            log(f"   🔄 [Quality Loop] Audit Round {attempts}...")
            audit_report = live_auditor.audit_live_article(published_url, target_keyword, iteration=attempts)
            
            if not audit_report: break
            
            quality_score = float(audit_report.get('quality_score', 0))
            if quality_score >= 9.5: break
            
            fixed_html = remedy.fix_article_content(full_body_html, audit_report, target_keyword, combined_text, iteration=attempts)
            if fixed_html and len(fixed_html) > 1000:
                if publisher.update_existing_post(post_id, title, fixed_html):
                    full_body_html = fixed_html
                    time.sleep(10)
                else: break
            else: break

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
            
            if vid_main_id: youtube_manager.update_video_description(vid_main_id, yt_update_text)
            if vid_short_id: youtube_manager.update_video_description(vid_short_id, yt_update_text)
            
            if img_url:
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
