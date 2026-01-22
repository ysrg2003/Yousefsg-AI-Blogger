import os
import json
import time
import requests
import re
import random
import sys
import datetime
import urllib.parse
import base64
import feedparser
from bs4 import BeautifulSoup
import social_manager
import video_renderer
import youtube_manager
from google import genai
from google.genai import types

# ==============================================================================
# 0. CONFIG & LOGGING
# ==============================================================================

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
# 1. CSS STYLING
# ==============================================================================
ARTICLE_STYLE = """
<style>
    .post-body { font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.85; color: #2c3e50; font-size: 19px; }
    h2 { color: #111; font-weight: 800; margin-top: 55px; margin-bottom: 25px; border-bottom: 4px solid #f1c40f; padding-bottom: 8px; display: inline-block; font-size: 28px; }
    h3 { color: #2980b9; font-weight: 700; margin-top: 40px; font-size: 24px; }
    .toc-box { background: #ffffff; border: 1px solid #e1e4e8; padding: 30px; margin: 40px 0; border-radius: 12px; display: inline-block; min-width: 60%; box-shadow: 0 8px 16px rgba(0,0,0,0.05); }
    .toc-box h3 { margin-top: 0; font-size: 22px; border-bottom: 2px solid #3498db; padding-bottom: 8px; display: inline-block; margin-bottom: 15px; color: #222; }
    .toc-box ul { list-style: none; padding: 0; margin: 0; }
    .toc-box li { margin-bottom: 12px; border-bottom: 1px dashed #f0f0f0; padding-bottom: 8px; padding-left: 20px; position: relative; }
    .toc-box li:before { content: "►"; color: #3498db; position: absolute; left: 0; font-size: 14px; top: 4px; }
    .toc-box a { color: #444; font-weight: 600; font-size: 18px; text-decoration: none; transition: 0.2s; }
    .toc-box a:hover { color: #3498db; padding-left: 8px; }
    .table-wrapper { overflow-x: auto; margin: 45px 0; border-radius: 12px; box-shadow: 0 5px 15px rgba(0,0,0,0.08); border: 1px solid #eee; }
    table { width: 100%; border-collapse: collapse; background: #fff; min-width: 600px; font-size: 18px; }
    th { background: #2c3e50; color: #fff; padding: 18px; text-align: left; text-transform: uppercase; font-size: 16px; letter-spacing: 1px; }
    td { padding: 16px 18px; border-bottom: 1px solid #eee; color: #34495e; }
    tr:nth-child(even) { background-color: #f8f9fa; }
    tr:hover { background-color: #e9ecef; transition: 0.3s; }
    .takeaways-box { background: linear-gradient(135deg, #fdfbf7 0%, #fff 100%); border-left: 6px solid #e67e22; padding: 30px; margin: 40px 0; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.02); }
    .takeaways-box h3 { margin-top: 0; color: #d35400; font-size: 22px; margin-bottom: 20px; display: flex; align-items: center; }
    .takeaways-box ul { margin: 0; padding-left: 25px; }
    .takeaways-box li { margin-bottom: 10px; font-weight: 600; font-size: 18px; color: #222; }
    .faq-section { margin-top: 70px; border-top: 3px solid #f1f1f1; padding-top: 50px; background: #fffcf5; padding: 40px; border-radius: 20px; }
    .faq-title { font-size: 30px; font-weight: 900; color: #222; margin-bottom: 35px; text-align: center; }
    .faq-q { font-weight: 700; font-size: 20px; color: #d35400; margin-bottom: 10px; display: block; }
    .faq-a { font-size: 19px; color: #555; line-height: 1.8; }
    .separator img { border-radius: 15px; box-shadow: 0 10px 40px rgba(0,0,0,0.12); max-width: 100%; height: auto; display: block; }
    blockquote { background: #ffffff; border-left: 5px solid #f1c40f; margin: 40px 0; padding: 25px 35px; font-style: italic; color: #555; font-size: 1.3em; line-height: 1.6; box-shadow: 0 3px 10px rgba(0,0,0,0.05); }
    a { color: #2980b9; text-decoration: none; font-weight: 600; border-bottom: 2px dotted #2980b9; transition: all 0.3s; }
    a:hover { color: #e67e22; border-bottom: 2px solid #e67e22; background-color: #fff8e1; }
</style>
"""

# ==============================================================================
# 2. PROMPTS (PASTE HERE)
# ==============================================================================

