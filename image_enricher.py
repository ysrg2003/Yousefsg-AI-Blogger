# FILE: image_enricher.py
import os
import requests
import numpy as np
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
from urllib.parse import urlparse

# استيراد وحدات المشروع
import image_processor 
from config import log

# --- AI Intelligence (للمطابقة الدلالية) ---
try:
    from sentence_transformers import SentenceTransformer
    from sklearn.metrics.pairwise import cosine_similarity
    AI_MODEL = SentenceTransformer('all-MiniLM-L6-v2')
    HAS_AI = True
except ImportError:
    log("⚠️ sentence-transformers not found. Ranking logic will be limited.")
    HAS_AI = False
    AI_MODEL = None

# --- Configuration ---
# عدد الصور التي نجلبها في كل عملية بحث
SEARCH_PAGE_SIZE = 8
# الحد الأقصى للصور في المقال
MAX_IMAGES = 10 
# --- End Configuration ---

def google_json_api_search(query: str, num_results: int = SEARCH_PAGE_SIZE) -> List[Dict]:
    """
    بحث مباشر باستخدام Google Custom Search JSON API.
    """
    api_key = os.getenv("GOOGLE_SEARCH_API_KEY")
    cx = os.getenv("GOOGLE_SEARCH_CX")
    
    if not api_key or not cx:
        log("   ❌ Google API Keys Missing!")
        return []

    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": api_key,
        "cx": cx,
        "q": query,
        "searchType": "image",
        "num": num_results,
        "safe": "high",
        "imgSize": "large",  # نريد صوراً واضحة للشرح
        "fileType": "jpg,png,webp"
    }
    
    try:
        response = requests.get(url, params=params, timeout=15)
        if response.status_code != 200: return []
        data = response.json()
        
        candidates = []
        for item in data.get("items", []):
            link = item.get("link")
            # استبعاد الأيقونات والصور الصغيرة جداً
            if any(x in link for x in ['logo', 'icon', 'favicon']): continue
            
            candidates.append({
                "url": link,
                "description": item.get("snippet", "") + " " + item.get("title", ""),
                "source": urlparse(item.get("displayLink", "")).netloc,
                "type": "google_search"
            })
        return candidates
    except Exception as e:
        log(f"      ⚠️ Google Search Error: {e}")
        return []

def gather_general_pool(article_title: str, article_meta: Dict, direct_images: List[Dict]) -> List[Dict]:
    """
    يجمع 'المسبح العام': صور رسمية + بحث جوجل عام عن الواجهة والمخططات.
    """
    pool = []
    
    # 1. الصور الرسمية (Official Extraction) - أولوية قصوى
    for img in direct_images:
        # نضيف كلمات مفتاحية للوصف لزيادة فرصة اختياره
        img['description'] = f"{img.get('description', '')} official interface screenshot {article_title}"
        pool.append(img)
    
    clean_title = article_title.split(':')[0].replace("Review", "").strip()

    # 2. بحث جوجل العام (General Context)
    # نبحث عن صور الواجهة العامة (Dashboard/UI)
    pool.extend(google_json_api_search(f"{clean_title} dashboard user interface screenshot"))
    
    # نبحث عن صور بيانية أو مقارنات (Charts)
    pool.extend(google_json_api_search(f"{clean_title} architecture diagram comparison chart"))

    # إزالة التكرار
    unique_pool = {v['url']: v for v in pool}.values()
    log(f"   🌊 Image Pool Created: {len(unique_pool)} candidates.")
    return list(unique_pool)

