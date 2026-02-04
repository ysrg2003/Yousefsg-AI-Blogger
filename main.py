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
import image_enricher
from urllib.parse import urlparse


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


        # ... (بعد الحصول على target_keyword)
        # 1. NEW: AI Intent Analysis Step (V2.0)
        log("   🧠 [Strategy] Analyzing Topic Intent & Accessibility...")
        intent_prompt = PROMPT_ARTICLE_INTENT.format(target_keyword=target_keyword, category=category)
        try:
            intent_analysis = api_manager.generate_step_strict(
                model_name, intent_prompt, "Intent Analysis", ["content_type", "visual_strategy"]
            )
            content_type = intent_analysis.get("content_type", "News Analysis")
            visual_strategy = intent_analysis.get("visual_strategy", "hunt_for_screenshot")
            is_b2b = intent_analysis.get("is_enterprise_b2b", False) # متغير جديد
            
            log(f"   🎯 Intent: {content_type} | B2B Mode: {is_b2b} | Strategy: {visual_strategy}")
            
            # --- تعديل جذري: منع الكود للمنتجات المغلقة ---
            if is_b2b:
                log("      🔒 Enterprise Topic detected. Disabling Code Hunter to prevent hallucinations.")
                # نغير نوع المحتوى إجبارياً إذا كان الكاتب قد أخطأ
                if content_type == "Guide": content_type = "News Analysis"
                
        except Exception as e:
            log(f"   ⚠️ Intent Analysis Failed: {e}. Defaulting to Safe Mode.")
            content_type = "News Analysis"
            visual_strategy = "generate_infographic" # أأمن خيار
            is_b2b = True # نفترض الأسوأ للحماية

        
        # ... (استبدال الخطوة القديمة 3 بهذه المتغيرات الجديدة)
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

        official_media_assets = []
        official_domain = None
        # [A] PRIORITY 0: THE OFFICIAL SOURCE (From Verification Phase)
        if official_source_url:
            log(f"   👑 Fetching Official Source Content: {official_source_url}")
            official_domain = urlparse(official_source_url).netloc
            try:
                # لاحظ: نستقبل المتغير الخامس o_media
                o_url, o_title, o_text, o_img, o_media = scraper.resolve_and_scrape(official_source_url)
                if o_text:
                    collected_sources.append({
                        "title": o_title or "Official Announcement",
                        "url": o_url,
                        "text": f"OFFICIAL SOURCE OF TRUTH:\n{o_text}",
                        "source_image": o_img,
                        "domain": "OFFICIAL_SOURCE",
                        "media": o_media
                    })
                    if o_img: img_url = o_img
                    if o_media: official_media_assets = o_media # حفظ الصور الرسمية
                    log(f"      📸 Extracted {len(o_media)} images from official source.")
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
	# 8. BUILD DATA BUNDLE & ARCHITECT BLUEPRINT
	# ======================================================================
	log("   🧠 Assembling data bundle for The Architect...")
	
	# --- A. ASSEMBLE TEXT DATA ---
	# This combines all research and Reddit discussions into one text block
	combined_text = "\n".join([f"SOURCE: {s['url']}\n{s['text'][:8000]}" for s in collected_sources])
	if reddit_context:
	    combined_text += "\n\n--- REDDIT COMMUNITY INTEL ---\n" + reddit_context
	
	# --- B. ASSEMBLE VISUAL CONTEXT ---
	# This creates a simple list of descriptions for the visuals available
	visual_context_for_writer = []
	# (The asset processing loop from later will be moved here)
	asset_map = {}
	available_tags = []
	
	for i, visual in enumerate(valid_visuals):
	    tag = f"[[VISUAL_EVIDENCE_{i+1}]]"
	    # We only create context for the writer here, not the full HTML yet
	    available_tags.append(tag)
	    visual_context_for_writer.append(f"{tag}: {visual['description']}")
	
	if code_snippet_html:
	    tag = "[[CODE_SNIPPET_1]]"
	    available_tags.append(tag)
	    visual_context_for_writer.append(f"{tag}: A practical Python code example for developers.")
	
	if chart_html_snippet:
	    tag = "[[GENERATED_CHART]]"
	    available_tags.append(tag)
	    visual_context_for_writer.append(f"{tag}: A data visualization chart comparing key metrics.")
	
	# --- C. CALL THE ARCHITECT ---
	import content_architect
	blueprint = content_architect.create_article_blueprint(
	    target_keyword,
	    content_type,
	    combined_text,
	    reddit_context,
	    "\n".join(visual_context_for_writer),
	    model_name
	)
	
	if not blueprint or not blueprint.get("article_blueprint"):
	    log("   ❌ CRITICAL FAILURE: Blueprint creation failed. Aborting pipeline.")
	    return False
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
						# The function returns a URL, not HTML. Let's store it correctly.
						chart_url = chart_generator.create_chart_from_data(
						    safe_data,
						    chart_data.get('chart_title', 'Performance Comparison')
						)
						
						if chart_url:
						    log(f"      ✅ Chart Generated & Uploaded: {chart_url}")
						    # Now, we build the HTML snippet ourselves using the returned URL
						    chart_html_snippet = f'''
						    <figure style="margin: 30px auto; text-align: center;">
						        <img src="{chart_url}" alt="{chart_data.get('chart_title', 'Performance Comparison')}" style="width: 100%; border-radius: 8px; border: 1px solid #ddd; box-shadow: 0 4px 12px rgba(0,0,0,0.08);">
						        <figcaption style="font-size: 13px; color: #555; margin-top: 8px; font-style: italic;">📊 Data analysis based on research for {target_keyword}</figcaption>
						    </figure>
						    '''
					
                        
        # ======================================================================
        # 6. VISUAL HUNT & REDDIT INTEL
        # ======================================================================
        official_media, reddit_media = [], []
        try:
            if visual_strategy.startswith("hunt"):
                official_media = scraper.smart_media_hunt(smart_query, category, visual_strategy,content_type)
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
            if not is_b2b and any(x in category.lower() + target_keyword.lower() for x in ['ai', 'code', 'python', 'api', 'model', 'bot', 'script', 'dev', 'software', 'tool']):
                code_snippet_html = code_hunter.find_code_snippet(target_keyword, model_name)
        except Exception as e:
            log(f"   ⚠️ Code Snippet Hunt Error: {e}")

        
        
        # في ملف main.py، داخل دالة run_pipeline

