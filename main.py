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
from urllib.parse import urlparse

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
import code_hunter
import image_enricher
import content_architect
import deep_dive_researcher

def is_source_viable(url, min_text_length=600):
    """Checks if a source URL is valid and has content."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.head(url, headers=headers, timeout=5, allow_redirects=True)
        if r.status_code == 404:
            return False, "404 Not Found"
        _, _, text, _, _ = scraper.resolve_and_scrape(url)
        if text and len(text) >= min_text_length:
            return True, "Valid Content"
        return False, "Content too short or empty"
    except:
        return False, "Connection Failed"

def is_url_accessible(url):
    """Checks if a URL is alive (Status 200) and allows hotlinking."""
    if not url: return False
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
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

    vid_main_id, vid_main_url = None, None
    vid_short_id = None
    local_fb_video = None
    reddit_context = ""
    chart_html_snippet = ""
    code_snippet_html = None
    
    # القائمة الرئيسية لجميع الأصول (صور + كود) التي سيتم جمعها
    all_collected_assets = [] 

    try:
        # ======================================================================
        # 0. DECODE OFFICIAL SOURCE (THE TRUTH INJECTION)
        # ======================================================================
        official_source_url = None
        if forced_keyword and "||OFFICIAL_SOURCE=" in forced_keyword:
            parts = forced_keyword.split("||OFFICIAL_SOURCE=")
            target_keyword = parts[0].strip()
            official_source_url = parts[1].replace("||", "").strip()
            log(f"   💎 OFFICIAL SOURCE INJECTED: {official_source_url}")
        else:
            target_keyword = forced_keyword

        # ======================================================================
        # 1. STRATEGY & KEYWORD SELECTION
        # ======================================================================
        if not target_keyword:
            log(f"   👉 [Strategy: Legacy Hunt] Scanning Category: {category}")
            recent_history = history_manager.get_recent_titles_string(category=category)
            try:
                seo_p = PROMPT_ZERO_SEO.format(category=category, date=datetime.date.today(), history=recent_history)
                seo_plan = api_manager.generate_step_strict(model_name, seo_p, "SEO Strategy", ["target_keyword"], use_google_search=True)
                target_keyword = seo_plan.get('target_keyword')
            except Exception as e: return False

        if not target_keyword: return False

        smart_query = ai_strategy.generate_smart_query(target_keyword)

        log("   🧠 [Strategy] Analyzing Topic Intent & Accessibility...")
        intent_prompt = PROMPT_ARTICLE_INTENT.format(target_keyword=target_keyword, category=category)
        try:
            intent_analysis = api_manager.generate_step_strict(
                model_name, intent_prompt, "Intent Analysis", ["content_type", "visual_strategy"]
            )
            content_type = intent_analysis.get("content_type", "News Analysis")
            visual_strategy = intent_analysis.get("visual_strategy", "hunt_for_screenshot")
            is_b2b = intent_analysis.get("is_enterprise_b2b", False)
            log(f"   🎯 Intent: {content_type} | B2B Mode: {is_b2b}")
            if is_b2b:
                log("      🔒 Enterprise Topic detected. Disabling Code Hunter to prevent hallucinations.")
                if content_type == "Guide": content_type = "News Analysis"
        except Exception as e:
            log(f"   ⚠️ Intent Analysis Failed: {e}. Defaulting to Safe Mode.")
            content_type = "News Analysis"
            visual_strategy = "generate_infographic"
            is_b2b = True

        # ======================================================================
        # 2. SEMANTIC GUARD (ANTI-DUPLICATION)
        # ======================================================================
        if not is_cluster_topic:
            if history_manager.check_semantic_duplication(target_keyword, category, config):
                log(f"   🚫 ABORTING PIPELINE: '{target_keyword}' is a semantic duplicate.")
                return False

        # ======================================================================
        # 3. ADVANCED DEEP DIVE & OMNI-HUNT RESEARCH (THE HARVEST)
        # ======================================================================
        log("   🕵️‍♂️ [Phase 1: Research] Initiating Deep Dive & Asset Harvest...")
        collected_sources = []
        official_domain = None

        # A. Get Sources List
        sources_to_scrape = []
        try:
            deep_dive_results = deep_dive_researcher.conduct_deep_dive(target_keyword, model_name)
            if deep_dive_results:
                sources_to_scrape.extend(deep_dive_results.get("official_sources", []))
                sources_to_scrape.extend(deep_dive_results.get("research_studies", []))
                sources_to_scrape.extend(deep_dive_results.get("personal_experiences", []))
                # Process independent critiques for E-A-T
                independent_critiques = deep_dive_results.get("independent_critiques", [])
                sources_to_scrape.extend(independent_critiques)
        except Exception as e:
            log(f"   ⚠️ Deep Dive Module Error: {e}")
            sources_to_scrape = []

        # Add Official Source URL if exists and not already in list
        if official_source_url:
             # Check if already present to avoid duplication
             if not any(s.get('url') == official_source_url for s in sources_to_scrape):
                 sources_to_scrape.insert(0, {"url": official_source_url, "page_name": "Official Source"})
             official_domain = urlparse(official_source_url).netloc

        # Fallback RSS if sources are low
        if len(sources_to_scrape) < 2:
            rss_items = news_fetcher.get_strict_rss(smart_query, category)
            for item in rss_items[:4]:
                sources_to_scrape.append({"url": item['link'], "page_name": item['title']})

        # B. SCRAPE LOOP (WITH ASSET EXTRACTION)
        processed_urls = set()
        
        for src_item in sources_to_scrape:
            url = src_item.get('url') or src_item.get('link')
            if not url or url in processed_urls: continue
            processed_urls.add(url)

            try:
                # Scraper returns 'extracted_assets' as the 5th element
                s_url, s_title, s_text, s_og_img, extracted_assets = scraper.resolve_and_scrape(url)
                
                if s_text:
                    # Identify source type for context
                    s_type = "SOURCE"
                    if official_source_url and url == official_source_url: 
                        s_type = "OFFICIAL SOURCE"
                    # Check if it was marked as a critique in the deep dive results
                    elif deep_dive_results and any(c.get('url') == url for c in deep_dive_results.get("independent_critiques", [])):
                        s_type = "INDEPENDENT CRITIQUE"
                    
                    collected_sources.append({
                        "title": s_title or src_item.get('page_name') or "Source",
                        "url": s_url,
                        "text": f"[{s_type}]\n{s_text}",
                        "domain": urllib.parse.urlparse(s_url).netloc
                    })

                    # Add extracted assets to the big pool
                    if extracted_assets:
                        log(f"      📸 Found {len(extracted_assets)} assets in {url[:30]}...")
                        all_collected_assets.extend(extracted_assets)
                    
                    # Grab Hero Image candidate from Official Source
                    if s_type == "OFFICIAL SOURCE" and s_og_img and not img_url:
                        img_url = s_og_img

            except Exception as e:
                log(f"         ⚠️ Scrape failed for {url}: {e}")

        if not collected_sources:
             log("   ❌ CRITICAL: No sources found. Aborting.")
             return False

        log(f"   ✅ Research Complete. Found {len(collected_sources)} sources.")

        # ======================================================================
        # 4. REDDIT INTEL (Additional Assets & Context)
        # ======================================================================
        try:
            reddit_context, reddit_media = reddit_manager.get_community_intel(smart_query)
            # Add Reddit media to our asset pool
            for media in reddit_media:
                all_collected_assets.append({
                    "type": "image",
                    "url": media['url'],
                    "description": media['description'],
                    "source_url": "Reddit",
                    "score": media.get('score', 5)
                })
        except: pass

        # ======================================================================
        # 4.5. NEW: COMPETITOR ANALYSIS
        # ======================================================================
        log("   🔍 [Competitor Analysis] Identifying market alternatives...")
        competitor_data = []
        try:
            comp_prompt = PROMPT_COMPETITOR_ANALYSIS.format(target_keyword=target_keyword)
            comp_result = api_manager.generate_step_strict(model_name, comp_prompt, "Competitor Analysis", ["competitors"], use_google_search=True)
            if comp_result and comp_result.get("competitors"):
                competitor_data = comp_result["competitors"]
                log(f"      ✅ Found competitors: {[c['name'] for c in competitor_data]}")
        except Exception as e:
            log(f"      ⚠️ Competitor analysis failed: {e}")

        # ======================================================================
        # 5. ASSET CURATION & PREPARATION (Before Blueprint)
        # ======================================================================
        log("   🎨 [Asset Curation] Filtering and Preparing Assets for AI...")
        
        # Deduplicate assets by URL
        unique_assets_map = {a.get('url', a.get('content')): a for a in all_collected_assets}
        unique_assets = list(unique_assets_map.values())
        
        # Prepare context list for the Architect
        # We limit to top 15 images to avoid token overflow
        visual_context_for_writer = []
        asset_map = {} # Maps ID to Asset Data
        
        # Prioritize: Hero > Code > High Score Images
        sorted_assets = sorted(unique_assets, key=lambda x: (x.get('is_hero', False), x.get('type') == 'code', x.get('score', 0)), reverse=True)
        
        valid_asset_count = 0
        valid_visuals = [] # Keep track for final assembly
        
        for asset in sorted_assets:
            if valid_asset_count >= 15: break
            
            # Check URL accessibility for images (crucial step)
            if asset['type'] == 'image':
                if not is_url_accessible(asset['url']): continue
                valid_visuals.append(asset)
                
            # Assign ID
            asset_id = f"[[ASSET_{valid_asset_count+1}]]"
            
            description = asset.get('description', '')
            if asset['type'] == 'code':
                description = f"CODE SNIPPET ({asset.get('language')}): {asset.get('content')[:100]}..."
                code_snippet_html = True # Flag that we have code
                
            visual_context_for_writer.append(f"{asset_id}: ({asset['type']}) {description}")
            
            # Store for later replacement
            asset_map[asset_id] = asset
            valid_asset_count += 1
            
        # Add generated chart if applicable
        all_text_blob_for_assets = "\n".join([s['text'] for s in collected_sources])[:20000]
        try:
            if "benchmark" in target_keyword.lower() or "vs" in target_keyword.lower() or "price" in target_keyword.lower():
                chart_prompt = f"TASK: Extract numerical data for a comparison chart from:\n{all_text_blob_for_assets}\nOUTPUT JSON: {{'chart_title': '...', 'data_points': {{'Entity1': 10, 'Entity2': 20}}}}" # Simplified prompt for brevity here
                # In real implementation use PROMPT_D_TEMPLATE or dedicated chart prompt logic
                chart_data = api_manager.generate_step_strict(model_name, chart_prompt, "Data Extraction for Chart", ["data_points"])
                
                if chart_data and chart_data.get('data_points') and len(chart_data['data_points']) >= 2:
                    chart_url = chart_generator.create_chart_from_data(chart_data['data_points'], chart_data.get('chart_title', 'Comparison'))
                    if chart_url:
                        log(f"      ✅ Chart Generated & Uploaded: {chart_url}")
                        chart_id = "[[GENERATED_CHART]]"
                        visual_context_for_writer.append(f"{chart_id}: A data visualization chart comparing key metrics.")
                        asset_map[chart_id] = {"type": "chart", "url": chart_url, "description": chart_data.get('chart_title', 'Comparison Chart')}
                        chart_html_snippet = True
        except Exception as e:
            log(f"      ⚠️ Chart Generation skipped: {e}")

        # ======================================================================
        # 6. ARCHITECT BLUEPRINT
        # ======================================================================
        log("   🧠 Assembling data bundle for The Architect...")
        
        # Combine text sources
        competitor_text = ""
        if competitor_data:
            competitor_text = "\n\n--- COMPETITOR ANALYSIS ---\n" + json.dumps(competitor_data)
            
        combined_text = "\n\n".join([s['text'][:8000] for s in collected_sources]) + competitor_text
        
        blueprint = content_architect.create_article_blueprint(
            target_keyword, content_type, combined_text, reddit_context, 
            "\n".join(visual_context_for_writer), model_name
        )

        if not blueprint or not blueprint.get("article_blueprint"):
            log("   ❌ CRITICAL FAILURE: Blueprint creation failed. Aborting pipeline.")
            return False

        # ======================================================================
        # 7. ARTISAN WRITER
        # ======================================================================
        log("   ✍️ [The Artisan] Writing the article...")
        artisan_prompt = PROMPT_B_TEMPLATE.format(
            blueprint_json=json.dumps(blueprint),
            raw_data_bundle=json.dumps({"research": combined_text[:15000], "reddit": reddit_context[:5000]})
        )
        json_b = api_manager.generate_step_strict(model_name, artisan_prompt, "Artisan Writer", ["headline", "article_body"])
        title = blueprint.get("final_title", json_b.get('headline', target_keyword))
        draft_body_html = json_b.get('article_body', '')

        # ======================================================================
        # 8. FINAL ASSEMBLY & ASSET REPLACEMENT
        # ======================================================================
        log("   🔗 Inserting Real Assets into HTML...")
        
        final_body_html = draft_body_html
        
        # Replace asset placeholders with actual HTML
        for asset_id, asset in asset_map.items():
            if asset_id not in final_body_html: continue # AI didn't use it
            
            replacement_html = ""
            if asset['type'] == 'image':
                # Upload to GitHub/ImgBB to ensure permanence
                final_img_url = image_processor.upload_external_image(asset['url'], f"asset-{target_keyword[:10]}") or asset['url']
                replacement_html = f'''
                <figure style="margin: 30px auto; text-align: center;">
                    <img src="{final_img_url}" alt="{asset['description']}" style="width: 100%; border-radius: 8px; border: 1px solid #ddd; box-shadow: 0 4px 12px rgba(0,0,0,0.08);">
                    <figcaption style="font-size: 13px; color: #555; margin-top: 8px; font-style: italic;">📸 {asset['description']}</figcaption>
                </figure>
                '''
                # Update Hero Image if not set
                if not img_url: img_url = final_img_url
                
            elif asset['type'] == 'code':
                replacement_html = f'''
                <div style="background: #f4f4f4; padding: 15px; border-radius: 5px; overflow-x: auto; margin: 20px 0;">
                    <pre><code class="language-{asset.get('language', 'text')}">{asset.get('content')}</code></pre>
                </div>
                '''
            elif asset['type'] == 'chart':
                replacement_html = f'''
                <figure style="margin: 30px auto; text-align: center;">
                    <img src="{asset['url']}" alt="{asset['description']}" style="width: 100%; border-radius: 8px; border: 1px solid #ddd; box-shadow: 0 4px 12px rgba(0,0,0,0.08);">
                    <figcaption style="font-size: 13px; color: #555; margin-top: 8px; font-style: italic;">📊 {asset['description']}</figcaption>
                </figure>
                '''
                
            final_body_html = final_body_html.replace(asset_id, replacement_html)

        # Cleanup unused placeholders
        final_body_html = re.sub(r'\[\[ASSET_\d+\]\]', '', final_body_html)

        # ======================================================================
        # 11. VIDEO PRODUCTION & UPLOAD (Moved here for flow)
        # ======================================================================
        log("   🎬 Video Production & Upload...")
        summ = re.sub('<[^<]+?>', '', draft_body_html)[:1000]
        try:
            vs_payload = api_manager.generate_step_strict(model_name, PROMPT_VIDEO_SCRIPT.format(title=title, text_summary=summ), "Video Script")
            script_json = vs_payload.get('video_script', [])

            if script_json:
                ts = int(time.time())
                main_video_path = video_renderer.VideoRenderer(output_dir="output").render_video(script_json, title, f"main_{ts}.mp4")
                if main_video_path:
                    vid_main_id, vid_main_url = youtube_manager.upload_video_to_youtube(main_video_path, title, "AI Analysis", [t.strip() for t in category.split()])
                
                short_video_path = video_renderer.VideoRenderer(output_dir="output", width=1080, height=1920).render_video(script_json, title, f"short_{ts}.mp4")
                if short_video_path:
                    local_fb_video = short_video_path
                    vid_short_id, _ = youtube_manager.upload_video_to_youtube(short_video_path, f"{title[:50]} #Shorts", "Quick Look", ["shorts", category])
        except Exception as e:
            log(f"   ⚠️ Video Production Failed: {e}")

        if vid_main_url and vid_main_url.startswith("https://"):
            video_html = f'<h3>Watch the Video Summary</h3><div class="video-wrapper" style="position:relative;padding-bottom:56.25%;"><iframe src="{vid_main_url}" style="position:absolute;top:0;left:0;width:100%;height:100%;border:0;" allowfullscreen title="{title}"></iframe></div>'
            if "[[TOC_PLACEHOLDER]]" in final_body_html:
                final_body_html = final_body_html.replace("[[TOC_PLACEHOLDER]]", "[[TOC_PLACEHOLDER]]" + video_html)
            else:
                final_body_html = video_html + final_body_html

        # ======================================================================
        # SEO POLISH & HUMANIZER
        # ======================================================================
        sources_data = [{"title": s['title'], "url": s['url']} for s in collected_sources]
        kg_links = history_manager.get_relevant_kg_for_linking(title, category)
        seo_payload = {"draft_content": {"headline": title, "article_body": final_body_html}, "sources_data": sources_data}
        json_c = api_manager.generate_step_strict(model_name, PROMPT_C_TEMPLATE.format(json_input=json.dumps(seo_payload), knowledge_graph=kg_links), "SEO Polish", ["finalTitle", "finalContent", "seo", "schemaMarkup"])

        # Fallback Image Generation
        if not img_url and json_c.get('imageGenPrompt'):
            log("   🎨 No real image found. Falling back to AI Image Generation...")
            img_url = image_processor.generate_and_upload_image(json_c['imageGenPrompt'], json_c.get('imageOverlayText', ''))

        humanizer_payload = api_manager.generate_step_strict(model_name, PROMPT_D_TEMPLATE.format(content_input=json_c['finalContent']), "Humanizer", ["finalContent"])
        final_title = json_c['finalTitle']
        full_body_html = humanizer_payload['finalContent']

        # ======================================================================
        # INJECTIONS: SCHEMA, HERO IMAGE, AUTHOR BOX
        # ======================================================================
        
        # 1. Schema Injection
        published_url_placeholder = f"https://www.latestai.me/{datetime.date.today().year}/{datetime.date.today().month:02d}/temp-slug.html"
        if json_c.get('schemaMarkup') and json_c['schemaMarkup'].get('OUTPUT'):
            log("   🧬 Injecting JSON-LD Schema into final HTML...")
            schema_data = json_c['schemaMarkup']['OUTPUT']
            schema_data['headline'] = final_title
            schema_data['datePublished'] = datetime.date.today().isoformat()
            if img_url: schema_data['image'] = img_url
            if 'mainEntityOfPage' in schema_data: schema_data['mainEntityOfPage']['@id'] = published_url_placeholder
            schema_script = f'<script type="application/ld+json">{json.dumps(schema_data, indent=2)}</script>'
            full_body_html += schema_script
        
        # 2. Hero Image Injection
        if img_url:
            img_html = f'<div class="separator" style="clear: both; text-align: center; margin-bottom: 30px;"><a href="{img_url}" style="margin-left: 1em; margin-right: 1em;"><img border="0" src="{img_url}" alt="{final_title}" style="max-width: 100%; height: auto; border-radius: 10px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);" /></a></div>'
            full_body_html = img_html + full_body_html

        # 3. Dynamic Author Box Injection
        log("   👤 Building dynamic author box...")
        author_info = config.get("author_profile", {})
        if author_info:
            author_box = f'''
            <div style="margin-top:50px; padding:30px; background:#f9f9f9; border-left: 6px solid #2ecc71; border-radius:12px; font-family:sans-serif; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">
                <div style="display:flex; align-items:flex-start; flex-wrap:wrap; gap:25px;">
                    <img src="{author_info.get('profile_image_url', '')}"
                         style="width:90px; height:90px; border-radius:50%; object-fit:cover; border:4px solid #fff; box-shadow:0 2px 8px rgba(0,0,0,0.1);" alt="{author_info.get('name', 'Author')}">
                    <div style="flex:1;">
                        <h4 style="margin:0; font-size:22px; color:#2c3e50; font-weight:800;">{author_info.get('name', '')} | Latest AI</h4>
                        <span style="font-size:12px; background:#e8f6ef; color:#2ecc71; padding:4px 10px; border-radius:6px; font-weight:bold;">{author_info.get('title', 'Tech Editor')}</span>
                        <p style="margin:15px 0; color:#555; line-height:1.7;">{author_info.get('bio', '')}</p>
                        <div style="display:flex; gap:15px; flex-wrap:wrap; margin-top:15px;">
                            <a href="{author_info.get('linkedin_url', '#')}" target="_blank" title="LinkedIn"><img src="https://cdn-icons-png.flaticon.com/512/1384/1384014.png" width="24"></a>
                            <a href="{author_info.get('twitter_url', '#')}" target="_blank" title="X (Twitter)"><img src="https://cdn-icons-png.flaticon.com/512/5969/5969020.png" width="24"></a>
                            <a href="{author_info.get('reddit_url', '#')}" target="_blank" title="Reddit"><img src="https://cdn-icons-png.flaticon.com/512/3536/3536761.png" width="24"></a>
                            <a href="https://www.latestai.me" target="_blank" title="Website"><img src="https://cdn-icons-png.flaticon.com/512/1006/1006771.png" width="24"></a>
                            <a href="https://m.youtube.com/@0latestai" target="_blank" title="YouTube"><img src="https://cdn-icons-png.flaticon.com/512/1384/1384060.png" width="24"></a>
                        </div>
                    </div>
                </div>
            </div>
            '''
            full_body_html += author_box
            
        # ======================================================================
        # 13. PUBLISH & POST-PROCESS
        # ======================================================================
        log(f"   🚀 [Publishing] Final Title: {final_title}")
        pub_result = publisher.publish_post(final_title, full_body_html, [category])
        published_url, post_id = (pub_result if isinstance(pub_result, tuple) else (pub_result, None))

        if not published_url or not post_id:
            log("   ❌ CRITICAL FAILURE: Could not publish the initial draft.")
            return False
            
        # Update schema with the final URL
        if "schema_script" in locals() and published_url_placeholder in full_body_html:
            log("   ✏️ Updating post with final URL in Schema...")
            final_html_with_schema_url = full_body_html.replace(published_url_placeholder, published_url)
            publisher.update_existing_post(post_id, final_title, final_html_with_schema_url)
            full_body_html = final_html_with_schema_url # Update for quality loop

        # QUALITY IMPROVEMENT LOOP
        quality_score, attempts, MAX_RETRIES = 0, 0, 0
        while quality_score < 9.0 and attempts < MAX_RETRIES:
            attempts += 1
            log(f"   🔄 [Deep Quality Loop] Audit Round {attempts}...")
            audit_report = live_auditor.audit_live_article(published_url, target_keyword, iteration=attempts)
            if not audit_report: break
            quality_score = float(audit_report.get('quality_score', 0))
            if quality_score >= 9.5: break
            
            fixed_html = remedy.fix_article_content(full_body_html, audit_report, target_keyword, iteration=attempts)
            if fixed_html and len(fixed_html) > 2000:
                 if publisher.update_existing_post(post_id, final_title, fixed_html):
                     full_body_html = fixed_html
                     log(f"      ✅ Surgery Successful. Article updated.")

        # FINAL DISTRIBUTION
        history_manager.update_kg(final_title, published_url, category, post_id)
        try: indexer.submit_url(published_url)
        except: pass
        
        try:
            fb_dat = api_manager.generate_step_strict(model_name, PROMPT_FACEBOOK_HOOK.format(title=final_title), "FB Hook", ["FB_Hook"])
            fb_caption = fb_dat.get('FB_Hook', final_title)
            yt_update_text = f"👇 Read the full technical analysis:\n{published_url}"
            if vid_main_id: youtube_manager.update_video_description(vid_main_id, yt_update_text)
            if vid_short_id: youtube_manager.update_video_description(vid_short_id, yt_update_text)
            if img_url: social_manager.distribute_content(fb_caption, published_url, img_url)
            if local_fb_video: social_manager.post_reel_to_facebook(local_fb_video, fb_caption, published_url)
        except Exception as e:
            log(f"   ⚠️ Social Distribution Error: {e}")

        return True

    except Exception as e:
        log(f"❌ PIPELINE CRASHED: {e}")
        traceback.print_exc()
        return False

def main():
    try:
        with open('config_advanced.json','r', encoding='utf-8') as f: 
            cfg = json.load(f)

        log("--- Starting Maintenance Phase ---")
        try:
            gardener.run_daily_maintenance(cfg)
            log("--- Maintenance Phase Complete ---")
        except Exception as e:
            log(f"   ⚠️ Gardener maintenance run failed: {e}")

        cats = list(cfg['categories'].keys())
        random.shuffle(cats)
        published_today = False

        for cat in cats:
            if published_today: break
            log(f"\n📂 CATEGORY: {cat}")
            try:
                topic, is_c = cluster_manager.get_strategic_topic(cat, cfg)
                if topic:
                    if run_pipeline(cat, cfg, forced_keyword=topic, is_cluster_topic=is_c):
                        published_today = True
                        continue
                    else:
                        cluster_manager.mark_topic_failed(topic)
            except Exception as e:
                log(f"   ⚠️ Cluster Strategy Error: {e}")
                traceback.print_exc()
            
            if not published_today:
                fresh_trends = trend_watcher.get_verified_trend(cat, cfg)
                if fresh_trends:
                    for trend in fresh_trends:
                        if published_today: break
                        if history_manager.check_semantic_duplication(trend, cat, cfg):
                            log(f"      ⏭️ Skipping duplicate trend: '{trend}'")
                            continue
                        is_valid, official_url, verified_title = truth_verifier.verify_topic_existence(trend, cfg['settings']['model_name'])
                        if is_valid:
                            log(f"      ✅ Trend Verified: {verified_title}")
                            forced_tag = f"{verified_title} ||OFFICIAL_SOURCE={official_url}||"
                            if run_pipeline(cat, cfg, forced_keyword=forced_tag, is_cluster_topic=False):
                                published_today = True
                        else:
                            log(f"      ⛔ Trend Rejected (No Official Source): {trend}")
            
            if not published_today and cfg['categories'][cat].get('trending_focus'):
                raw_topics = [t.strip() for t in cfg['categories'][cat]['trending_focus'].split(',')]
                random.shuffle(raw_topics)
                log(f"   📜 Checking {len(raw_topics)} manual focus topics...")
                for potential_topic in raw_topics:
                    if published_today: break
                    if history_manager.check_semantic_duplication(potential_topic, cat, cfg):
                        log(f"      ⏭️ Skipping duplicate: '{potential_topic}'")
                        continue
                    log(f"      🚀 Attempting manual topic: {potential_topic}")
                    if run_pipeline(cat, cfg, forced_keyword=potential_topic, is_cluster_topic=False):
                        published_today = True

        if published_today:
            log("\n✅ MISSION COMPLETE: New content published successfully.")
        else:
            log("\n❌ MISSION FAILED: No fresh, verified topics found today.")
    except Exception as e:
        log(f"❌ CRITICAL MAIN ERROR: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