def find_image_for_slot(slot_context: str, article_title: str, image_pool: List[Dict], used_urls: set) -> Optional[Dict]:
    """
    المنطق الذكي:
    1. ابحث في المسبح عن صورة مطابقة للسياق.
    2. إذا لم تجد -> ابحث في جوجل خصيصاً لهذا السياق.
    """
    clean_title = article_title.split(':')[0]
    
    # --- المرحلة 1: البحث في المسبح (Pool) ---
    available = [img for img in image_pool if img['url'] not in used_urls]
    
    best_pool_image = None
    if available and HAS_AI:
        # استخدام Embeddings للمطابقة
        slot_emb = AI_MODEL.encode(slot_context)
        img_embs = AI_MODEL.encode([img['description'] for img in available])
        scores = cosine_similarity([slot_emb], img_embs)[0]
        
        best_idx = np.argmax(scores)
        best_score = scores[best_idx]
        
        # إذا كانت الصورة ملائمة جداً (Score > 0.30)، نأخذها ونوفر بحث جوجل
        if best_score > 0.30:
            log(f"      ✅ Found relevant image in Pool (Score: {best_score:.2f})")
            return available[best_idx]

    # --- المرحلة 2: البحث الخاص (Specific Fallback Search) ---
    # لم نجد صورة في المسبح تناسب هذه الفقرة (مثلاً: "خطوات التثبيت")
    # إذن، نبحث خصيصاً عنها.
    
    # نستخرج كلمات البحث من السياق (أول 6 كلمات معبرة)
    specific_query = f"{clean_title} {slot_context} screenshot"
    log(f"      🕵️‍♂️ Pool failed. Triggering SPECIFIC search: '{specific_query[:40]}...'")
    
    specific_results = google_json_api_search(specific_query, num_results=2)
    
    if specific_results:
        candidate = specific_results[0]
        candidate['type'] = 'specific_search' # نضع علامة أنها بحث خاص
        return candidate

    return None

def enrich_article_html(html: str, article_title: str, article_meta: Dict, direct_images: List[Dict] = []) -> str:
    """
    الوظيفة الرئيسية التي يستدعيها main.py
    """
    log("✨ [Image Enricher] Starting Analysis...")
    
    # 1. تجهيز المسبح العام
    image_pool = gather_general_pool(article_title, article_meta, direct_images)
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # 2. تحديد الأماكن التي تحتاج صور (العناوين الفرعية H2, H3)
    slots = []
    for element in soup.find_all(['h2', 'h3']):
        text = element.get_text(strip=True)
        # تجاهل العناوين القصيرة جداً أو الخاتمة
        if len(text) < 5 or any(x in text.lower() for x in ["conclusion", "faq", "verdict"]): 
            continue
        
        # نأخذ العنوان + جزء من الفقرة التالية كسياق للبحث
        context = text
        next_tag = element.find_next()
        if next_tag and next_tag.name == 'p':
            context += " " + next_tag.get_text(strip=True)[:100]
            
        slots.append({"context": context, "element": element})

    log(f"   📍 Identified {len(slots)} slots needing images.")
    
    used_urls = set()
    images_count = 0

    for slot in slots:
        if images_count >= MAX_IMAGES: break
        
        # البحث عن الصورة المناسبة (من المسبح أو بحث خاص)
        best_image = find_image_for_slot(slot['context'], article_title, image_pool, used_urls)
        
        if best_image:
            # --- المعالجة والرفع (Self-Hosting) ---
            final_url = image_processor.upload_external_image(best_image['url'], f"{article_title} {images_count}")
            
            if not final_url: 
                log("      ⚠️ Upload failed, skipping image.")
                continue

            # --- التضمين في المقال ---
            caption = best_image['description'].split('...')[0][:100]
            source_lbl = f"Source: {best_image['source']}"
            
            figure = BeautifulSoup(f'''
            <figure style="margin: 30px auto; text-align: center; max-width: 90%;">
                <img src="{final_url}" alt="{caption}" loading="lazy" 
                     style="width: 100%; height: auto; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); border: 1px solid #eee;">
                <figcaption style="font-size: 13px; color: #666; margin-top: 8px; font-style: italic;">
                    {caption} <span style="opacity: 0.7;">({source_lbl})</span>
                </figcaption>
            </figure>
            ''', 'html.parser')
            
            slot['element'].insert_after(figure)
            used_urls.add(best_image['url'])
            images_count += 1
            log(f"      ✅ Image inserted for: {slot['context'][:30]}...")

    return str(soup)
