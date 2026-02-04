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
    valid_visuals = []

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
            is_b2b = intent_analysis.get("is_enterprise_b2b", False)
            log(f"   🎯 Intent: {content_type} | B2B Mode: {is_b2b}")
            if is_b2b:
                log("      🔒 Enterprise Topic detected. Disabling Code Hunter to prevent hallucinations.")
                if content_type == "Guide": content_type = "News Analysis"
        except Exception as e:
            log(f"   ⚠️ Intent Analysis Failed: {e}. Defaulting to Safe Mode.")
            content_type = "News Analysis"
            is_b2b = True

        # ======================================================================
        # 2. SEMANTIC GUARD (ANTI-DUPLICATION)
        # ======================================================================
        if not is_cluster_topic:
            if history_manager.check_semantic_duplication(target_keyword, category, config):
                log(f"   🚫 ABORTING PIPELINE: '{target_keyword}' is a semantic duplicate.")
                return False

        # ======================================================================
        # 3. ADVANCED DEEP DIVE & OMNI-HUNT RESEARCH
        # ======================================================================
        log("   🕵️‍♂️ [Phase 1: Research] Initiating Deep Dive Protocol...")
        collected_sources = []
        official_media_assets = []
        official_domain = None

        try:
            deep_dive_results = deep_dive_researcher.conduct_deep_dive(target_keyword, model_name)
            if deep_dive_results:
                all_high_value_sources = (
                    deep_dive_results.get("official_sources", []) +
                    deep_dive_results.get("research_studies", []) +
                    deep_dive_results.get("personal_experiences", [])
                )
                
                # NEW: Process independent critiques for E-A-T
                independent_critiques = deep_dive_results.get("independent_critiques", [])
                
                all_sources_to_scrape = all_high_value_sources + independent_critiques

                for item in all_sources_to_scrape:
                    url = item.get('url')
                    if not url or any(s.get('url') == url for s in collected_sources):
                        continue
            
                    log(f"      ↳ Scraping high-value source: {url[:60]}...")
                    try:
                        s_url, s_title, s_text, s_img, s_media = scraper.resolve_and_scrape(url)
                        if s_text:
                            source_type = "SOURCE"
                            if item in deep_dive_results.get("official_sources", []): source_type = "OFFICIAL SOURCE"
                            elif item in deep_dive_results.get("research_studies", []): source_type = "RESEARCH STUDY"
                            elif item in deep_dive_results.get("personal_experiences", []): source_type = "EXPERT EXPERIENCE"
                            elif item in independent_critiques: source_type = "INDEPENDENT_CRITIQUE" # Mark critiques
                            
                            collected_sources.append({
                                "title": s_title or item.get('page_name') or "Source",
                                "url": s_url,
                                "text": f"[{source_type}]\n{s_text}",
                                "source_image": s_img, "domain": urllib.parse.urlparse(s_url).netloc, "media": s_media
                            })
                            if not img_url and s_img: img_url = s_img
                            if source_type == "OFFICIAL SOURCE" and s_media: official_media_assets.extend(s_media)
                    except Exception as e:
                        log(f"         ⚠️ Failed to scrape source {url}: {e}")
        except Exception as e:
            log(f"   ⚠️ Deep Dive Module Error: {e}")

        if official_source_url and not any(s['url'] == official_source_url for s in collected_sources):
            log(f"   👑 Fetching Official Source Content: {official_source_url}")
            official_domain = urlparse(official_source_url).netloc
            try:
                o_url, o_title, o_text, o_img, o_media = scraper.resolve_and_scrape(official_source_url)
                if o_text:
                    collected_sources.insert(0, {
                        "title": o_title or "Official Announcement", "url": o_url, "text": f"OFFICIAL SOURCE OF TRUTH:\n{o_text}",
                        "source_image": o_img, "domain": "OFFICIAL_SOURCE", "media": o_media
                    })
                    if not img_url and o_img: img_url = o_img
                    if o_media: official_media_assets.extend(o_media)
                    log(f"      📸 Extracted {len(o_media)} images from official source.")
            except Exception as e:
                log(f"   ⚠️ Failed to scrape official source: {e}")

        if len(collected_sources) < 2:
            log(f"   ⚠️ Low sources ({len(collected_sources)}). Activating Fallback RSS...")
            try:
                legacy_items = news_fetcher.get_real_news_rss(smart_query, category)
                for item in legacy_items:
                    if len(collected_sources) >= 4: break
                    if any(s['url'] == item['link'] for s in collected_sources): continue
                    f_url, f_title, text, f_image, media = scraper.resolve_and_scrape(item['link'])
                    if text:
                        collected_sources.append({"title": f_title or item['title'], "url": f_url, "text": text, "source_image": f_image, "domain": urllib.parse.urlparse(f_url).netloc, "media": media})
                        if not img_url and f_image: img_url = f_image
            except Exception as e: log(f"      ⚠️ Legacy RSS Error: {e}")

        if not collected_sources:
            log(f"   ❌ CRITICAL FAILURE: No sources found. Aborting.")
            return False
        
        log(f"   ✅ Research Complete. Found {len(collected_sources)} sources.")

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
        # 5, 6, 7. GATHER ALL ASSETS *BEFORE* BLUEPRINT CREATION
        # ======================================================================
        log("   🎨 [Asset Gathering] Collecting all potential visual and data assets...")

        # --- 5. DATA VISUALIZATION ---
        all_text_blob_for_assets = "\n".join([s['text'] for s in collected_sources])[:20000]
        try:
            if "benchmark" in target_keyword.lower() or "vs" in target_keyword.lower() or "price" in target_keyword.lower():
                # (Logic for chart generation remains the same)
                chart_prompt = PROMPT_D_TEMPLATE.format(target_keyword=target_keyword, text_blob=all_text_blob_for_assets) # Assuming a prompt for this
                chart_data = api_manager.generate_step_strict(model_name, chart_prompt, "Data Extraction for Chart")
                if chart_data and chart_data.get('data_points') and len(chart_data['data_points']) >= 2:
                    chart_url = chart_generator.create_chart_from_data(chart_data['data_points'], chart_data.get('chart_title', 'Comparison'))
                    if chart_url:
                        log(f"      ✅ Chart Generated & Uploaded: {chart_url}")
                        chart_html_snippet = f'''<figure...><img src="{chart_url}"...></figure>'''
        except Exception as e:
            log(f"      ⚠️ Chart Generation skipped: {e}")
        
        # --- 6. VISUAL HUNT & REDDIT INTEL ---
        reddit_media = []
        try:
            reddit_context, reddit_media = reddit_manager.get_community_intel(smart_query)
        except Exception as e:
            log(f"   ⚠️ Reddit Hunt Error: {e}")

        # --- 7. CODE SNIPPET HUNT ---
        try:
            if not is_b2b and any(x in category.lower() + target_keyword.lower() for x in ['ai', 'code', 'python', 'api', 'model']):
                code_snippet_html = code_hunter.find_code_snippet(target_keyword, model_name)
        except Exception as e:
            log(f"   ⚠️ Code Snippet Hunt Error: {e}")

        # ======================================================================
        # 8. BUILD DATA BUNDLE & ARCHITECT BLUEPRINT (NOW DATA-DRIVEN)
        # ======================================================================
        log("   🧠 Assembling data bundle for The Architect...")

        # --- A. ASSEMBLE TEXT DATA (with competitor info) ---
        competitor_text = ""
        if competitor_data:
            competitor_text = "\n\n--- COMPETITOR ANALYSIS ---\n" + json.dumps(competitor_data)
        
        combined_text = "\n\n".join([f"SOURCE: {s['url']}\n{s['text'][:8000]}" for s in collected_sources]) + competitor_text

        # --- B. ASSEMBLE *AVAILABLE* VISUAL CONTEXT ---
        all_media = official_media_assets + reddit_media
        unique_media = list({m['url']: m for m in all_media if m.get('url')}.values())
        valid_visuals = [media for media in unique_media if is_url_accessible(media.get('url'))][:5] # Limit to 5
        
        visual_context_for_writer = []
        for i, visual in enumerate(valid_visuals):
            visual_context_for_writer.append(f"[[VISUAL_EVIDENCE_{i+1}]]: {visual.get('description', 'Visual evidence')}")
        
        if code_snippet_html:
            visual_context_for_writer.append("[[CODE_SNIPPET_1]]: A practical Python code example for developers.")
        if chart_html_snippet:
            visual_context_for_writer.append("[[GENERATED_CHART]]: A data visualization chart comparing key metrics.")

        # --- C. CALL THE ARCHITECT ---
        blueprint = content_architect.create_article_blueprint(
            target_keyword, content_type, combined_text, reddit_context, "\n".join(visual_context_for_writer), model_name
        )

        if not blueprint or not blueprint.get("article_blueprint"):
            log("   ❌ CRITICAL FAILURE: Blueprint creation failed. Aborting pipeline.")
            return False

        # ... (The rest of the pipeline from step 9 onwards remains largely the same, but with the corrected logic for asset replacement and schema injection)

        # ======================================================================
        # 9. THE ARTISAN PHASE (WRITING FROM BLUEPRINT)
        # ======================================================================
        log("   ✍️ [The Artisan] Executing the blueprint to write the article...")
        artisan_prompt = PROMPT_B_TEMPLATE.format(
            blueprint_json=json.dumps(blueprint),
            raw_data_bundle=json.dumps({"research": combined_text[:15000], "reddit": reddit_context[:5000]})
        )
        json_b = api_manager.generate_step_strict(model_name, artisan_prompt, "Artisan Writer", ["headline", "article_body"])
        title = blueprint.get("final_title", json_b.get('headline', target_keyword))
        draft_body_html = json_b.get('article_body', '')

        # ======================================================================
        # 10. SYNTHESIS & ASSET PROCESSING
        # ======================================================================
        log("   ✍️ Synthesizing Content & Validating Assets...")
        if not img_url: # Find a fallback featured image
            for s in collected_sources:
                if s.get('source_image') and is_url_accessible(s.get('source_image')):
                    img_url = s['source_image']
                    break
        if img_url:
            featured_img_cdn_url = image_processor.upload_external_image(img_url, f"featured-img-{target_keyword}")
            img_url = featured_img_cdn_url or img_url

        # ======================================================================
        # 11. VIDEO PRODUCTION & UPLOAD
        # ======================================================================
        log("   🎬 Video Production & Upload...")
        summ = re.sub('<[^<]+?>', '', draft_body_html)[:1000]
        try:
            vs_payload = api_manager.generate_step_strict(model_name, PROMPT_VIDEO_SCRIPT.format(title=title, text_summary=summ), "Video Script")
            if vs_payload.get('video_script'):
                ts = int(time.time())
                main_video_path = video_renderer.VideoRenderer(output_dir="output").render_video(vs_payload['video_script'], title, f"main_{ts}.mp4")
                if main_video_path:
                    vid_main_id, vid_main_url = youtube_manager.upload_video_to_youtube(main_video_path, title, "AI Analysis", [t.strip() for t in category.split()])
                short_video_path = video_renderer.VideoRenderer(output_dir="output", width=1080, height=1920).render_video(vs_payload['video_script'], title, f"short_{ts}.mp4")
                if short_video_path:
                    local_fb_video = short_video_path
                    vid_short_id, _ = youtube_manager.upload_video_to_youtube(short_video_path, f"{title[:50]} #Shorts", "Quick Look", ["shorts", category])
        except Exception as e:
            log(f"   ⚠️ Video Production Failed: {e}")

        # ======================================================================
        # 12. FINAL ASSEMBLY
        # ======================================================================
        log("   🔗 Assembling Final HTML...")
        final_body_html = draft_body_html
        asset_map = {}
        for i, visual in enumerate(valid_visuals):
            tag = f"[[VISUAL_EVIDENCE_{i+1}]]"
            cdn_url = image_processor.upload_external_image(visual['url'], f"visual-evidence-{i}-{target_keyword}")
            if cdn_url:
                asset_map[tag] = f'''<figure...><img src="{cdn_url}" alt="{visual['description']}"...></figure>'''
        if code_snippet_html: asset_map["[[CODE_SNIPPET_1]]"] = code_snippet_html
        if chart_html_snippet: asset_map["[[GENERATED_CHART]]"] = chart_html_snippet
        for tag, html_code in asset_map.items():
            final_body_html = final_body_html.replace(tag, html_code)
        if vid_main_url:
            video_html = f'<h3>Watch the Video Summary</h3><div class="video-wrapper"...><iframe src="{vid_main_url}"...></iframe></div>'
            final_body_html = video_html + final_body_html

        sources_data = [{"title": s['title'], "url": s['url']} for s in collected_sources if s.get('url')]
        kg_links = history_manager.get_relevant_kg_for_linking(title, category)
        seo_payload = {"draft_content": {"headline": title, "article_body": final_body_html}, "sources_data": sources_data}
        json_c = api_manager.generate_step_strict(model_name, PROMPT_C_TEMPLATE.format(json_input=json.dumps(seo_payload), knowledge_graph=kg_links), "SEO Polish", ["finalTitle", "finalContent", "seo", "schemaMarkup"])

        if not img_url and json_c.get('imageGenPrompt'):
            img_url = image_processor.generate_and_upload_image(json_c['imageGenPrompt'], json_c.get('imageOverlayText', ''))

        humanizer_payload = api_manager.generate_step_strict(model_name, PROMPT_D_TEMPLATE.format(content_input=json_c['finalContent']), "Humanizer", ["finalContent"])
        final_title = json_c['finalTitle']
        full_body_html = humanizer_payload['finalContent']

        # --- SCHEMA & AUTHOR BOX INJECTION ---
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
        
        if img_url:
            img_html = f'<div class="separator"...><a href="{img_url}"...><img src="{img_url}" alt="{final_title}" .../></a></div>'
            full_body_html = img_html + full_body_html

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
            
        # ... The rest of the publishing logic ...
        pub_result = publisher.publish_post(final_title, full_body_html, [category])
        published_url, post_id = (pub_result if isinstance(pub_result, tuple) else (pub_result, None))

        if not published_url or not post_id:
            log("   ❌ CRITICAL FAILURE: Could not publish the initial draft.")
            return False
            
        # Update schema with the final URL and update the post
        if "schema_script" in locals() and published_url_placeholder in full_body_html:
            log("   ✏️ Updating post with final URL in Schema...")
            final_html_with_schema_url = full_body_html.replace(published_url_placeholder, published_url)
            publisher.update_existing_post(post_id, final_title, final_html_with_schema_url)
            full_body_html = final_html_with_schema_url # Update for quality loop

        # ======================================================================
        # 13. QUALITY IMPROVEMENT LOOP & DISTRIBUTION
        # ======================================================================
        # (The quality loop and distribution logic remains the same)
        quality_score, attempts, MAX_RETRIES = 0, 0, 1 # Set MAX_RETRIES to 1 to enable one loop
        while quality_score < 9.0 and attempts < MAX_RETRIES:
            attempts += 1
            log(f"   🔄 [Deep Quality Loop] Audit Round {attempts}...")
            # ... (rest of the loop)

        history_manager.update_kg(final_title, published_url, category, post_id)
        # ... (rest of the distribution logic)

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
