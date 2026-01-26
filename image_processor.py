# FILE: image_processor.py
# DESCRIPTION: Handles image downloading, processing, face blurring, and hosting on GitHub.

import os
import re
import requests
import random
import datetime
import urllib.parse
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import cv2
import numpy as np
from github import Github
from google import genai
from google.genai import types
from bs4 import BeautifulSoup

# Import from local modules
from config import log, USER_AGENTS
from api_manager import key_manager

def extract_og_image(html_content):
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        meta = soup.find('meta', property='og:image')
        if meta and meta.get('content'): return meta['content']
        meta = soup.find('meta', name='twitter:image')
        if meta and meta.get('content'): return meta['content']
        return None
    except:
        return None

def draw_text_with_outline(draw, position, text, font, fill_color, outline_color, outline_width):
    x, y = position
    for dx in range(-outline_width, outline_width + 1):
        for dy in range(-outline_width, outline_width + 1):
            if dx != 0 or dy != 0:
                draw.text((x + dx, y + dy), text, font=font, fill=outline_color)
    draw.text(position, text, font=font, fill=fill_color)

def upload_to_github_cdn(image_bytes, filename):
    try:
        gh_token = os.getenv('MY_GITHUB_TOKEN')
        image_repo_name = os.getenv('GITHUB_IMAGE_REPO') 
        if not image_repo_name:
            image_repo_name = os.getenv('GITHUB_REPO_NAME')

        if not gh_token or not image_repo_name:
            log("      ❌ GitHub Token or Image Repo Name missing.")
            return None

        g = Github(gh_token)
        repo = g.get_repo(image_repo_name)
        
        date_folder = datetime.datetime.now().strftime("%Y-%m")
        file_path = f"images/{date_folder}/{filename}"
        
        try:
            repo.create_file(
                path=file_path,
                message=f"🤖 Auto-upload: {filename}",
                content=image_bytes.getvalue(),
                branch="main" 
            )
        except Exception as e:
            if "already exists" in str(e):
                filename = f"{random.randint(1000,9999)}_{filename}"
                file_path = f"images/{date_folder}/{filename}"
                repo.create_file(
                    path=file_path,
                    message=f"🤖 Auto-upload (Retry): {filename}",
                    content=image_bytes.getvalue(),
                    branch="main"
                )
            else:
                raise e

        cdn_url = f"https://cdn.jsdelivr.net/gh/{image_repo_name}@main/{file_path}"
        log(f"      ☁️ Hosted on Public CDN: {cdn_url}")
        return cdn_url

    except Exception as e:
        log(f"      ❌ GitHub Upload Error: {e}")
        return None

def ensure_haarcascade_exists():
    """
    Checks for face detection model, downloads if missing.
    """
    cascade_path = "haarcascade_frontalface_default.xml"
    if not os.path.exists(cascade_path):
        log("      📥 Downloading Face Detection Model (Haar Cascade)...")
        url = "https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_default.xml"
        try:
            r = requests.get(url, timeout=30)
            with open(cascade_path, 'wb') as f:
                f.write(r.content)
        except Exception as e:
            log(f"      ⚠️ Failed to download Haar Cascade: {e}")
            return None
    return cascade_path

