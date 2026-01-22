import os
import json
import time
import requests
import re
import random
import sys
import datetime
import urllib.parse
import feedparser
from bs4 import BeautifulSoup  # New requirement: BeautifulSoup for scraping
import social_manager
import video_renderer
import youtube_manager
from google import genai
from google.genai import types

# ==============================================================================
# 0. CONFIG & LOGGING
# ==============================================================================

# Words that indicate AI patterns (Stricter list)
FORBIDDEN_PHRASES = [
    "In today's digital age",
    "The world of AI is ever-evolving",
    "unveils",
    "unveiled",
    "poised to",
    "delve into",
    "game-changer",
    "paradigm shift",
    "tapestry",
    "robust",
    "leverage",
    "underscore",
    "testament to",
    "beacon of",
    "In conclusion",
    "Remember that",
    "It is important to note",
    "Imagine a world",
    "fast-paced world",
    "cutting-edge",
    "realm of"
]

def log(msg):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)

# ==============================================================================
# 1. CSS STYLING (Complete)
# ==============================================================================
ARTICLE_STYLE = """
<style>
    /* Global Typography */
    .post-body { font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.85; color: #2c3e50; font-size: 19px; }
    h2 { color: #111; font-weight: 800; margin-top: 50px; margin-bottom: 20px; border-bottom: 4px solid #f1c40f; padding-bottom: 5px; display: inline-block; font-size: 28px; }
    h3 { color: #2980b9; font-weight: 700; margin-top: 35px; font-size: 24px; }
    
    /* Table of Contents */
    .toc-box { background: #fdfdfd; border: 1px solid #e1e4e8; padding: 25px; margin: 30px 0; border-radius: 12px; display: inline-block; min-width: 60%; box-shadow: 0 4px 10px rgba(0,0,0,0.05); }
    .toc-box h3 { margin-top: 0; font-size: 20px; border-bottom: 2px solid #3498db; padding-bottom: 8px; display: inline-block; margin-bottom: 15px; color: #222; }
    .toc-box ul { list-style: none; padding: 0; margin: 0; }
    .toc-box li { margin-bottom: 10px; border-bottom: 1px dashed #eee; padding-bottom: 5px; padding-left: 20px; position: relative; }
    .toc-box li:before { content: "►"; color: #3498db; position: absolute; left: 0; font-size: 12px; top: 4px; }
    .toc-box a { color: #444; font-weight: 600; font-size: 17px; text-decoration: none; transition: 0.2s; }
    .toc-box a:hover { color: #3498db; padding-left: 5px; }

    /* Tables */
    .table-wrapper { overflow-x: auto; margin: 35px 0; border-radius: 12px; box-shadow: 0 0 15px rgba(0,0,0,0.1); border: 1px solid #eee; }
    table { width: 100%; border-collapse: collapse; background: #fff; min-width: 600px; }
    th { background: #2c3e50; color: #fff; padding: 15px; text-align: left; }
    td { padding: 14px 16px; border-bottom: 1px solid #eee; color: #34495e; }
    tr:nth-child(even) { background-color: #f8f9fa; }

    /* Key Takeaways */
    .takeaways-box { background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%); border-left: 6px solid #2c3e50; padding: 25px; margin: 35px 0; border-radius: 8px; }
    .takeaways-box h3 { margin-top: 0; color: #222; font-size: 22px; margin-bottom: 15px; }
    .takeaways-box ul { margin: 0; padding-left: 20px; }
    .takeaways-box li { margin-bottom: 10px; font-weight: 500; font-size: 18px; }

    /* FAQ */
    .faq-section { margin-top: 60px; border-top: 2px solid #ecf0f1; padding-top: 40px; background: #fffbf2; padding: 30px; border-radius: 10px; }
    .faq-title { font-size: 26px; font-weight: 800; color: #2c3e50; margin-bottom: 25px; text-align: center; }
    .faq-q { font-weight: 700; font-size: 20px; color: #d35400; margin-bottom: 8px; display: block; }
    .faq-a { font-size: 18px; color: #555; line-height: 1.8; }

    /* Other */
    .separator img { border-radius: 10px; box-shadow: 0 10px 30px rgba(0,0,0,0.15); max-width: 100%; height: auto; display: block; }
    blockquote { background: #fff; border-left: 5px solid #ffb703; margin: 35px 0; padding: 20px 35px; font-style: italic; color: #555; font-size: 1.2em; line-height: 1.6; }
    a { color: #2980b9; text-decoration: none; font-weight: 500; border-bottom: 2px dotted #2980b9; transition: 0.3s; }
    a:hover { color: #e67e22; border-bottom: 1px solid #e67e22; }
</style>
"""

