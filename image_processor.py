# FILE: image_processor.py
import os
import re
import requests
import random
import datetime # تم الإضافة
import urllib.parse # تم الإضافة
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import cv2
import numpy as np
from github import Github
from google import genai
from google.genai import types
from bs4 import BeautifulSoup
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
    except: return None

def draw_text_with_outline(draw, position, text, font, fill_color, outline_color, outline_width):
    x, y = position
    for dx in range(-outline_width, outline_width + 1):
        for dy in range(-outline_width, outline_width + 1):
            if dx != 0 or dy != 0: draw.text((x + dx, y + dy), text, font=font, fill=outline_color)
    draw.text(position, text, font=font, fill=fill_color)

def upload_to_github_cdn(image_bytes, filename):
    try:
        gh_token = os.getenv('MY_GITHUB_TOKEN')
        image_repo_name = os.getenv('GITHUB_IMAGE_REPO') 
        if not image_repo_name: image_repo_name = os.getenv('GITHUB_REPO_NAME')
        if not gh_token or not image_repo_name: return None

        # استخدام الصيغة الحديثة للتوكن لتجنب التحذيرات
        g = Github(gh_token)
        repo = g.get_repo(image_repo_name)
        date_folder = datetime.datetime.now().strftime("%Y-%m") # كان يسبب الخطأ
        file_path = f"images/{date_folder}/{filename}"
        
        try:
            repo.create_file(path=file_path, message=f"🤖 Auto-upload: {filename}", content=image_bytes.getvalue(), branch="main")
        except Exception as e:
            if "already exists" in str(e):
                filename = f"{random.randint(1000,9999)}_{filename}"
                file_path = f"images/{date_folder}/{filename}"
                repo.create_file(path=file_path, message=f"Retry: {filename}", content=image_bytes.getvalue(), branch="main")
            else: raise e
        
        return f"https://cdn.jsdelivr.net/gh/{image_repo_name}@main/{file_path}"
    except Exception as e:
        log(f"      ❌ GitHub Upload Error: {e}")
        return None

def ensure_haarcascade_exists():
    cascade_path = "haarcascade_frontalface_default.xml"
    if not os.path.exists(cascade_path):
        url = "https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_default.xml"
        try:
            r = requests.get(url, timeout=30)
            with open(cascade_path, 'wb') as f: f.write(r.content)
        except: return None
    return cascade_path

