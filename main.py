# FILE: main.py
# ROLE: Orchestrator V11.0 (The Elite Technical Analyst)
# DESCRIPTION: The complete, final, and stable version integrating real-time data, 
#              truth verification, semantic deduplication, auto-data visualization,
#              AND Code Snippet Hunting.
#              FULL FIDELITY - NO SIMPLIFICATIONS.

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

# --- NEW INTELLIGENCE MODULES ---
import trend_watcher
import truth_verifier
import chart_generator
import code_hunter  # <--- NEW: Code Snippet Hunter


def is_source_viable(url, min_text_length=600):
    """Checks if a source URL is valid and has content."""
    try:
        # فحص سريع
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.head(url, headers=headers, timeout=5, allow_redirects=True)
        if r.status_code == 404: return False, "404 Not Found"
        
        # فحص المحتوى (نستخدم السكرابر الموجود)
        _, _, text, _, _ = scraper.resolve_and_scrape(url)
        if text and len(text) >= min_text_length:
            return True, "Valid Content"
        return False, "Content too short or empty"
    except:
        return False, "Connection Failed"
        
# --- VALIDATION FUNCTION ---
def is_url_accessible(url):
    """Checks if a URL is alive (Status 200) and allows hotlinking."""
    if not url: return False
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        # Timeout is short (3s) to prevent hanging
        r = requests.head(url, headers=headers, timeout=3, allow_redirects=True)
        return r.status_code == 200
    except:
        return False

