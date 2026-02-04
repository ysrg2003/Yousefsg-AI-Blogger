# FILE: image_enricher.py
# ROLE: The Autonomous Photo Editor (Hunter-Gatherer Edition).
# STRATEGY: 
# 1. Scans Article Headers.
# 2. Performs TARGETED Google Searches for EACH section specifically.
# 3. Aggregates all finds + Official Images.
# 4. Uses Gemini Vision to map the absolute best images to sections.

import os
import requests
import concurrent.futures
import json
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from io import BytesIO
from PIL import Image
from google import genai
from google.genai import types

# Project imports
import image_processor 
from config import log
from api_manager import key_manager

# --- Configuration ---
MAX_POOL_SIZE = 20  # نجمع عدداً كبيراً من الصور لنعطي الذكاء الاصطناعي خيارات واسعة
DOWNLOAD_TIMEOUT = 5

def download_image_to_memory(url: str) -> Optional[bytes]:
    """Downloads image to memory for AI analysis (Fast & Safe)."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Referer': 'https://www.google.com/'
        }
        r = requests.get(url, headers=headers, timeout=DOWNLOAD_TIMEOUT)
        if r.status_code != 200: return None
        
        # Validation: Is it actually an image?
        if 'image' not in r.headers.get('Content-Type', ''): return None
        
        # Resize huge images to save bandwidth/tokens
        if len(r.content) > 3 * 1024 * 1024: 
            img = Image.open(BytesIO(r.content))
            if img.mode in ("RGBA", "P"): img = img.convert("RGB")
            img.thumbnail((1024, 1024))
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=85)
            return buf.getvalue()
            
        return r.content
    except: return None

def targeted_google_search(query: str, section_context: str, num_results: int = 3) -> List[Dict]:
    """
    Performs a specialized search for a specific section.
    Ex: Query: "Fieldguide", Section: "Reporting Features" -> Search: "Fieldguide reporting features screenshot UI"
    """
    api_key = os.getenv("GOOGLE_SEARCH_API_KEY")
    cx = os.getenv("GOOGLE_SEARCH_CX")
    if not api_key or not cx: return []
    
    # Construct a highly specific query
    # We insist on "Screenshot" or "UI" to avoid abstract art
    full_query = f"{query} {section_context} (screenshot OR interface OR demo OR diagram)"
    
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": api_key, "cx": cx, "q": full_query,
        "searchType": "image", "num": num_results, "safe": "high",
        "imgSize": "large", "fileType": "jpg,png,webp"
    }
    try:
        r = requests.get(url, params=params, timeout=5)
        if r.status_code != 200: return []
        data = r.json()
        
        results = []
        for item in data.get("items", []):
            # Basic trash filter
            title = item.get("title", "").lower()
            if any(x in title for x in ["stock", "vector", "clipart", "logo", "icon"]): continue
            
            results.append({
                "url": item.get("link"),
                "description": item.get("title"),
                "source": urlparse(item.get("displayLink", "")).netloc,
                "type": "targeted_search",
                "target_section": section_context # Tag it so we know where it belongs
            })
        return results
    except: return []

def batch_analyze_and_map(candidates: List[Dict], headers_list: List[str], topic: str):
    """
    THE MASTERMIND: Sends everything to Gemini Vision to pick the winners.
    """
    log(f"   🧠 [Art Director] Reviewing {len(candidates)} candidates for {len(headers_list)} sections...")
    
    # 1. Parallel Download
    valid_images_payload = []
    valid_indices_map = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        future_to_idx = {executor.submit(download_image_to_memory, c['url']): i for i, c in enumerate(candidates)}
        results = sorted([(future_to_idx[f], f.result()) for f in concurrent.futures.as_completed(future_to_idx)], key=lambda x: x[0])
        
    for original_idx, img_bytes in results:
        if img_bytes:
            valid_indices_map.append(original_idx)
            # Create Gemini Part
            valid_images_payload.append(types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"))

    if not valid_images_payload:
        log("      ⚠️ All image downloads failed. No visuals to analyze.")
        return {}

    # 2. Strict Prompt
    headers_text = "\n".join([f"- {h}" for h in headers_list])
    
    prompt_text = f"""
    ROLE: Elite Tech Journalist & Photo Editor.
    TASK: Map the BEST available images to the article sections.
    
    ARTICLE TOPIC: {topic}
    SECTIONS TO FILL:
    {headers_text}
    
    INSTRUCTIONS:
    1. I have provided {len(valid_images_payload)} images below.
    2. Examine each image. Is it a **REAL** UI screenshot, Product Photo, or Technical Diagram relevant to the topic?
    3. **REJECT GARBAGE:** 
       - If it's a generic stock photo (people in suits, blue brains), IGNORE IT.
       - If it's a logo on a white background, IGNORE IT.
       - If it's blurry or irrelevant, IGNORE IT.
    4. **MAP TO SECTIONS:**
       - Assign the best image index to the most relevant section.
       - You can leave a section as `null` if no good image exists. DO NOT force a bad image.
    
    OUTPUT JSON ONLY:
    {{
        "mapping": {{
            "Section Title": integer_index_of_image_or_null,
            ...
        }}
    }}
    """
    
    # 3. API Call
    try:
        key = key_manager.get_current_key()
        client = genai.Client(api_key=key)
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt_text] + valid_images_payload,
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.0)
        )
        
        result = json.loads(response.text)
        mapping = result.get("mapping", {})
        
        final_assignments = {}
        used_indices = set()
        
        for section, ai_idx in mapping.items():
            if ai_idx is not None and isinstance(ai_idx, int):
                if 0 <= ai_idx < len(valid_indices_map):
                    real_idx = valid_indices_map[ai_idx]
                    if real_idx not in used_indices:
                        final_assignments[section] = candidates[real_idx]
                        used_indices.add(real_idx)
                        
        return final_assignments

    except Exception as e:
        log(f"      ❌ Vision Analysis Failed: {e}")
        return {}

def enrich_article_html(html: str, article_title: str, article_meta: Dict, direct_images: List[Dict] = []) -> str:
    log("\n✨ [Image Enricher] Starting Agentic Search & Analysis...")
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # 1. Identify "Visual" Sections
    target_sections = []
    header_elements = {}
    
    for h2 in soup.find_all(['h2', 'h3']):
        text = h2.get_text(strip=True)
        # We target sections that likely need explanation
        if any(x in text.lower() for x in ["interface", "dashboard", "how to", "setup", "features", "performance", "architecture", "vs", "comparison"]):
            target_sections.append(text)
            header_elements[text] = h2
            
    if not target_sections:
        return str(soup)

    # 2. BUILD THE POOL (The Hunter Phase)
    # Start with official images (High Trust)
    candidate_pool = direct_images.copy()
    
    # Add GENERAL search results (Medium Trust)
    clean_keyword = article_title.split(':')[0].replace("Review", "").strip()
    candidate_pool.extend(targeted_google_search(clean_keyword, "overview", num_results=4))
    
    # Add SPECIFIC targeted searches for top 3 sections (High Precision)
    # This solves the "specific image for specific paragraph" problem
    log(f"   🕵️‍♂️ Performing targeted searches for {len(target_sections[:3])} sections...")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        future_to_sec = {
            executor.submit(targeted_google_search, clean_keyword, section): section 
            for section in target_sections[:3] # Limit to top 3 sections to save API quota
        }
        for future in concurrent.futures.as_completed(future_to_sec):
            new_imgs = future.result()
            if new_imgs:
                candidate_pool.extend(new_imgs)

    # Deduplicate Pool
    seen_urls = set()
    unique_pool = []
    for img in candidate_pool:
        if img['url'] not in seen_urls:
            unique_pool.append(img)
            seen_urls.add(img['url'])
            
    # Limit pool size for Gemini
    unique_pool = unique_pool[:MAX_POOL_SIZE]
    
    if not unique_pool:
        log("      ⚠️ No images found anywhere.")
        return str(soup)

    # 3. SELECT THE BEST (The Judge Phase)
    assignments = batch_analyze_and_map(unique_pool, target_sections, article_title)
    
    # 4. INJECT
    injected_count = 0
    for section_text, img_data in assignments.items():
        element = header_elements.get(section_text)
        if element:
            # Upload ONLY the winners
            final_url = image_processor.upload_external_image(img_data['url'], f"{clean_keyword} {injected_count}")
            
            if final_url:
                caption = f"{section_text}: {img_data['description'][:80]} ({img_data['source']})"
                
                figure = BeautifulSoup(f'''
                <figure style="margin: 30px auto; text-align: center;">
                    <img src="{final_url}" alt="{caption}" style="width: 100%; border-radius: 8px; border: 1px solid #ddd; box-shadow: 0 4px 12px rgba(0,0,0,0.08);">
                    <figcaption style="font-size: 13px; color: #555; margin-top: 8px; font-style: italic;">📸 {caption}</figcaption>
                </figure>
                ''', 'html.parser')
                
                element.insert_after(figure)
                injected_count += 1
                log(f"      ✅ Injected: {section_text[:20]}... -> {img_data['url'][:30]}...")

    return str(soup)
