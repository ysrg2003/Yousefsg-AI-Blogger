# FILE: main.py
# ROLE: Orchestrator V9.3 (The Unstoppable Research Engine)
# DESCRIPTION: The complete, final, and stable version integrating all modules and fixes.
#              Features a multi-layered, intelligent research strategy that guarantees
#              source acquisition or gracefully aborts, enforcing a strict 3-source quality rule.
#              UPDATES: Contextual Visual Injection, Timeline Paradox Fix, Variable Name Corrections.

import os
import json
import time
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

def run_pipeline(category, config, forced_keyword=None, is_cluster_topic=False):
    
    # ======================================================================
    # ### NEW: CENTRALIZED SMART QUERY GENERATION ###
    # ======================================================================

            

    
    """
    Executes the full content lifecycle using a robust, multi-layered Gemini-powered strategy.
    """
    model_name = config['settings'].get('model_name', "gemini-2.5-flash") # Use a powerful model for writing
    
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
        except: visual_strategy = "generate_comparison_table"

        
        
        # ======================================================================
        # 4. OMNI-HUNT (HYBRID: STRICT PRIMARY -> LEGACY FALLBACK)
        # ======================================================================
        log("   🕵️‍♂️ Starting Omni-Hunt (Strict Primary -> Legacy Fallback)...")
        collected_sources = []
        
        # --- [A] PRIMARY MECHANISM: STRICT GOOGLE NEWS RESOLVER ---
        try:
            log("   🚀 Executing Primary Mechanism (Strict RSS + Selenium Resolver)...")
            
            # استدعاء دالة البحث الصارمة الجديدة من news_fetcher
            rss_items = news_fetcher.get_strict_rss(smart_query, category)
            
            if rss_items:
                # قائمة الكلمات المملة (كما وردت في الكود الصارم)
                BORING_KEYWORDS_STRICT = [
                    "CFO", "CEO", "Quarterly", "Earnings", "Report", "Market Cap", 
                    "Dividend", "Shareholders", "Acquisition", "Merger", "Appointment", 
                    "Executive", "Knorex", "Partner", "Agreement", "B2B", "Enterprise"
                ]
                
                recent_titles = history_manager.get_recent_titles_string() # لتجنب التكرار

                for item in rss_items[:6]: # المرحلة 5: التكرار
                    if len(collected_sources) >= 3: break
                    
                    if item['title'][:20] in recent_titles: continue
                    
                    # الفلتر الصارم
                    if any(b_word.lower() in item['title'].lower() for b_word in BORING_KEYWORDS_STRICT):
                        log(f"         ⛔ Skipped Boring Corporate Topic: {item['title']}")
                        continue
                    
                    if any(src.get('url') == item['link'] for src in collected_sources): continue

                    log(f"      📌 Checking Source: {item['title'][:40]}...")
                    
                    # المرحلة 6: فك الرابط باستخدام url_resolver
                    data = url_resolver.get_page_html(item['link'])
                    
                    if data and data.get('html'):
                        r_url = data['url']
                        html_content = data['html']
                        
                        # استخراج النص
                        text = trafilatura.extract(html_content, include_comments=False, include_tables=True)
                        
                        # Fallback للاستخراج
                        if not text:
                            soup = BeautifulSoup(html_content, 'html.parser')
                            for script in soup(["script", "style", "nav", "footer"]): script.extract()
                            text = soup.get_text(" ", strip=True)

                        if text and len(text) >= 800:
                            log(f"         ✅ Accepted Source! ({len(text)} chars).")
                            domain = urllib.parse.urlparse(r_url).netloc
                            
                            # محاولة استخراج صورة من الميتا (إضافة لتحسين التجربة)
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
                                "media": [] # سيتم ملؤها لاحقاً إذا احتجنا
                            })
                        else:
                            log("         ⚠️ Content too short or extraction failed.")
                    else:
                        log("         ⚠️ Selenium failed to resolve URL.")
                    
                    time.sleep(2) # راحة

        except Exception as e:
            log(f"   ⚠️ Primary Mechanism Error: {e}")

        # --- [B] FALLBACK MECHANISM: LEGACY OMNI-HUNT ---
        # يعمل فقط إذا فشل النظام الأساسي في جمع 3 مصادر
        if len(collected_sources) < 3:
            log(f"   ⚠️ Primary yielded {len(collected_sources)}/3 sources. Activating Legacy Fallback...")
            
            # Layer 1: AI Smart Search (Legacy)
            try:
                ai_results = ai_researcher.smart_hunt(target_keyword, config, mode="general")
                if ai_results:
                    vetted = news_fetcher.ai_vet_sources(ai_results, model_name)
                    for item in vetted:
                        if len(collected_sources) >= 3: break
                        # تخطي ما تم جمعه بالفعل
                        if any(s['url'] == item['link'] for s in collected_sources): continue
                        
                        f_url, f_title, text, f_image, media = scraper.resolve_and_scrape(item['link'])
                        if text: collected_sources.append({"title": f_title or item['title'], "url": f_url, "text": text, "source_image": f_image, "domain": urllib.parse.urlparse(f_url).netloc, "media": media})
            except Exception as e: log(f"      ⚠️ Legacy AI Search Error: {e}")

            # Layer 2: Legacy RSS (Original get_real_news_rss)
            if len(collected_sources) < 3:
                try:
                    # نستخدم الدالة القديمة (تأكد من وجودها في news_fetcher)
                    legacy_items = news_fetcher.get_real_news_rss(target_keyword, category) 
                    for item in legacy_items:
                        if len(collected_sources) >= 3: break
                        if any(s['url'] == item['link'] for s in collected_sources): continue
                        
                        f_url, f_title, text, f_image, media = scraper.resolve_and_scrape(item['link'])
                        if text: collected_sources.append({"title": f_title or item['title'], "url": f_url, "text": text, "source_image": f_image, "domain": urllib.parse.urlparse(f_url).netloc, "media": media})
                except Exception as e: log(f"      ⚠️ Legacy RSS Error: {e}")

        # --- FINAL CHECK ---
        if len(collected_sources) < 3:
            log(f"   ❌ CRITICAL FAILURE: Found only {len(collected_sources)}/3 required sources. Aborting.")
            return False
        
        log(f"   ✅ Research Complete. Found {len(collected_sources)} sources.")

        
        # ======================================================================
        # 5. VISUAL HUNT & REDDIT INTEL
        # ======================================================================
        official_media, reddit_media = [], []
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
        # We use the new "Detective" prompt with web search enabled
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
            # Convert the AI's findings into the same format as our other media
            for evidence in evidence_payload["visual_evidence"]:
                # Map AI output type to our internal type
                evidence_type = "image" # Default
                if "video" in evidence.get("type", ""):
                    evidence_type = "embed"
                elif "gif" in evidence.get("type", ""):
                    evidence_type = "gif"

                ai_found_evidence.append({
                    "type": evidence_type,
                    "url": evidence["url"],
                    "description": evidence["description"],
                    "score": 10  # Give high priority to AI-verified evidence
                })
        else:
            log("      ⚠️ AI Detective did not find any new evidence.")

    except Exception as e:
        log(f"      ❌ Visual Augmentation step failed: {e}")
        # ======================================================================
        # 6. SYNTHESIS, VIDEO PRODUCTION, AND REAL EVIDENCE INJECTION
        # ======================================================================
        log("   ✍️ Synthesizing Content & Preparing Visual Assets...")
        
        # --- [NEW] REAL EVIDENCE FILTERING & PREPARATION ---

        all_media = []
        for s in collected_sources:
            if s.get('media'): all_media.extend(s['media'])
        if official_media: all_media.extend(official_media)
        if reddit_media: all_media.extend(reddit_media)
        if ai_found_evidence: all_media.extend(ai_found_evidence) # <-- السطر الجديد والمهم
                
        # Deduplicate and select the best 3-5 pieces of evidence
        unique_media = list({m['url']: m for m in all_media}.values())
        # Sort by score (if available) to prioritize better visuals
        unique_media = sorted(unique_media, key=lambda x: x.get('score', 0), reverse=True)
        best_visuals = unique_media[:5] # Take the top 5 visuals

        asset_map = {}
        available_tags = []
        visual_context_for_writer = [] # Descriptions for the AI writer

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
        combined_text = "\n".join([f"SOURCE: {s['url']}\n{s['text'][:8000]}" for s in collected_sources]) + reddit_context
        
        payload = {
            "keyword": target_keyword, 
            "research_data": combined_text, 
            "AVAILABLE_VISUAL_TAGS": available_tags, # Pass the tags to AI
            "VISUAL_DESCRIPTIONS": "\n".join(visual_context_for_writer), # Give AI context about visuals
            "TODAY_DATE": str(datetime.date.today())
        }
        
        # We call the new V2 prompt now
        json_b = api_manager.generate_step_strict(model_name, PROMPT_B_TEMPLATE.format(json_input=json.dumps(payload), forbidden_phrases="[]"), "Writer", ["headline", "article_body"])
        
        title = json_b['headline']
        draft_body_html = json_b['article_body']

        # --- VIDEO PRODUCTION & UPLOAD ---
        log("   🎬 Video Production & Upload...")
        vid_main_id, vid_main_url, vid_short_id, local_fb_video = None, None, None, None
        
        summ = re.sub('<[^<]+?>', '', draft_body_html)[:1000]
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

        # ======================================================================
        # 7. FINAL ASSEMBLY & PUBLISHING
        # ======================================================================
        log("   🔗 Assembling Final HTML with All Assets...")

        final_body_html = draft_body_html

        # [CRITICAL FIX] Inject the main YouTube video IFRAME directly into the HTML
        if vid_main_url:
            video_html = f'''
            <h3>Watch the Video Summary</h3>
            <div class="video-wrapper" style="position:relative;padding-bottom:56.25%;height:0;overflow:hidden;margin:30px 0;border-radius:12px;box-shadow:0 4px 15px rgba(0,0,0,0.1);">
            <iframe src="{vid_main_url}" style="position:absolute;top:0;left:0;width:100%;height:100%;border:0;" allowfullscreen title="{title}"></iframe>
            </div>'''
            # Inject video after the table of contents
            if "[[TOC_PLACEHOLDER]]" in final_body_html:
                 final_body_html = final_body_html.replace("[[TOC_PLACEHOLDER]]", "[[TOC_PLACEHOLDER]]" + video_html)
            else:
                 final_body_html = video_html + final_body_html # Fallback if TOC is missing

        # Inject the REAL visual evidence found earlier
        for tag, html_code in asset_map.items():
            final_body_html = final_body_html.replace(tag, html_code)

        # SEO Polish Stage (Now happens on a much richer draft)
        sources_data = [{"title": s['title'], "url": s['url']} for s in collected_sources if s.get('url')]
        kg_links = history_manager.get_relevant_kg_for_linking(title, category)
        
        # We re-use json_c structure but with our assembled content
        seo_payload = {"draft_content": {"headline": title, "article_body": final_body_html}, "sources_data": sources_data}
        json_c = api_manager.generate_step_strict(
            model_name, 
            PROMPT_C_TEMPLATE.format(json_input=json.dumps(seo_payload), knowledge_graph=kg_links), "SEO Polish", ["finalTitle", "finalContent", "seo", "schemaMarkup"]
        )

        # Humanizer Stage
        humanizer_payload = api_manager.generate_step_strict(model_name, PROMPT_D_TEMPLATE.format(content_input=json_c['finalContent']),"Humanizer", ["finalContent"])
        
        final_title = json_c['finalTitle']
        full_body_html = humanizer_payload['finalContent']

    
        
        log("   🚀 [Publishing] Initial Draft...")
        pub_result = publisher.publish_post(title, full_body_html, [category])
        published_url, post_id = (pub_result if isinstance(pub_result, tuple) else (pub_result, None))

        if not published_url or not post_id:
            log("   ❌ CRITICAL FAILURE: Could not publish the initial draft.")
            return False

        # ======================================================================
        # 7.5 QUALITY IMPROVEMENT LOOP (AUDIT -> REMEDY -> UPDATE)
        # ======================================================================
        quality_score, attempts, MAX_RETRIES = 0, 0, 0
        
        while quality_score < 9.5 and attempts < MAX_RETRIES:
            attempts += 1
            log(f"   🔄 [Quality Loop] Audit Round {attempts}...")
            
            # 1. Auditor visits the LIVE URL
            audit_report = live_auditor.audit_live_article(published_url, target_keyword, iteration=attempts)
            
            if not audit_report:
                log("      ⚠️ Quality Audit failed to return a report. Skipping loop.")
                break
            
            quality_score = float(audit_report.get('quality_score', 0))
            
            if quality_score >= 9.5:
                log(f"      🌟 Excellence Achieved! Score: {quality_score}/10. No further fixes needed.")
                break
            
            log(f"      ⚠️ Score {quality_score}/10. Auditor found issues. Starting surgery...")
            
            # 2. Remedy Agent fixes the content
            fixed_html = remedy.fix_article_content(
                full_body_html, 
                audit_report, 
                target_keyword, 
                combined_text, 
                iteration=attempts
            )
            
            # 3. Update on Blogger
            if fixed_html and len(fixed_html) > 1000:
                if publisher.update_existing_post(post_id, title, fixed_html):
                    full_body_html = fixed_html
                    log(f"      ✅ Article updated on Blogger. Waiting for sync...")
                    time.sleep(10) 
                else:
                    log("      ❌ Failed to update the post on Blogger. Breaking loop.")
                    break
            else:
                log("      ⚠️ Remedy agent failed to produce a valid fix. Breaking loop.")
                break

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
            
            # Use IDs for updating description (Fixed Variable Name Bug)
            if vid_main_id: youtube_manager.update_video_description(vid_main_id, yt_update_text)
            if vid_short_id: youtube_manager.update_video_description(vid_short_id, yt_update_text)
            
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
