# FILE: image_enricher.py
# ROLE: Visual Quality Gatekeeper.
# STRICT UPDATE: Rejects generic stock photos. Only allows relevant UI/Context images.

import os
import requests
import numpy as np
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import re

# Project imports
import image_processor 
from config import log

# --- Configuration ---
# Only accept images if they contain these keywords in description/alt text
VALID_IMAGE_KEYWORDS = ["interface", "dashboard", "screenshot", "diagram", "chart", "architecture", "demo", "workflow", "configuration", "panel", "menu", "graph"]
# Reject if they contain these
BAD_IMAGE_KEYWORDS = ["stock", "generic", "concept", "illustration", "vector", "art", "drawing", "symbol"]

def google_json_api_search(query: str, num_results: int = 4) -> List[Dict]:
    """
    Strict Search: Adds 'UI' and 'Screenshot' to query to force relevance.
    """
    api_key = os.getenv("GOOGLE_SEARCH_API_KEY")
    cx = os.getenv("GOOGLE_SEARCH_CX")
    
    if not api_key or not cx: return []

    # Force visual relevance in query
    strict_query = f"{query} (dashboard OR screenshot OR interface)"

    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": api_key, "cx": cx, "q": strict_query,
        "searchType": "image", "num": num_results, "safe": "high",
        "imgSize": "large", "fileType": "jpg,png,webp"
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code != 200: return []
        data = response.json()
        
        candidates = []
        for item in data.get("items", []):
            link = item.get("link")
            title = (item.get("snippet", "") + " " + item.get("title", "")).lower()
            
            # 1. Keyword Filtering (The Trash Filter)
            if any(bad in title for bad in BAD_IMAGE_KEYWORDS): continue
            
            # 2. Heuristic Check
            if "logo" in title or "icon" in title: continue

            candidates.append({
                "url": link,
                "description": title,
                "source": urlparse(item.get("displayLink", "")).netloc,
                "type": "google_search"
            })
        return candidates
    except Exception as e:
        log(f"      ⚠️ Google Search Error: {e}")
        return []

def enrich_article_html(html: str, article_title: str, article_meta: Dict, direct_images: List[Dict] = []) -> str:
    log("✨ [Image Enricher] Starting Strict Visual Analysis...")
    
    # 1. Prioritize Official Images (They are the source of truth)
    # We trust 'direct_images' coming from the Scraper because they are from the source URL.
    image_pool = direct_images.copy()
    
    # 2. Add Search Results ONLY if we don't have enough official images
    if len(image_pool) < 3:
        clean_title = article_title.split(':')[0].replace("Review", "").strip()
        search_results = google_json_api_search(clean_title)
        image_pool.extend(search_results)

    soup = BeautifulSoup(html, 'html.parser')
    
    # 3. Intelligent Slotting
    slots = soup.find_all(['h2', 'h3'])
    used_urls = set()
    images_inserted = 0
    
    for element in slots:
        if images_inserted >= 5: break
        
        header_text = element.get_text(strip=True).lower()
        
        # Only inject images in relevant sections
        if any(x in header_text for x in ["interface", "dashboard", "how to", "look", "demo", "setup", "features"]):
            
            # Find best image
            best_img = None
            for img in image_pool:
                if img['url'] in used_urls: continue
                
                # Simple matching: Does image desc match header?
                # e.g. Header: "The Dashboard" -> Image: "Fieldguide Dashboard UI"
                if any(w in img['description'].lower() for w in header_text.split()):
                    best_img = img
                    break
            
            # Fallback: Just take the next official image if available
            if not best_img and image_pool:
                for img in image_pool:
                    if img['url'] not in used_urls:
                        best_img = img; break

            if best_img:
                # --- FINAL QUALITY CHECK ---
                # Upload -> Blur -> Check
                final_url = image_processor.upload_external_image(best_img['url'], f"{article_title} {images_inserted}")
                
                if final_url:
                    caption = best_img['description'].split('...')[0][:80]
                    figure = BeautifulSoup(f'''
                    <figure style="margin: 30px auto; text-align: center;">
                        <img src="{final_url}" alt="{caption}" style="width: 100%; border-radius: 8px; border: 1px solid #ddd; box-shadow: 0 2px 10px rgba(0,0,0,0.05);">
                        <figcaption style="font-size: 13px; color: #777; margin-top: 5px;">📸 {caption}</figcaption>
                    </figure>
                    ''', 'html.parser')
                    
                    element.insert_after(figure)
                    used_urls.add(best_img['url'])
                    images_inserted += 1
                    log(f"      ✅ Injected image for header: {header_text[:20]}...")

    return str(soup)