def apply_smart_privacy_blur(pil_image):
    """
    Detects faces and applies heavy blur to protect privacy.
    """
    try:
        # Convert PIL to OpenCV (Numpy Array)
        img_np = np.array(pil_image)
        
        # Color conversion
        if img_np.shape[2] == 4: # RGBA
            img_np = cv2.cvtColor(img_np, cv2.COLOR_RGBA2BGR)
        else: # RGB
            img_np = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

        cascade_path = ensure_haarcascade_exists()
        if not cascade_path: 
            log("      ⚠️ Haar Cascade missing. Skipping smart blur.")
            return pil_image
        
        face_cascade = cv2.CascadeClassifier(cascade_path)
        gray = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY)

        faces = face_cascade.detectMultiScale(
            gray, 
            scaleFactor=1.1, 
            minNeighbors=5, 
            minSize=(30, 30)
        )

        if len(faces) > 0:
            log(f"      🕵️‍♂️ Detected {len(faces)} face(s). Applying NUCLEAR blur...")
            h_img, w_img, _ = img_np.shape
            
            for (x, y, w, h) in faces:
                pad_w = int(w * 0.6) 
                pad_h = int(h * 0.6)
                pad_h_bottom = int(h * 0.8)
                
                x1 = max(0, x - pad_w)
                y1 = max(0, y - pad_h)
                x2 = min(w_img, x + w + pad_w)
                y2 = min(h_img, y + h + pad_h_bottom)
                
                roi = img_np[y1:y2, x1:x2]
                
                k_size = (w // 2) 
                if k_size % 2 == 0: k_size += 1
                k_size = max(k_size, 51) 
                
                try:
                    blurred_roi = cv2.GaussianBlur(roi, (k_size, k_size), 0)
                    img_np[y1:y2, x1:x2] = blurred_roi
                except: continue

        # Convert back to PIL (RGB)
        img_rgb = cv2.cvtColor(img_np, cv2.COLOR_BGR2RGB)
        return Image.fromarray(img_rgb)

    except Exception as e:
        log(f"      ⚠️ Smart Blur Error: {e}. Fallback to global blur.")
        return pil_image.filter(ImageFilter.GaussianBlur(radius=15))

def select_best_image_with_gemini(model_name, article_title, images_list):
    """
    Uses Gemini Vision to select the best image, avoiding close-up faces.
    """
    if not images_list: return None

    log(f"   🤖 Asking Gemini to select the best image from {len(images_list)} candidates...")

    valid_images = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    for i, img_data in enumerate(images_list[:4]): 
        try:
            r = requests.get(img_data['url'], headers=headers, timeout=10)
            if r.status_code == 200:
                valid_images.append({
                    "mime_type": "image/jpeg",
                    "data": r.content,
                    "original_url": img_data['url']
                })
        except: pass

    if not valid_images: return None

    prompt = f"""
    TASK: Photo Editor Selection.
    ARTICLE TITLE: "{article_title}"
    
    CRITERIA FOR SELECTION:
    1. **Relevance:** Image must match the specific tech topic.
    2. **PRIVACY & AESTHETICS:** 
       - **PREFER:** Images of gadgets, screens, code, wide shots of offices, or robots.
       - **AVOID:** Close-up portraits of specific people faces if an alternative exists.
       - **AVOID:** Low quality or blurry images.
    
    OUTPUT INSTRUCTIONS:
    - Return ONLY the integer index (0, 1, 2...) of the best image.
    - If ALL images are completely irrelevant or unsafe, return -1.
    """

    try:
        key = key_manager.get_current_key()
        client = genai.Client(api_key=key)
        
        inputs = [prompt]
        for img in valid_images:
            inputs.append(types.Part.from_bytes(data=img['data'], mime_type="image/jpeg"))

        response = client.models.generate_content(
            model="gemini-2.5-flash", 
            contents=inputs
        )
        
        result = response.text.strip()
        
        if "-1" in result or "NONE" in result:
            log("      🤖 Gemini rejected all source images.")
            return None
            
        match = re.search(r'\d+', result)
        if match:
            idx = int(match.group())
            if 0 <= idx < len(valid_images):
                log(f"      ✅ Gemini selected Image #{idx+1}.")
                return valid_images[idx]['original_url']
                
    except Exception as e:
        log(f"      ⚠️ Gemini Vision Error: {e}")
    
    return images_list[0]['url']

def process_source_image(source_url, overlay_text, filename_title):
    log(f"   🖼️ Processing Source Image: {source_url[:60]}...")
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(source_url, headers=headers, timeout=15, stream=True)
        if r.status_code != 200: return None
        
        original_img = Image.open(BytesIO(r.content)).convert("RGBA")
        
        # Resize & Crop (1200x630)
        target_w, target_h = 1200, 630
        img_ratio = original_img.width / original_img.height
        target_ratio = target_w / target_h
        
        if img_ratio > target_ratio:
            new_width = int(target_h * img_ratio)
            new_height = target_h
        else:
            new_width = target_w
            new_height = int(target_w / img_ratio)
            
        original_img = original_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        left = (new_width - target_w) / 2
        top = (new_height - target_h) / 2
        right = (new_width + target_w) / 2
        bottom = (new_height + target_h) / 2
        base_img = original_img.crop((left, top, right, bottom))
        
        # Smart Privacy Filter
        base_img_rgb = base_img.convert("RGB")
        base_img_rgb = apply_smart_privacy_blur(base_img_rgb)
        base_img = base_img_rgb.convert("RGBA")

        # Dark Overlay
        overlay = Image.new('RGBA', base_img.size, (0, 0, 0, 90))
        base_img = Image.alpha_composite(base_img, overlay)
        
        # Text Overlay
        if overlay_text:
            draw = ImageDraw.Draw(base_img)
            W, H = base_img.size
            
            # --- FONT LOGIC RESTORED FROM OLD CODE ---
            try:
                font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
                if not os.path.exists(font_path): font_path = "arialbd.ttf"
                font = ImageFont.truetype(font_path, 80)
            except: font = ImageFont.load_default()
            # -----------------------------------------
            
            words = overlay_text.upper().split()
            lines = []
            current_line = []
            for word in words:
                test_line = ' '.join(current_line + [word])
                bbox = draw.textbbox((0, 0), test_line, font=font)
                if bbox[2] < W - 80:
                    current_line.append(word)
                else:
                    lines.append(' '.join(current_line))
                    current_line = [word]
            lines.append(' '.join(current_line))
            
            text_y = H / 2 - (len(lines) * 90 / 2)
            for line in lines:
                bbox = draw.textbbox((0, 0), line, font=font)
                line_x = (W - (bbox[2] - bbox[0])) / 2
                draw_text_with_outline(draw, (line_x, text_y), line, font, "#FFD700", "black", 5)
                text_y += 95

        img_byte_arr = BytesIO()
        base_img.convert("RGB").save(img_byte_arr, format='JPEG', quality=95)
        
        safe_filename = re.sub(r'[^a-zA-Z0-9\s-]', '', filename_title).strip().replace(' ', '-').lower()[:50] + ".jpg"
        
        return upload_to_github_cdn(img_byte_arr, safe_filename)
            
    except Exception as e:
        log(f"      ⚠️ Image Processing Error: {e}")
        return None

def generate_and_upload_image(prompt_text, overlay_text=""):
    log(f"   🎨 Generating Thumbnail (Flux + GitHub Host)...")
    
    enhancers = ", photorealistic, shot on Sony A7R IV, 8k, youtube thumbnail style"
    final_prompt = urllib.parse.quote(f"{prompt_text}{enhancers}")
    seed = random.randint(1, 99999)
    image_url = f"https://image.pollinations.ai/prompt/{final_prompt}?width=1280&height=720&model=flux&seed={seed}&nologo=true"

    try:
        r = requests.get(image_url, timeout=60)
        if r.status_code != 200: return None
        
        img = Image.open(BytesIO(r.content)).convert("RGBA")
        
        if overlay_text:
            draw = ImageDraw.Draw(img)
            W, H = img.size
            
            # --- FONT LOGIC RESTORED FROM OLD CODE ---
            try:
                font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
                if not os.path.exists(font_path): font_path = "arial.ttf"
                font = ImageFont.truetype(font_path, 80)
            except: font = ImageFont.load_default()
            # -----------------------------------------
            
            text = overlay_text.upper()
            bbox = draw.textbbox((0, 0), text, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            x = (W - text_w) / 2
            y = H - text_h - 50
            
            for dx in range(-4, 5):
                for dy in range(-4, 5):
                    draw.text((x+dx, y+dy), text, font=font, fill="black")
            draw.text((x, y), text, font=font, fill="yellow")

        img_byte_arr = BytesIO()
        img.convert("RGB").save(img_byte_arr, format='JPEG', quality=95)
        
        filename = f"ai_gen_{seed}.jpg"
        return upload_to_github_cdn(img_byte_arr, filename)
            
    except Exception as e:
        log(f"      ⚠️ AI Image Error: {e}")
    
    return None