# ==============================================================================
# 2. PROMPTS DEFINITIONS
# ==============================================================================

# 🛑🛑🛑 [AREA FOR MANUAL PROMPTS] 🛑🛑🛑
# Paste your DETAILED Beast Mode Prompts here.
# NOTE: Update 'PROMPT_B' to acknowledge it will receive 'FULL SOURCE TEXT'.

PROMPT_A_TRENDING = """ """ 
PROMPT_A_EVERGREEN = """ """ 
PROMPT_B_TEMPLATE = """ """ # <- This one needs to know about SOURCE_TEXT input
PROMPT_C_TEMPLATE = """ """ 
PROMPT_D_TEMPLATE = """ """ 
PROMPT_E_TEMPLATE = """ """ 
PROMPT_VIDEO_SCRIPT = """ """ 
PROMPT_YOUTUBE_METADATA = """ """ 
PROMPT_FACEBOOK_HOOK = """ """ 

# ==============================================================================
# 3. HELPER FUNCTIONS & CLASSES
# ==============================================================================

class KeyManager:
    """Round-robin Gemini API Keys."""
    def __init__(self):
        self.keys = []
        for i in range(1, 11):
            k = os.getenv(f'GEMINI_API_KEY_{i}')
            if k: self.keys.append(k)
        if not self.keys:
            k = os.getenv('GEMINI_API_KEY')
            if k: self.keys.append(k)
        self.current_index = 0
        log(f"🔑 Loaded {len(self.keys)} API Keys.")

    def get_current_key(self):
        if not self.keys: return None
        return self.keys[self.current_index]

    def switch_key(self):
        if self.current_index < len(self.keys) - 1:
            self.current_index += 1
            log(f"🔄 Quota limit. Switching to Key #{self.current_index + 1}...")
            return True
        else:
            log("❌ FATAL: All API Keys exhausted.")
            return False

key_manager = KeyManager()

def clean_json(text):
    """Robust JSON cleaner (Nuclear option)."""
    text = text.strip()
    match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if match: text = match.group(1)
    else:
        match = re.search(r'```\s*(.*?)\s*```', text, re.DOTALL)
        if match: text = match.group(1)
    
    if text.startswith("[") or (text.find("[") != -1 and text.find("[") < text.find("{")):
        start = text.find('[')
        end = text.rfind(']')
    else:
        start = text.find('{')
        end = text.rfind('}')
    
    if start != -1 and end != -1: return text[start:end+1].strip()
    return text.strip()

def try_parse_json(text, context=""):
    try: return json.loads(text)
    except:
        try:
            fixed = re.sub(r'\\(?![\\"/bfnrtu])', r'\\\\', text)
            return json.loads(fixed)
        except:
            log(f"      ❌ JSON Parse Error in {context}")
            return None

def fetch_full_article(url):
    """
    🌟 NEW: SCRAPER ENGINE 🌟
    Visits the real URL, grabs the body text to provide factual data to AI.
    """
    log(f"   🕷️ Scraping Article Source: {url}")
    try:
        # User-Agent to mimic real Chrome browser (bypass some blocks)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Referer': 'https://www.google.com/'
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        
        # If scraper fails (403/404), return None to fallback
        if response.status_code != 200:
            log(f"      ⚠️ Scrape blocked ({response.status_code}). Using RSS summary.")
            return None
            
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Cleanup DOM
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'form', 'ads', 'iframe']):
            tag.decompose()
            
        # Extract meaningful text (Paragraphs)
        # Filters out short nav links or empty lines
        paragraphs = [p.get_text().strip() for p in soup.find_all('p') if len(p.get_text()) > 25]
        
        # Combine text (Limit to first 12,000 chars to respect Token Limits)
        full_text = "\n\n".join(paragraphs)[:12000]
        
        if len(full_text) < 200:
            log("      ⚠️ Scraped content too short. Using RSS summary.")
            return None
            
        return full_text
        
    except Exception as e:
        log(f"      ⚠️ Scrape Exception: {e}")
        return None