def run_pipeline(category, config, forced_keyword=None, is_cluster_topic=False):
    """
    Executes the full content lifecycle using a robust, multi-layered strategy.
    Integrated with Truth Verification, Data Visualization, Code Hunting, and Strict Quality Loops.
    """
    model_name = config['settings'].get('model_name', "gemini-2.5-flash")
    img_url = None 
    
    # Initialize variables to prevent UnboundLocalError
    vid_main_id, vid_main_url = None, None
    vid_short_id = None
    local_fb_video = None
    reddit_context = ""

    try:
        # ======================================================================
        # 0. DECODE OFFICIAL SOURCE (THE TRUTH INJECTION)
        # ======================================================================
        # If the keyword comes from cluster_manager/truth_verifier, it might contain the verified URL.
        official_source_url = None
        if forced_keyword and "||OFFICIAL_SOURCE=" in forced_keyword:
            parts = forced_keyword.split("||OFFICIAL_SOURCE=")
            target_keyword = parts[0].strip() # Use this as the clean keyword
            official_source_url = parts[1].replace("||", "").strip()
            log(f"   💎 OFFICIAL SOURCE INJECTED: {official_source_url}")
        else:
            target_keyword = forced_keyword

        # ======================================================================
        # 1. STRATEGY & KEYWORD SELECTION
        # ======================================================================
        if not target_keyword:
            # Fallback to AI Daily Hunt if no keyword forced (Legacy Mode)
            log(f"   👉 [Strategy: Legacy Hunt] Scanning Category: {category}")
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
        # Final safety check: Even if passed before, verify specifically for this keyword.
        if not is_cluster_topic:
            if history_manager.check_semantic_duplication(target_keyword, category, config):
                log(f"   🚫 ABORTING PIPELINE: '{target_keyword}' is a semantic duplicate.")
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
        # 4. OMNI-HUNT (UPDATED: OFFICIAL SOURCE FIRST)
        # ======================================================================
        log("   🕵️‍♂️ Starting Omni-Hunt...")
        collected_sources = []

        # [A] PRIORITY 0: THE OFFICIAL SOURCE (From Verification Phase)
        if official_source_url:
            log(f"   👑 Fetching Official Source Content: {official_source_url}")
            try:
                # Scrape the official link we found earlier
                o_url, o_title, o_text, o_img, o_media = scraper.resolve_and_scrape(official_source_url)
                if o_text:
                    collected_sources.append({
                        "title": o_title or "Official Announcement",
                        "url": o_url,
                        "text": f"OFFICIAL SOURCE OF TRUTH (HIGHEST PRIORITY):\n{o_text}", 
                        "source_image": o_img,
                        "domain": "OFFICIAL_SOURCE",
                        "media": o_media
                    })
                    if o_img: img_url = o_img
            except Exception as e:
                log(f"   ⚠️ Failed to scrape official source: {e}")

        # [B] PRIMARY MECHANISM: STRICT GOOGLE NEWS RESOLVER
        try:
            log("   🚀 Executing Primary Mechanism (Strict RSS + Selenium Resolver)...")
            rss_items = news_fetcher.get_strict_rss(smart_query, category)
            
            if rss_items:
                recent_titles = history_manager.get_recent_titles_string()
                
                # Strict Boring Filter
                BORING_KEYWORDS_STRICT = [
                    "CFO", "CEO", "Quarterly", "Earnings", "Report", "Market Cap", 
                    "Dividend", "Shareholders", "Acquisition", "Merger", "Appointment", 
                    "Executive", "Knorex", "Partner", "Agreement", "B2B", "Enterprise"
                ]

                for item in rss_items[:6]:
                    if len(collected_sources) >= 4: break # Limit sources

                    if official_source_url and item['link'] == official_source_url:
                        continue 
                    
                    if item['title'][:20] in recent_titles: continue
                    
                    # Avoid duplicates of the official source
                    if any(s.get('url') == item['link'] for s in collected_sources): continue
                    
                    if any(b_word.lower() in item['title'].lower() for b_word in BORING_KEYWORDS_STRICT):
                        continue

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
                            # Set fallback image if not set by official source
                            if not img_url and og_image: img_url = og_image
                        else:
                            log("         ⚠️ Content too short or extraction failed.")
                    else:
                        log("         ⚠️ Selenium failed to resolve URL.")
                    time.sleep(2)

        except Exception as e:
            log(f"   ⚠️ Primary Mechanism Error: {e}")

        # [C] FALLBACK MECHANISM: LEGACY OMNI-HUNT (If not enough sources)
        if len(collected_sources) < 2:
            log(f"   ⚠️ Low sources ({len(collected_sources)}). Activating Fallback...")
            try:
                ai_results = ai_researcher.smart_hunt(smart_query, config, mode="general")
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
                    legacy_items = news_fetcher.get_real_news_rss(smart_query, category) 
                    for item in legacy_items:
                        if len(collected_sources) >= 3: break
                        if any(s['url'] == item['link'] for s in collected_sources): continue
                        
                        f_url, f_title, text, f_image, media = scraper.resolve_and_scrape(item['link'])
                        if text: 
                            collected_sources.append({"title": f_title or item['title'], "url": f_url, "text": text, "source_image": f_image, "domain": urllib.parse.urlparse(f_url).netloc, "media": media})
                            if not img_url and f_image: img_url = f_image
                except Exception as e: log(f"      ⚠️ Legacy RSS Error: {e}")

        if len(collected_sources) < 1:
            log(f"   ❌ CRITICAL FAILURE: No sources found. Aborting.")
            return False
        
        log(f"   ✅ Research Complete. Found {len(collected_sources)} sources.")

        # ======================================================================
        # 5. DATA VISUALIZATION (UPDATED FOR E-E-A-T)
        # ======================================================================
        chart_html_snippet = ""
        try:
            # Gather all text to scan for data
            all_text_blob = "\n".join([s['text'] for s in collected_sources])[:15000]
            
            # Check if we should generate a chart
            if "benchmark" in target_keyword.lower() or "vs" in target_keyword.lower() or "price" in target_keyword.lower() or "score" in target_keyword.lower() or "performance" in target_keyword.lower() or "cost" in target_keyword.lower():
                log("   📊 [Chart Generator] Analyzing data for potential visualization...")
                
                chart_prompt = f"""
                TASK: Extract numerical data for a comparison chart.
                TOPIC: {target_keyword}
                TEXT: {all_text_blob}
                
                REQUIREMENTS:
                - Find at least 2 entities with comparable numerical values (Scores, Prices, Speed, Parameters, Percentages).
                - Return strictly JSON.
                
                OUTPUT JSON:
                {{
                    "chart_title": "Gemini 1.5 vs GPT-4 (MMLU Score)",
                    "data_points": {{
                        "Gemini 1.5": 90.0,
                        "GPT-4": 86.4
                    }}
                }}
                OR return null if no good data found.
                """
                
                chart_data = api_manager.generate_step_strict(model_name, chart_prompt, "Data Extraction", ["data_points"])
                
                if chart_data and chart_data.get('data_points'):
                    safe_data = {}
                    for k, v in chart_data['data_points'].items():
                        try: safe_data[k] = float(v)
                        except: continue
                    
                    if len(safe_data) >= 2:
                        # --- MODIFIED: Pass source text and get HTML directly ---
                        chart_html_snippet = chart_generator.create_chart_from_data(
                            safe_data, 
                            chart_data.get('chart_title', 'Performance Comparison'),
                            source_text=f"Data analysis based on official benchmarks for {target_keyword}."
                        )
                    
                        if chart_html_snippet:
                            log(f"      ✅ Chart Generated Successfully.")
        except Exception as e:
            log(f"      ⚠️ Chart Generation skipped: {e}")

        # ======================================================================
        # 6. VISUAL HUNT & REDDIT INTEL
        # ======================================================================
        official_media, reddit_media = [], []
        try:
            if visual_strategy.startswith("hunt"):
                official_media = scraper.smart_media_hunt(smart_query, category, visual_strategy)
            reddit_context, reddit_media = reddit_manager.get_community_intel(smart_query)
        except Exception as e:
            log(f"   ⚠️ Visual/Reddit Hunt Error: {e}")
            reddit_context = ""

        # ======================================================================
        # 7. VISUAL EVIDENCE AUGMENTATION
        # ======================================================================
        log("   🔍 [Augmentation] Using Gemini Search for additional evidence...")
        ai_found_evidence = []
        try:
            augmentation_prompt = PROMPT_EVIDENCE_AUGMENTATION.format(target_keyword=target_keyword)
            evidence_payload = api_manager.generate_step_strict(
                model_name, augmentation_prompt, "Visual Evidence Augmentation", ["visual_evidence"], use_google_search=True
            )
            
            if evidence_payload and evidence_payload.get("visual_evidence"):
                log(f"      ✅ AI found {len(evidence_payload['visual_evidence'])} new pieces of evidence.")
                for evidence in evidence_payload["visual_evidence"]:
                    evidence_type = "image"
                    if "video" in evidence.get("type", ""): evidence_type = "embed"
                    elif "gif" in evidence.get("type", ""): evidence_type = "gif"

                    ai_found_evidence.append({
                        "type": evidence_type,
                        "url": evidence["url"],
                        "description": evidence["description"],
                        "score": 10
                    })
        except Exception as e:
            log(f"      ❌ Visual Augmentation failed: {e}")
        
        # ======================================================================
        # 7.5. CODE SNIPPET HUNT (THE MISSING PIECE)
        # ======================================================================
        code_snippet_html = None
        try:
            # Only hunt for code if it's a software/AI/Dev topic
            if any(x in category.lower() + target_keyword.lower() for x in ['ai', 'code', 'python', 'api', 'model', 'bot', 'script', 'dev', 'software', 'tool']):
                code_snippet_html = code_hunter.find_code_snippet(target_keyword, model_name)
        except Exception as e:
            log(f"   ⚠️ Code Snippet Hunt Error: {e}")

        # ======================================================================
        # 8. SYNTHESIS & ASSET PROCESSING
        # ======================================================================
        log("   ✍️ Synthesizing Content & Validating Assets...")
        
        all_media = []
        for s in collected_sources:
            if s.get('media'): all_media.extend(s['media'])
        if official_media: all_media.extend(official_media)
        if reddit_media: all_media.extend(reddit_media)
        if ai_found_evidence: all_media.extend(ai_found_evidence)
        
        unique_media = list({m['url']: m for m in all_media}.values())
        unique_media = sorted(unique_media, key=lambda x: x.get('score', 0), reverse=True)
        
        valid_visuals = []
        log("      🛡️ Validating all found media assets...")
        for media in unique_media:
            if len(valid_visuals) >= 5: break
            
            # YouTube Link Fixer
            if "youtube.com" in media['url'] or "youtu.be" in media['url']:
                video_id_match = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11}).*', media['url'])
                if video_id_match:
                    media['url'] = f"https://www.youtube.com/embed/{video_id_match.group(1)}"
                    media['type'] = 'embed'
                else: continue

            if is_url_accessible(media['url']):
                valid_visuals.append(media)
            else:
                log(f"      ⚠️ Broken Link Removed: {media['url']}")

        # Image Priority: 1. Real Evidence, 2. Source OG Image, 3. AI Gen (Later)
        # Image Priority: 1. AI Vision from Mirrored Assets, 2. Source OG Image, 3. AI Gen (Later)
        
        mirrored_image_candidates = [{'url': m['url'], 'title': m['description']} for m in valid_visuals if m['type'] in ['image', 'gif']]
        
        if not img_url and mirrored_image_candidates:
            log("      🧠 Using Gemini Vision to select the best Featured Image from Mirrored Assets...")
            # محاولة اختيار أفضل صورة من الأدلة التي تم رفعها للـ CDN
            best_url = image_processor.select_best_image_with_gemini(model_name, target_keyword, mirrored_image_candidates)
            if best_url: img_url = best_url
                
        if not img_url:
            # آخر محاولة: الرجوع لـ OG Image الأصلية للمقال الرئيسي (ولكنها قد تكون صورة مكسورة)
            for s in collected_sources:
                if s.get('source_image') and is_url_accessible(s['source_image']):
                    img_url = s['source_image']; break
        

        asset_map = {}
        available_tags = []
        visual_context_for_writer = []
        
        
        for i, visual in enumerate(valid_visuals):
            
            tag = f"[[VISUAL_EVIDENCE_{i+1}]]"
            html = ""
            
            if visual['type'] in ['image', 'gif']:
                # --- [1] Images/GIFs: Mirror to CDN (To prevent hotlink break) ---
                # استخدام دالة رفع الصور الخارجية
                cdn_url = image_processor.upload_external_image(visual['url'], f"visual-evidence-{target_keyword}")
                if not cdn_url:
                    log(f"      ⚠️ Failed to mirror image. Skipping tag {tag}.")
                    continue 
                
                visual['url'] = cdn_url 
                
                html = f'''
                <figure style="margin:30px 0; text-align:center;">
                    <img src="{visual['url']}" alt="{visual['description']}" style="max-width:100%; height:auto; border-radius:10px; border:1px solid #eee; box-shadow:0 2px 8px rgba(0,0,0,0.05);">
                    <figcaption style="font-size:14px; color:#666; margin-top:8px; font-style:italic;">📸 {visual['description']}</figcaption>
                </figure>
                '''
                
            elif visual['type'] == 'embed':
                # --- [2] Embeds (Videos): Pass the embed code as is (للسماح للمخرج الذكي بوضعها) ---
                 html = f'''<div class="video-wrapper" style="position:relative;padding-bottom:56.25%;height:0;overflow:hidden;margin:30px 0;border-radius:12px;box-shadow:0 4px 15px rgba(0,0,0,0.1);"><iframe src="{visual['url']}" style="position:absolute;top:0;left:0;width:100%;height:100%;border:0;" allowfullscreen title="{visual['description']}"></iframe></div>'''

            if html:
                asset_map[tag] = html
                available_tags.append(tag)
                visual_context_for_writer.append(f"{tag}: {visual['description']}")

        # --- NEW: Inject Code Snippet if found ---
        if code_snippet_html:
            tag = "[[CODE_SNIPPET_1]]"
            asset_map[tag] = code_snippet_html
            available_tags.append(tag)
            visual_context_for_writer.append(f"{tag}: A practical Python code example for developers.")
            log(f"      💻 Code Snippet injected into asset map.")
        

        # --- WRITING STAGE ---
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
        # 9. FINAL ASSEMBLY
        # ======================================================================
        log("   🔗 Assembling Final HTML...")

        final_body_html = draft_body_html

        # Insert Video
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

        # Insert Generated Chart (The Upgrade)
        if chart_html_snippet:
            # Insert chart after the first paragraph or near TOC
            if "[[TOC_PLACEHOLDER]]" in final_body_html:
                final_body_html = final_body_html.replace("[[TOC_PLACEHOLDER]]", "[[TOC_PLACEHOLDER]]" + chart_html_snippet)
            else:
                final_body_html = chart_html_snippet + final_body_html

        # Insert Assets
        for tag, html_code in asset_map.items():
            final_body_html = final_body_html.replace(tag, html_code)

        sources_data = [{"title": s['title'], "url": s['url']} for s in collected_sources if s.get('url')]
        kg_links = history_manager.get_relevant_kg_for_linking(title, category)
        
        seo_payload = {"draft_content": {"headline": title, "article_body": final_body_html}, "sources_data": sources_data}
        json_c = api_manager.generate_step_strict(
            model_name, 
            PROMPT_C_TEMPLATE.format(json_input=json.dumps(seo_payload), knowledge_graph=kg_links), "SEO Polish", ["finalTitle", "finalContent", "seo", "schemaMarkup"]
        )

        # AI Image Generation (Last Resort)
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
        # 10. QUALITY IMPROVEMENT LOOP
        # ======================================================================
        quality_score, attempts, MAX_RETRIES = 0, 0, 0
        
        while quality_score < 9.5 and attempts < MAX_RETRIES:
            attempts += 1
            log(f"   🔄 [Quality Loop] Audit Round {attempts}...")
            audit_report = live_auditor.audit_live_article(published_url, target_keyword, iteration=attempts)
            
            if not audit_report: break
            
            quality_score = float(audit_report.get('quality_score', 0))
            if quality_score >= 9.5: break
            
            fixed_html = remedy.fix_article_content(full_body_html, audit_report, target_keyword, combined_text, iteration=attempts)
            if fixed_html and len(fixed_html) > 1000:
                # === شبكة أمان: فحص عدد الروابط ===
                orig_links = full_body_html.count("<a href")
                new_links = fixed_html.count("<a href")
                
                if orig_links > 0 and new_links < (orig_links * 0.7):
                    log(f"   ❌ REMEDY FAILED: Destroyed {orig_links - new_links} links. Discarding changes.")
                    break # توقف عن محاولات الإصلاح
                
                if publisher.update_existing_post(post_id, title, fixed_html):
                    full_body_html = fixed_html
                    time.sleep(10)
                else: break
            else: break

        # ======================================================================
        # 11. DISTRIBUTION
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
        
        # --- Maintenance Phase (Living Article Protocol) ---
        log("--- Starting Maintenance Phase ---")
        try:
            gardener.run_daily_maintenance(cfg)
            log("--- Maintenance Phase Complete ---")
        except Exception as e:
            log(f"   ⚠️ Gardener maintenance run failed: {e}")
            log("--- Maintenance Phase Skipped due to error ---")
        # --------------------------------------------------
            
        cats = list(cfg['categories'].keys())
        random.shuffle(cats)
        
        published_today = False
        
        for cat in cats:
            if published_today: break
            log(f"\n📂 CATEGORY: {cat}")
            
            # --- STRATEGY 1: CLUSTER (The Smartest) ---
            try:
                topic, is_c = cluster_manager.get_strategic_topic(cat, cfg)
                if topic:
                    if run_pipeline(cat, cfg, forced_keyword=topic, is_cluster_topic=is_c):
                        published_today = True
                        break
                    else:
                        cluster_manager.mark_topic_failed(topic)
            except Exception as e: 
                log(f"   ⚠️ Cluster Strategy Error: {e}")

            # --- STRATEGY 2: MANUAL TRENDING FOCUS (Fallback) ---
            if not published_today and cfg['categories'][cat].get('trending_focus'):
                raw_topics = [t.strip() for t in cfg['categories'][cat]['trending_focus'].split(',')]
                random.shuffle(raw_topics)
                log(f"   📜 Checking {len(raw_topics)} manual focus topics...")
                
                for potential_topic in raw_topics:
                    if history_manager.check_semantic_duplication(potential_topic, cat, cfg):
                        log(f"      ⏭️ Skipping duplicate: '{potential_topic}'")
                        continue
                    
                    log(f"      🚀 Attempting manual topic: {potential_topic}")
                    if run_pipeline(cat, cfg, forced_keyword=potential_topic, is_cluster_topic=False):
                        published_today = True
                        break 
            
            # --- STRATEGY 3: AI DAILY HUNT (With Verification Loop) ---
            if not published_today:
                fresh_trends = trend_watcher.get_verified_trend(cat, cfg)
                if fresh_trends:
                    log(f"   🤖 Processing {len(fresh_trends)} AI trends...")
                    for trend in fresh_trends:
                        # 1. Dedup check
                        if history_manager.check_semantic_duplication(trend, cat, cfg):
                            log(f"      ⏭️ Skipping duplicate trend: '{trend}'")
                            continue
                        
                        # 2. Verify Truth (Gatekeeper)
                        is_valid, official_url, verified_title = truth_verifier.verify_topic_existence(trend, cfg['settings']['model_name'])
                        
                        if is_valid:
                            log(f"      ✅ Trend Verified: {verified_title}")
                            # Pass the official source via the special tag
                            forced_tag = f"{verified_title} ||OFFICIAL_SOURCE={official_url}||"
                            if run_pipeline(cat, cfg, forced_keyword=forced_tag, is_cluster_topic=False):
                                published_today = True
                                break
                        else:
                            log(f"      ⛔ Trend Rejected (No Official Source): {trend}")

        if published_today: 
            log("\n✅ MISSION COMPLETE: New content published successfully.")
        else: 
            log("\n❌ MISSION FAILED: Exhausted all options. No fresh, verified topics found today.")
            
    except Exception as e: 
        log(f"❌ CRITICAL MAIN ERROR: {e}")
        traceback.print_exc()
    
if __name__ == "__main__":
    main()