# 🛑 الصق البرومبتات التفصيلية "Beast Mode" هنا 🛑
PROMPT_A_TRENDING = """ """ 
PROMPT_A_EVERGREEN = """ """ 
PROMPT_B_TEMPLATE = """ """ 
PROMPT_C_TEMPLATE = """ """ 
PROMPT_D_TEMPLATE = """ """ 
PROMPT_E_TEMPLATE = """ """ 
PROMPT_VIDEO_SCRIPT = """ """ 
PROMPT_YOUTUBE_METADATA = """ """ 
PROMPT_FACEBOOK_HOOK = """ """ 

# ==============================================================================
# 3. HELPER UTILITIES
# ==============================================================================

class KeyManager:
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
            log(f"🔄 Key Limit. Switching #{self.current_index + 1}...")
            return True
        log("❌ FATAL: Keys Exhausted.")
        return False

key_manager = KeyManager()

def clean_json(text):
    text = text.strip()
    match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if match: text = match.group(1)
    else:
        match = re.search(r'```\s*(.*?)\s*```', text, re.DOTALL)
        if match: text = match.group(1)
    
    if text.startswith("[") or (text.find("[") != -1 and text.find("[") < text.find("{")):
        start, end = text.find('['), text.rfind(']')
    else:
        start, end = text.find('{'), text.rfind('}')
    
    if start != -1 and end != -1: return text[start:end+1].strip()
    return text.strip()

def try_parse_json(text, context=""):
    try: return json.loads(text)
    except:
        try:
            fixed = re.sub(r'\\(?![\\"/bfnrtu])', r'\\\\', text)
            return json.loads(fixed)
        except:
            log(f"      ❌ JSON Error ({context})")
            return None

def get_original_url(google_url):
    """
    CRITICAL FUNCTION: UNLOCKS GOOGLE NEWS REDIRECTS
    Uses Decoding + Requests to find the destination.
    """
    try:
        # METHOD 1: Clean Base64 Decoding
        # Google RSS URLs often embed the target URL encoded in base64.
        # Format usually has specific prefixes/suffixes. This attempts to clean and decode.
        try:
            base64_part = google_url.split('/')[-1].split('?')[0]
            # Fix padding
            base64_part += "=" * ((4 - len(base64_part) % 4) % 4)
            decoded_bytes = base64.urlsafe_b64decode(base64_part)
            decoded_str = decoded_bytes.decode('latin1', errors='ignore')
            
            # Find HTTPs url inside garbage
            urls = re.findall(r'(https?://[^"\'\s<>]+)', decoded_str)
            for u in urls:
                # Basic check to avoid grabbing Google internal links
                if "google.com" not in u and "googleusercontent" not in u:
                    if len(u) > 10:
                        log(f"      🔓 Decoded (Method 1): {u[:50]}...")
                        return u
        except:
            pass

        # METHOD 2: Link Following (If Method 1 fails)
        # Use cookies to verify 'consent' to prevent the redirection page block
        cookies = {
            'CONSENT': 'YES+cb.20210720-07-p0.en+FX+410', 
            'SOCS': 'CAESEwgDEgk0ODE3NzA3MjQaAmVuIAEaBgiAo_PmBg' 
        }
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9',
        }
        
        response = requests.get(google_url, headers=headers, cookies=cookies, timeout=10, allow_redirects=True)
        final_url = response.url
        
        if "news.google.com" not in final_url:
            log(f"      🔓 Redirected (Method 2): {final_url[:50]}...")
            return final_url
            
        # If still stuck on google, search page content
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Google Redirect Pages often have a link with specific class or just the first external link
        for a in soup.find_all('a', href=True):
            href = a['href']
            if href.startswith("http") and "google.com" not in href:
                log(f"      🔓 Scraped Link (Method 3): {href[:50]}...")
                return href
                
        return google_url # Fail, return original
        
    except Exception as e:
        log(f"      ⚠️ Resolve Error: {e}")
        return google_url

def fetch_full_article(url):
    """
    VISITS THE REAL SITE & SCRAPES TEXT
    """
    # 1. RESOLVE REDIRECT
    target_url = get_original_url(url)
    
    log(f"   🕷️ Reading: {target_url[:60]}...")
    
    try:
        session = requests.Session()
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Referer': 'https://www.google.com/'
        }
        
        response = session.get(target_url, headers=headers, timeout=20)
        
        if response.status_code != 200:
            log(f"      ❌ HTTP {response.status_code}")
            return None
            
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove Noise
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'form', 'noscript', 'iframe', 'button', 'input']):
            tag.decompose()
            
        # Get dense text
        text_blocks = []
        for p in soup.find_all('p'):
            text = p.get_text().strip()
            if len(text) > 60: # Filter Short captions
                text_blocks.append(text)
        
        full_text = "\n\n".join(text_blocks)[:12000] # Cap size
        
        if len(full_text) < 600:
            log("      ⚠️ Scrape too short (Bot protection or video page).")
            return None
            
        log(f"      ✅ Text Content: {len(full_text)} chars.")
        return full_text
        
    except Exception as e:
        log(f"      ⚠️ Scrape Crash: {e}")
        return None