def get_real_news_rss(query_keywords, category):
    try:
        # Smart Niche Selector
        if "," in query_keywords:
            topics = [t.strip() for t in query_keywords.split(',') if t.strip()]
            focused = random.choice(topics)
            log(f"   🎯 Targeted Search: '{focused}'")
            full_query = f"{focused} when:1d"
        else:
            full_query = f"{query_keywords} when:1d"

        encoded = urllib.parse.quote(full_query)
        url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
        
        feed = feedparser.parse(url)
        items = []
        if feed.entries:
            for entry in feed.entries[:7]:
                pub = entry.published if 'published' in entry else "Today"
                title_clean = entry.title.split(' - ')[0]
                # Note: 'link' here is passed to scraper later
                items.append({"title": title_clean, "link": entry.link, "date": pub})
            return items 
        else:
            # Fallback Logic
            log(f"   ⚠️ RSS Empty. Fallback to category.")
            fallback_q = f"{category} news when:1d"
            url = f"https://news.google.com/rss/search?q={urllib.parse.quote(fallback_q)}&hl=en-US&gl=US&ceid=US:en"
            feed = feedparser.parse(url)
            for entry in feed.entries[:4]:
                items.append({"title": entry.title, "link": entry.link, "date": "Today"})
            return items 
            
    except Exception as e:
        log(f"❌ RSS Error: {e}")
        return []

def get_blogger_token():
    payload = {
        'client_id': os.getenv('BLOGGER_CLIENT_ID'),
        'client_secret': os.getenv('BLOGGER_CLIENT_SECRET'),
        'refresh_token': os.getenv('BLOGGER_REFRESH_TOKEN'),
        'grant_type': 'refresh_token'
    }
    try:
        r = requests.post('https://oauth2.googleapis.com/token', data=payload)
        return r.json().get('access_token') if r.status_code == 200 else None
    except: return None

def publish_post(title, content, labels):
    token = get_blogger_token()
    if not token: return None
    
    url = f"https://www.googleapis.com/blogger/v3/blogs/{os.getenv('BLOGGER_BLOG_ID')}/posts"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {"title": title, "content": content, "labels": labels, "status": "LIVE"}
    
    try:
        r = requests.post(url, headers=headers, json=body)
        if r.status_code == 200:
            link = r.json().get('url')
            log(f"✅ Published: {link}")
            return link
        log(f"❌ Blogger Error: {r.text}")
        return None
    except Exception as e:
        log(f"❌ Blogger Fail: {e}")
        return None

def generate_and_upload_image(prompt_text, overlay_text=""):
    key = os.getenv('IMGBB_API_KEY')
    if not key: return None
    log(f"   🎨 Generating Image (Flux)...")
    for attempt in range(3):
        try:
            safe = urllib.parse.quote(f"{prompt_text}, abstract tech, 8k, --no text")
            txt = f"&text={urllib.parse.quote(overlay_text)}&font=roboto&fontsize=48&color=white" if overlay_text else ""
            url = f"https://image.pollinations.ai/prompt/{safe}?width=1280&height=720&model=flux&nologo=true&seed={random.randint(1,999)}{txt}"
            r = requests.get(url, timeout=50)
            if r.status_code == 200:
                res = requests.post("https://api.imgbb.com/1/upload", data={"key":key}, files={"image":r.content}, timeout=60)
                if res.status_code == 200:
                    link = res.json()['data']['url']
                    log(f"   ✅ Image URL: {link}")
                    return link
        except: time.sleep(3)
    return None

def load_kg():
    try:
        if os.path.exists('knowledge_graph.json'): return json.load(open('knowledge_graph.json','r'))
    except: pass
    return []

def get_recent_titles_string(limit=50):
    kg = load_kg()
    if not kg: return "None"
    return ", ".join([i.get('title','') for i in kg[-limit:]])

def get_relevant_kg_for_linking(current_category, limit=60):
    kg = load_kg()
    links = [{"title":i['title'],"url":i['url']} for i in kg if i.get('section')==current_category][:limit]
    return json.dumps(links)