# ... (بعد تجميع كل البيانات: combined_text, reddit_context, visual_context_for_writer) ...

        # في ملف main.py، داخل دالة run_pipeline

# ... (بعد تجميع كل البيانات: combined_text, reddit_context, visual_context_for_writer) ...

        # ======================================================================
        # 8. THE ARCHITECT PHASE (STRATEGIC BLUEPRINT CREATION)
        # ======================================================================
        import content_architect # استدعاء العقل الجديد
        
        blueprint = content_architect.create_article_blueprint(
            target_keyword,
            content_type, # تمرير نية المستخدم للمهندس
            combined_text,
            reddit_context,
            "\n".join(visual_context_for_writer),
            model_name
        )

        if not blueprint or not blueprint.get("article_blueprint"):
            log("   ❌ CRITICAL FAILURE: Blueprint creation failed. Aborting pipeline.")
            return False

        # ======================================================================
        # 9. THE ARTISAN PHASE (WRITING FROM BLUEPRINT)
        # ======================================================================
        log("   ✍️ [The Artisan] Executing the blueprint to write the article...")
        
        # نرسل "المخطط" + البيانات الخام للعامل
        artisan_prompt = PROMPT_B_TEMPLATE.format(
            blueprint_json=json.dumps(blueprint),
            raw_data_bundle=json.dumps({
                "research": combined_text[:10000],
                "reddit": reddit_context[:5000]
            })
        )
        
        json_b = api_manager.generate_step_strict(
            model_name, 
            artisan_prompt, 
            "Artisan Writer", 
            ["headline", "article_body"]
        )

        # نستخرج العنوان من المخطط لضمان الاتساق
        title = blueprint.get("final_title", json_b['headline'])
        draft_body_html = json_b['article_body']