def get_real_news_rss(query_keywords, category):
    try:
        # Selection Logic
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
            for entry in feed.entries[:8]:
                pub = entry.published if 'published' in entry else "Today"
                title_clean = entry.title.split(' - ')[0]
                items.append({"title": title_clean, "link": entry.link, "date": pub})
            return items 
        else:
            log(f"   ⚠️ RSS Empty. Using Category Fallback.")
            fb = f"{category} news when:1d"
            url = f"https://news.google.com/rss/search?q={urllib.parse.quote(fb)}&hl=en-US&gl=US&ceid=US:en"
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:
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
    
    url = f"https://www.googleapis.com/blogger/v3/blogs/{os.getenv('BLOGGER_BLOG_ID')}/posts?isDraft=false"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {"title": title, "content": content, "labels": labels}
    
    try:
        r = requests.post(url, headers=headers, json=body)
        if r.status_code == 200:
            link = r.json().get('url')
            log(f"✅ Blog Published: {link}")
            return link
        log(f"❌ Blogger Refusal: {r.text}")
        return None
    except Exception as e:
        log(f"❌ Connection Fail: {e}")
        return None

def generate_and_upload_image(prompt_text, overlay_text=""):
    key = os.getenv('IMGBB_API_KEY')
    if not key: return None
    log(f"   🎨 Image Gen (Flux)...")
    for attempt in range(3):
        try:
            safe = urllib.parse.quote(f"{prompt_text}, abstract tech, 8k, --no text")
            txt = f"&text={urllib.parse.quote(overlay_text)}&font=roboto&fontsize=48&color=white" if overlay_text else ""
            url = f"https://image.pollinations.ai/prompt/{safe}?width=1280&height=720&model=flux&nologo=true&seed={random.randint(1,999)}{txt}"
            r = requests.get(url, timeout=50)
            if r.status_code == 200:
                res = requests.post("https://api.imgbb.com/1/upload", data={"key":key}, files={"image":r.content}, timeout=60)
                if res.status_code == 200: return res.json()['data']['url']
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

def get_relevant_kg_for_linking(category, limit=60):
    kg = load_kg()
    links = [{"title":i['title'],"url":i['url']} for i in kg if i.get('section')==category][:limit]
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
                if not key_manager.switch_key(): return None
            else: return None

# ==============================================================================
# 5. CORE PIPELINE LOGIC (REDIRECT PROOF)
# ==============================================================================