def update_kg(title, url, section):
    try:
        data = load_kg()
        for i in data:
            if i['url']==url: return
        data.append({"title":title, "url":url, "section":section, "date":str(datetime.date.today())})
        with open('knowledge_graph.json','w') as f: json.dump(data, f, indent=2)
    except: pass

def perform_maintenance_cleanup():
    try:
        if os.path.exists('knowledge_graph.json'):
            with open('knowledge_graph.json','r') as f: d=json.load(f)
            if len(d)>800: json.dump(d[-400:], open('knowledge_graph.json','w'), indent=2)
    except: pass

def generate_step(model, prompt, step):
    log(f"   👉 Generating: {step}")
    while True:
        key = key_manager.get_current_key()
        if not key: 
            log("❌ FATAL: Keys exhausted.")
            return None
        client = genai.Client(api_key=key)
        try:
            r = client.models.generate_content(
                model=model, contents=prompt, config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            return clean_json(r.text)
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                log(f"      ⚠️ Key Quota. Switching...")
                if not key_manager.switch_key(): return None
            else:
                log(f"      ❌ AI Error: {e}")
                return None

# ==============================================================================
# 5. CORE PIPELINE LOGIC (RSS + SCRAPING + 5 STEPS)
# ==============================================================================

def run_pipeline(category, config, mode="trending"):
    model = config['settings'].get('model_name')
    cat_conf = config['categories'][category]
    
    log(f"\n🚀 INIT PIPELINE: {category} ({mode})")
    recent = get_recent_titles_string()

    # 1. RSS
    rss_items = get_real_news_rss(cat_conf.get('trending_focus',''), category)
    if not rss_items: return # Stop if empty

    # Flatten RSS for prompt
    rss_prompt_data = "\n".join([f"- Title: {i['title']}\n  Link: {i['link']}\n  Date: {i['date']}" for i in rss_items])

    # 2. Step A: Research Selection
    prompt_a = PROMPT_A_TRENDING.format(rss_data=rss_prompt_data, section=category, section_focus=cat_conf['trending_focus'], recent_titles=recent, today_date=str(datetime.date.today()))
    json_a = try_parse_json(generate_step(model, prompt_a, "Step A (Research)"), "A")
    if not json_a: return
    
    # 2.5: SCRAPING ENGINE (The Fact Checker)
    target_link = json_a.get('original_rss_link')
    log(f"   🗞️ Topic: {json_a.get('headline')} \n   🔗 Fetching source: {target_link}")
    
    full_source_text = fetch_full_article(target_link)
    
    if full_source_text:
        log("   ✅ Source Content Acquired. Using Factual Mode.")
        input_payload = f"*** REAL SOURCE CONTENT (USE THIS FACTS): ***\n\n{full_source_text}\n\n*** END SOURCE ***\n\n(Context: {json.dumps(json_a)})"
    else:
        log("   ⚠️ Source Blocked. Falling back to Analytical Mode.")
        input_payload = f"*** SOURCE UNAVAILABLE ***\n(Analyze the headline implications: {json.dumps(json_a)})"

    time.sleep(3)

    # 3. Step B: Drafting (Uses Scraped Input)
    prompt_b = PROMPT_B_TEMPLATE.format(json_input=input_payload, forbidden_phrases=str(FORBIDDEN_PHRASES))
    json_b = try_parse_json(generate_step(model, prompt_b, "Step B (Drafting)"), "B")
    if not json_b: return
    time.sleep(3)

    # 4. Step C: Format & SEO
    kg_links = get_relevant_kg_for_linking(category)
    prompt_c = PROMPT_C_TEMPLATE.format(json_input=json.dumps(json_b), knowledge_graph=kg_links)
    json_c = try_parse_json(generate_step(model, prompt_c, "Step C (SEO)"), "C")
    if not json_c: return
    time.sleep(3)

    # 5. Step D: Audit
    prompt_d = PROMPT_D_TEMPLATE.format(json_input=json.dumps(json_c))
    json_d = try_parse_json(generate_step(model, prompt_d, "Step D (Audit)"), "D")
    if not json_d: return
    time.sleep(3)

    # 6. Step E: Publish
    prompt_e = PROMPT_E_TEMPLATE.format(json_input=json.dumps(json_d))
    final_data = try_parse_json(generate_step(model, prompt_e, "Step E"), "E")
    
    # Failover if E returns text not json
    if not final_data: final_data = json_d 

    title = final_data.get('finalTitle', f"{category} News")

    # ========================================================
    # 🎥 MEDIA & SOCIAL
    # ========================================================
    log("   🧠 Generating Hooks...")
    yt_meta = try_parse_json(generate_step(model, PROMPT_YOUTUBE_METADATA.format(draft_title=title), "YT Meta")) or {"title":title, "description":"", "tags":[]}
    fb_data = try_parse_json(generate_step(model, PROMPT_FACEBOOK_HOOK.format(title=title, category=category), "FB Hook"))
    fb_cap = fb_data.get('facebook', title) if fb_data else title

    video_html, vid_main, vid_short, vid_path_fb = "", None, None, None
    try:
        # Pass scraped text summary for script accuracy
        script = try_parse_json(generate_step(model, PROMPT_VIDEO_SCRIPT.format(title=title, text_summary=final_data['excerpt']), "Script"))
        
        if script:
            rr = video_renderer.VideoRenderer()
            # 16:9
            pm = rr.render_video(script, title, f"main_{int(time.time())}.mp4")
            if pm:
                desc = f"{yt_meta['description']}\n\n👉 Full Story Link Soon.\n\n#AI #Tech"
                vid_main, _ = youtube_manager.upload_video_to_youtube(pm, yt_meta.get('title',title)[:100], desc, yt_meta.get('tags',[]))
                if vid_main:
                    video_html = f'<div class="video-container" style="position:relative;padding-bottom:56.25%;margin:35px 0;border-radius:12px;overflow:hidden;box-shadow:0 4px 12px rgba(0,0,0,0.1);"><iframe style="position:absolute;top:0;left:0;width:100%;height:100%;" src="https://www.youtube.com/embed/{vid_main}" frameborder="0" allowfullscreen></iframe></div>'
            # 9:16
            rs = video_renderer.VideoRenderer(width=1080, height=1920)
            ps = rs.render_video(script, title, f"short_{int(time.time())}.mp4")
            vid_path_fb = ps
            if ps: vid_short, _ = youtube_manager.upload_video_to_youtube(ps, f"{yt_meta.get('title',title)[:90]} #Shorts", desc, yt_meta.get('tags',[])+['shorts'])
    except Exception as e: log(f"⚠️ Video: {e}")

    # ========================================================
    # 📝 PUBLISH
    # ========================================================
    html_body = ARTICLE_STYLE
    img = generate_and_upload_image(final_data.get('imageGenPrompt', title), final_data.get('imageOverlayText', 'News'))
    if img: html_body += f'<div class="separator" style="clear:both;text-align:center;margin-bottom:30px;"><a href="{img}"><img src="{img}" alt="{final_data["seo"]["imageAltText"]}" /></a></div>'
    
    if video_html: html_body += video_html
    html_body += final_data.get('finalContent', '')
    
    if 'schemaMarkup' in final_data:
        try: html_body += f'\n<script type="application/ld+json">\n{json.dumps(final_data["schemaMarkup"])}\n</script>'
        except: pass
    
    url = publish_post(title, html_body, [category])
    
    # Social Update
    if url:
        update_kg(title, url, category)
        upd = f"\n\n🚀 FULL LINK: {url}"
        if vid_main: youtube_manager.update_video_description(vid_main, upd)
        if vid_short: youtube_manager.update_video_description(vid_short, upd)
        
        try:
            if vid_path_fb: social_manager.post_reel_to_facebook(vid_path_fb, f"{fb_cap}\n\nRead: {url} #Tech")
            time.sleep(10)
            if img: social_manager.distribute_content(f"{fb_cap}\n\n👇 BREAKDOWN:\n{url}", url, img)
        except: pass

# ==============================================================================
# 7. MAIN
# ==============================================================================

def main():
    try:
        with open('config_advanced.json','r') as f: cfg = json.load(f)
    except:
        log("❌ No Config.")
        return
    
    cat = random.choice(list(cfg['categories'].keys()))
    run_pipeline(cat, cfg, mode="trending")
    perform_maintenance_cleanup()
    log("✅ Finished.")

if __name__ == "__main__":
    main()