def apply_smart_privacy_blur(pil_image):
    try:
        img_np = np.array(pil_image)
        if img_np.shape[2] == 4: img_np = cv2.cvtColor(img_np, cv2.COLOR_RGBA2BGR)
        else: img_np = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        cascade_path = ensure_haarcascade_exists()
        if not cascade_path: return pil_image
        face_cascade = cv2.CascadeClassifier(cascade_path)
        gray = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(30, 30))
        if len(faces) > 0:
            for (x, y, w, h) in faces:
                pad_w, pad_h = int(w*0.6), int(h*0.6)
                x1, y1 = max(0, x - pad_w), max(0, y - pad_h)
                x2, y2 = min(img_np.shape[1], x + w + pad_w), min(img_np.shape[0], y + h + int(h*0.8))
                roi = img_np[y1:y2, x1:x2]
                k_size = (w // 2) | 1
                k_size = max(k_size, 51)
                img_np[y1:y2, x1:x2] = cv2.GaussianBlur(roi, (k_size, k_size), 0)
        return Image.fromarray(cv2.cvtColor(img_np, cv2.COLOR_BGR2RGB))
    except: return pil_image.filter(ImageFilter.GaussianBlur(radius=15))

def select_best_image_with_gemini(model_name, article_title, images_list):
    if not images_list: return None
    valid_images = []
    headers = {'User-Agent': random.choice(USER_AGENTS)}
    for img_data in images_list[:4]: 
        try:
            r = requests.get(img_data['url'], headers=headers, timeout=10)
            if r.status_code == 200:
                valid_images.append({"mime_type": "image/jpeg", "data": r.content, "original_url": img_data['url']})
        except: pass
    if not valid_images: return None
    prompt = f"TASK: Select best image index (0-{len(valid_images)-1}) for '{article_title}'. Return Integer only."
    key = key_manager.get_current_key()
    client = genai.Client(api_key=key)
    inputs = [prompt]
    for img in valid_images: inputs.append(types.Part.from_bytes(data=img['data'], mime_type="image/jpeg"))
    for v_model in ["gemini-1.5-flash", "gemini-2.0-flash-exp"]:
        try:
            response = client.models.generate_content(model=v_model, contents=inputs)
            match = re.search(r'\d+', response.text)
            if match:
                idx = int(match.group())
                if 0 <= idx < len(valid_images): return valid_images[idx]['original_url']
        except: continue
    return images_list[0]['url']

def process_source_image(source_url, overlay_text, filename_title):
    if not source_url or source_url.startswith('/'): return None
    try:
        headers = {'User-Agent': random.choice(USER_AGENTS)}
        r = requests.get(source_url, headers=headers, timeout=15, stream=True)
        original_img = Image.open(BytesIO(r.content)).convert("RGBA")
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
        base_img = original_img.crop((left, top, left+target_w, top+target_h))
        base_img = apply_smart_privacy_blur(base_img.convert("RGB")).convert("RGBA")
        overlay = Image.new('RGBA', base_img.size, (0, 0, 0, 90))
        base_img = Image.alpha_composite(base_img, overlay)
        if overlay_text:
            draw = ImageDraw.Draw(base_img)
            try: font = ImageFont.truetype("arialbd.ttf", 80) 
            except: font = ImageFont.load_default()
            words = overlay_text.upper().split()
            lines, current_line = [], []
            for word in words:
                test_line = ' '.join(current_line + [word])
                bbox = draw.textbbox((0, 0), test_line, font=font)
                if bbox[2] < 1200 - 80: current_line.append(word)
                else: lines.append(' '.join(current_line)); current_line = [word]
            lines.append(' '.join(current_line))
            text_y = 315 - (len(lines) * 90 / 2)
            for line in lines:
                bbox = draw.textbbox((0, 0), line, font=font)
                line_x = (1200 - (bbox[2] - bbox[0])) / 2
                draw_text_with_outline(draw, (line_x, text_y), line, font, "#FFD700", "black", 5)
                text_y += 95
        img_byte_arr = BytesIO()
        base_img.convert("RGB").save(img_byte_arr, format='WEBP', quality=85)
        safe_name = re.sub(r'[^a-zA-Z0-9\s-]', '', filename_title).strip().replace(' ', '-').lower()[:50] + ".webp"
        return upload_to_github_cdn(img_byte_arr, safe_name)
    except: return None

def generate_and_upload_image(prompt_text, overlay_text=""):
    log(f"   🎨 Generating AI Thumbnail...")
    enhancers = ", photorealistic, shot on Sony A7R IV, 8k, youtube thumbnail style"
    final_prompt = urllib.parse.quote(f"{prompt_text}{enhancers}") # كان يسبب الخطأ
    seed = random.randint(1, 99999)
    image_url = f"https://image.pollinations.ai/prompt/{final_prompt}?width=1280&height=720&model=flux&seed={seed}&nologo=true"
    try:
        r = requests.get(image_url, timeout=60)
        img = Image.open(BytesIO(r.content)).convert("RGBA")
        if overlay_text:
            draw = ImageDraw.Draw(img)
            try: font = ImageFont.truetype("arial.ttf", 80)
            except: font = ImageFont.load_default()
            text = overlay_text.upper()
            bbox = draw.textbbox((0,0), text, font=font)
            x, y = (1280 - (bbox[2]-bbox[0]))/2, 720 - (bbox[3]-bbox[1]) - 50
            for dx in range(-4,5):
                for dy in range(-4,5): draw.text((x+dx, y+dy), text, font=font, fill="black")
            draw.text((x,y), text, font=font, fill="yellow")
        img_byte_arr = BytesIO()
        img.convert("RGB").save(img_byte_arr, format='WEBP', quality=85)
        return upload_to_github_cdn(img_byte_arr, f"ai_gen_{seed}.webp")
    except: return None