def run_pipeline(category, config, mode="trending"):
    model = config['settings'].get('model_name')
    cat_conf = config['categories'][category]
    
    log(f"\n🚀 INIT PIPELINE: {category}")
    recent = get_recent_titles_string()

    # 1. RSS
    rss_items = get_real_news_rss(cat_conf.get('trending_focus',''), category)
    if not rss_items: return

    # Candidate Loop
    selected_item = None
    source_content = None
    
    # Try multiple items if scraping fails
    for item in rss_items[:3]:
        if item['title'][:30] in recent: continue # Dup check
        
        text = fetch_full_article(item['link'])
        
        if text:
            selected_item = item
            source_content = text
            break
    
    # Fallback to Analyst Mode
    is_analyst = False
    if not selected_item:
        if rss_items:
            log("⚠️ CRITICAL: Scraping ALL candidates failed. Enabling ANALYST MODE (Headline).")
            selected_item = rss_items[0]
            is_analyst = True
            source_content = "*** SCRAPING FAILED. Write ANALYTICAL OPINION piece based on HEADLINE and common knowledge. ***"
        else: return

    json_ctx = {
        "headline": selected_item['title'],
        "original_link": selected_item['link'],
        "date": selected_item['date']
    }
    
    # Drafting
    log(f"   🗞️ Writing: {selected_item['title']}")
    
    # Inject Text into Prompt
    payload = f"METADATA: {json.dumps(json_ctx)}\n\n*** SOURCE TEXT START ***\n{source_content}\n*** SOURCE TEXT END ***"
    
    json_b = try_parse_json(generate_step(model, PROMPT_B_TEMPLATE.format(json_input=payload, forbidden_phrases=str(FORBIDDEN_PHRASES)), "Step B"), "B")
    if not json_b: return
    time.sleep(3)

    # SEO
    kg_links = get_relevant_kg_for_linking(category)
    prompt_c = PROMPT_C_TEMPLATE.format(json_input=json.dumps(json_b), knowledge_graph=kg_links)
    json_c = try_parse_json(generate_step(model, prompt_c, "Step C"), "C")
    if not json_c: return
    time.sleep(3)

    # Audit
    prompt_d = PROMPT_D_TEMPLATE.format(json_input=json.dumps(json_c))
    json_d = try_parse_json(generate_step(model, prompt_d, "Step D"), "D")
    if not json_d: return
    time.sleep(3)

    # Publish
    prompt_e = PROMPT_E_TEMPLATE.format(json_input=json.dumps(json_d))
    final = try_parse_json(generate_step(model, prompt_e, "Step E"), "E")
    if not final: final = json_d 

    title = final.get('finalTitle', selected_item['title'])

    # Media & Hooks
    log("   🧠 Hooks...")
    yt_meta = try_parse_json(generate_step(model, PROMPT_YOUTUBE_METADATA.format(draft_title=title), "YT Meta")) or {"title":title, "description":"", "tags":[]}
    fb_dat = try_parse_json(generate_step(model, PROMPT_FACEBOOK_HOOK.format(title=title, category=category), "FB Hook"))
    fb_cap = fb_dat.get('facebook', title) if fb_dat else title

    # Video Gen
    vid_html, vid_main, vid_short, fb_path = "", None, None, None
    try:
        summ = re.sub('<[^<]+?>','', final.get('finalContent',''))[:1500]
        script = try_parse_json(generate_step(model, PROMPT_VIDEO_SCRIPT.format(title=title, text_summary=summ), "Script"))
        
        if script:
            rr = video_renderer.VideoRenderer()
            # 16:9
            pm = rr.render_video(script, title, f"main_{int(time.time())}.mp4")
            if pm:
                desc = f"{yt_meta.get('description','')}\n\n👉 Full Link Soon.\n\n#Tech"
                vid_main, _ = youtube_manager.upload_video_to_youtube(pm, yt_meta.get('title',title)[:100], desc, yt_meta.get('tags',[]))
                if vid_main:
                    vid_html = f'<div class="video-container" style="position:relative;padding-bottom:56.25%;margin:35px 0;border-radius:12px;overflow:hidden;box-shadow:0 4px 12px rgba(0,0,0,0.1);"><iframe style="position:absolute;top:0;left:0;width:100%;height:100%;" src="https://www.youtube.com/embed/{vid_main}" frameborder="0" allowfullscreen></iframe></div>'
            # 9:16
            rs = video_renderer.VideoRenderer(width=1080, height=1920)
            ps = rs.render_video(script, title, f"short_{int(time.time())}.mp4")
            fb_path = ps
            if ps: vid_short, _ = youtube_manager.upload_video_to_youtube(ps, f"{yt_meta.get('title',title)[:90]} #Shorts", desc, yt_meta.get('tags',[])+['shorts'])
    except Exception as e: log(f"⚠️ Video: {e}")

    # Final HTML
    body = ARTICLE_STYLE
    img = generate_and_upload_image(final.get('imageGenPrompt', title), final.get('imageOverlayText', 'News'))
    if img: body += f'<div class="separator" style="clear:both;text-align:center;margin-bottom:30px;"><a href="{img}"><img src="{img}" alt="{final.get("seo",{}).get("imageAltText","News")}" /></a></div>'
    if vid_html: body += vid_html
    body += final.get('finalContent', '')
    
    if 'schemaMarkup' in final:
        try: body += f'\n<script type="application/ld+json">\n{json.dumps(final["schemaMarkup"])}\n</script>'
        except: pass
    
    url = publish_post(title, body, [category])
    
    if url:
        update_kg(title, url, category)
        upd = f"\n\n🚀 FULL LINK: {url}"
        if vid_main: youtube_manager.update_video_description(vid_main, upd)
        if vid_short: youtube_manager.update_video_description(vid_short, upd)
        try:
            if fb_path: 
                social_manager.post_reel_to_facebook(fb_path, f"{fb_cap}\nLink: {url}")
                time.sleep(15)
            if img:
                social_manager.distribute_content(f"{fb_cap}\n\n👇 Read:\n{url}", url, img)
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