# ... (باقي الكود يستمر كما هو) ...
        
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

        # CRITICAL FIX: إعطاء الأولوية للصور السياقية (Screenshots)
        valid_visuals = []
        process_visuals = []  # لقطات الشاشة و UI
        general_visuals = []  # الصور العامة
        log("      🛡️ Validating all found media assets...")
        for media in unique_media:
            if len(valid_visuals) >= 5: break

            # YouTube Link Fixer
            if media['type'] in ['embed', 'video'] or any(domain in media['url'] for domain in ["youtube.com", "youtu.be", "vimeo.com"]):
                log(f"      🚫 Policy Blocked External Video/Embed: {media['url'][:50]}")
                continue

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


                # [CRITICAL FIX]: MANDATORY IMAGE MIRRORING TO GITHUB CDN
        if img_url:
            log(f"   🖼️ Enforcing Self-Hosting Policy for Featured Image: {img_url[:50]}...")

            # نستخدم دالة upload_external_image التي تقوم بالتحميل، تطبيق الـ Blur، والرفع
            # نستخدم target_keyword كاسم ملف أساسي
            featured_img_cdn_url = image_processor.upload_external_image(
                img_url,
                f"featured-img-{target_keyword}"
            )

            if featured_img_cdn_url:
                # تحديث img_url لـ CDN URL الجديد
                img_url = featured_img_cdn_url
                log(f"      ✅ Featured Image successfully mirrored to CDN: {img_url}")
            else:
                # إذا فشل الرفع لأي سبب (مثل خطأ في GitHub Token)، نضطر لإزالة الرابط
                # لتجنب نشر صورة من مصدر خارجي.
                log("      ❌ CRITICAL: Failed to mirror Featured Image to CDN. Removing image to maintain policy.")
                img_url = None

        # ... (بقية المنطق يستمر) ...

        # ... (حوالي السطر 700 - حقن الصورة الرئيسية في HTML)
        if img_url:
            log(f"   🖼️ Injecting Featured Image into HTML...")


        asset_map = {}
        available_tags = []
        visual_context_for_writer = []

        # --- FIXED ASSET PROCESSING LOOP ---
        for i, visual in enumerate(valid_visuals):
            tag = f"[[VISUAL_EVIDENCE_{i+1}]]"
            html = ""
            
            if visual['type'] in ['image', 'gif']:
                # 1. Mirror to CDN
                cdn_url = image_processor.upload_external_image(visual['url'], f"visual-evidence-{target_keyword}")
                
                if not cdn_url:
                    log(f"      ⚠️ Failed to mirror image. Skipping tag {tag}.")
                    continue

                # Corrected: use 'visual' instead of 'media'
                visual['url'] = cdn_url 

                # Classification logic
                if "screenshot" in visual['url'].lower() or visual['url'].lower().endswith('.png') or 'ui' in visual['description'].lower():
                    process_visuals.append(visual)
                else:
                    general_visuals.append(visual)

                html = f'''
                <figure style="margin:30px 0; text-align:center;">
                    <img src="{visual['url']}" alt="{visual['description']}" style="max-width:100%; height:auto; border-radius:10px; border:1px solid #eee; box-shadow:0 2px 8px rgba(0,0,0,0.05);">
                    <figcaption style="font-size:14px; color:#666; margin-top:8px; font-style:italic;">📸 {visual['description']}</figcaption>
                </figure>
                '''
                
            elif visual['type'] == 'embed':
                embed_url = visual.get('url')
                if embed_url and isinstance(embed_url, str) and embed_url.startswith("https://"):
                    html = f'''<div class="video-wrapper" style="position:relative;padding-bottom:56.25%;height:0;overflow:hidden;margin:30px 0;border-radius:12px;box-shadow:0 4px 15px rgba(0,0,0,0.1);"><iframe src="{embed_url}" style="position:absolute;top:0;left:0;width:100%;height:100%;border:0;" allowfullscreen title="{visual['description']}"></iframe></div>'''

            # Only add to map if HTML was successfully generated
            if html:
                asset_map[tag] = html
                available_tags.append(tag)
                visual_context_for_writer.append(f"{tag}: {visual['description']}")

        # Move list extensions OUTSIDE the loop to avoid infinite iteration/logic bugs
        valid_visuals.extend(process_visuals)
        valid_visuals.extend(general_visuals[:5 - len(process_visuals)])
        log(f"      ✅ Final Assets: {len(process_visuals)} Process Visuals processed.")


    
        visual['url'] = cdn_url







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
        if vid_main_url and vid_main_url.startswith("https://"):
           video_html = f'''
           <h3>Watch the Video Summary</h3>
           <div class="video-wrapper" style="position:relative;padding-bottom:56.25%;...">
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
        # --- IMAGE ENRICHMENT STAGE (The Professional Editor) ---
        try:
            log("\n--- Starting Image Enrichment Stage ---")
            article_meta = {
                "official_domain": official_domain,
                "target_keyword": target_keyword
            }
            # نمرر الـ HTML، العنوان، الميتا، والصور الرسمية
            full_body_html = image_enricher.enrich_article_html(
                full_body_html, 
                final_title, 
                article_meta, 
                direct_images=official_media_assets 
            )
            log("--- Image Enrichment Complete ---\n")
        except Exception as e:
            log(f"   ⚠️ Image enrichment process failed: {e}")
            import traceback
            traceback.print_exc()
        # --- END ENRICHMENT ---7

        # CRITICAL: استخراج الـ SEO Metadata من النتيجة النهائية للـ AI
        seo_metadata = json_c.get('seo', {})
        meta_title = seo_metadata.get('metaTitle', final_title)
        meta_description = seo_metadata.get('metaDescription', '')

        schema_data = json_c.get('schemaMarkup', {}).get('OUTPUT', None)

        # التأكد من أن العنوان الذي يتم نشره هو العنوان المُحسن للميتا
        final_publish_title = meta_title

        log(f"   🚀 [Publishing] Final Title: {final_publish_title}")
        log("   🏷️  Category Included: " + category)

        # UPDATE: نرسل عنوان المقالة والـ Category إلى الناشر
        pub_result = publisher.publish_post(final_publish_title, full_body_html, [category])
        published_url, post_id = (pub_result if isinstance(pub_result, tuple) else (pub_result, None))

        if not published_url or not post_id:
            log("   ❌ CRITICAL FAILURE: Could not publish the initial draft.")
            return False

        # ملاحظة: الميتا داتا (metaTitle/metaDescription) لا يتم إرسالها لـ Blogger API مباشرة.
        # Blogger يستخدم محتوى المقالة (title و content) فقط.
        # لهذا نحتاج إلى حقن الميتا داتا في كود الـ HTML للمقالة!

        # [NEW CRITICAL STEP]: حقن الميتا داتا في كود المقالة
        # هذا يضمن أن القارئ لا يراها، ولكن محركات البحث تراها في الـ <head>
        meta_tags_to_inject = f"""
        <!-- SEO Metadata Injection -->
        <meta name="description" content={meta_description}>
        <meta property="og:title" content={meta_title}>
        <meta property="og:description" content={meta_description}>
        """
        # [CRITICAL STEP 2]: بناء كود Schema JSON-LD
        schema_tags_to_inject = ""
        if schema_data:
            try:
                # 1. تحديث الـ Placeholders في الـ Schema
                # (يجب أن يتم هذا قبل تحويل الـ JSON إلى نص)
                article_url_final = published_url if published_url else "ARTICLE_URL_PLACEHOLDER"

                # نستخدم دالة dump مع ensure_ascii=False لضمان دعم اللغة العربية
                schema_json_string = json.dumps(schema_data, indent=2, ensure_ascii=False)

                # استبدال الـ Placeholders المتبقية (HEADLINE, IMAGE, URL)
                schema_json_string = schema_json_string.replace("HEADLINE_PLACEHOLDER", final_publish_title)
                schema_json_string = schema_json_string.replace("IMAGE_URL_PLACEHOLDER", img_url if img_url else "IMAGE_URL_PLACEHOLDER")
                schema_json_string = schema_json_string.replace("ARTICLE_URL_PLACEHOLDER", article_url_final)

                schema_tags_to_inject = f"""
                <!-- JSON-LD Schema Markup Injection -->
                <script type="application/ld+json">
                {schema_json_string}
                </script>
                """




                log("      ✅ Schema JSON-LD successfully generated.")
            except Exception as e:
                log(f"      ❌ Schema JSON-LD generation failed: {e}")

        # حقن الميتا داتا والـ Schema في بداية المحتوى
        full_body_html = meta_tags_to_inject + schema_tags_to_inject + full_body_html




        # يجب أن نُحدث المقالة التي تم نشرها للتو بهذا الـ HTML الجديد!
        if post_id:
             publisher.update_existing_post(post_id, final_publish_title, full_body_html)

        if not published_url or not post_id:
            log("   ❌ CRITICAL FAILURE: Could not publish the initial draft.")
            return False

        # ======================================================================
        # 10. QUALITY IMPROVEMENT LOOP
        # ======================================================================
        # داخل ملف main.py - ابحث عن حلقة Quality Loop وحدثها:

        # ======================================================================
        # 10. DEEP QUALITY IMPROVEMENT LOOP (The Google Ranker)
        # ======================================================================
        quality_score = 0
        attempts = 0
        MAX_RETRIES = 2

        while quality_score < 9.5 and attempts < MAX_RETRIES:
            attempts += 1
            log(f"   🔄 [Deep Quality Loop] Audit Round {attempts}...")
            
            # 1. فحص الرابط الفعلي (Actual URL Audit)
            audit_report = live_auditor.audit_live_article(published_url, target_keyword, iteration=attempts)
            if not audit_report: break

            quality_score = float(audit_report.get('quality_score', 0))
            is_ready = audit_report.get('is_page_one_ready', False)

            if quality_score >= 9.5 and is_ready:
                log(f"      ✨ Article is Page 1 Ready! Score: {quality_score}")
                break

            # 2. تنفيذ الجراحة (Remedy Surgery)
            log(f"      🚑 Score {quality_score}/10 is not enough. Launching Surgeon Agent...")
            fixed_html = remedy.fix_article_content(full_body_html, audit_report, target_keyword, combined_text, iteration=attempts)
            
            if fixed_html and len(fixed_html) > 2000:
                # تحديث المقال على بلوجر بالمحتوى المعزز بالأدلة
                if publisher.update_existing_post(post_id, title, fixed_html):
                    full_body_html = fixed_html
                    log(f"      ✅ Surgery Successful. Article updated with new evidence.")
                    time.sleep(15) # انتظار الفهرسة
                else: break
            else:
                log("      ⚠️ Surgeon failed to return improved content. Ending loop.")
                break
        
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
