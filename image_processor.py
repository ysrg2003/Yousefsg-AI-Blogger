# FILE: image_processor.py
# DESCRIPTION: Smart Image Processing (Face/Neck/Hair Blur ONLY if detected).

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
            if dx != 0 or dy != 0:
                draw.text((x + dx, y + dy), text, font=font, fill=outline_color)
    draw.text(position, text, font=font, fill=fill_color)

def upload_to_github_cdn(image_bytes, filename):
    try:
        gh_token = os.getenv('MY_GITHUB_TOKEN')
        image_repo_name = os.getenv('GITHUB_IMAGE_REPO') 
        if not image_repo_name: image_repo_name = os.getenv('GITHUB_REPO_NAME')
        if not gh_token or not image_repo_name: return None

        g = Github(gh_token)
        repo = g.get_repo(image_repo_name)
        date_folder = datetime.datetime.now().strftime("%Y-%m")
        file_path = f"images/{date_folder}/{filename}"
        
        try:
            repo.create_file(path=file_path, message=f"🤖 Auto: {filename}", content=image_bytes.getvalue(), branch="main")
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
    """
    Applies blur ONLY to faces (including hair/neck) if detected.
    If no faces are found, returns the original sharp image.
    """
    try:
        # Convert PIL to OpenCV format
        img_np = np.array(pil_image)
        if img_np.shape[2] == 4: img_np = cv2.cvtColor(img_np, cv2.COLOR_RGBA2BGR)
        else: img_np = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

        cascade_path = ensure_haarcascade_exists()
        if not cascade_path: 
            return pil_image # Return original if model missing
        
        face_cascade = cv2.CascadeClassifier(cascade_path)
        gray = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY)
        
        # Detect faces (Human & Humanoid Robots)
        # minNeighbors=4 makes it slightly aggressive to catch robots
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(30, 30))

        if len(faces) > 0:
            log(f"      🕵️‍♂️ Detected {len(faces)} face(s). Applying Extended Blur (Face+Hair+Neck)...")
            h_img, w_img, _ = img_np.shape
            
            for (x, y, w, h) in faces:
                # --- EXPANDED BLUR AREA LOGIC ---
                # We expand the box significantly to cover hair and neck
                pad_w = int(w * 0.5)        # 50% padding on sides
                pad_h_top = int(h * 0.8)    # 80% padding on top (Hair)
                pad_h_bottom = int(h * 1.0) # 100% padding on bottom (Neck)
                
                # Calculate coordinates with boundary checks
                x1 = max(0, x - pad_w)
                y1 = max(0, y - pad_h_top)
                x2 = min(w_img, x + w + pad_w)
                y2 = min(h_img, y + h + pad_h_bottom)
                
                # Extract Region of Interest (ROI)
                roi = img_np[y1:y2, x1:x2]
                
                # Calculate blur strength based on face size
                k_size = (w // 2) | 1 # Ensure odd number
                k_size = max(k_size, 99) # Minimum blur strength (Very High)
                
                try:
                    # Apply Gaussian Blur
                    blurred_roi = cv2.GaussianBlur(roi, (k_size, k_size), 0)
                    img_np[y1:y2, x1:x2] = blurred_roi
                except: pass
            
            # Convert back to PIL if changes were made
            return Image.fromarray(cv2.cvtColor(img_np, cv2.COLOR_BGR2RGB))
        
        else:
            # --- NO FACES DETECTED ---
            log("      👀 No faces detected. Keeping image sharp.")
            return pil_image # Return original sharp image

    except Exception as e:
        log(f"      ⚠️ Smart Blur Error: {e}. Returning original.")
        return pil_image


prompt = f"""
    TASK: You are a Photo Editor.
    CONTEXT: I need an image that best represents: {context_description}.
    
    INSTRUCTIONS:
    - Look at the provided images.
    - Select the one that is clearest, most relevant, and high quality.
    - Avoid images that are just text, logos, or blurry.
    - Return ONLY the index number (0, 1, 2, etc.) of the best image.
    """
def process_source_image(source_url, overlay_text, filename_title):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(source_url, headers=headers, timeout=15, stream=True)
        if r.status_code != 200: return None
        
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
        
        # --- APPLY SMART BLUR (Only if faces detected) ---
        # We convert to RGB for processing, then back to RGBA
        base_img_rgb = base_img.convert("RGB")
        base_img_rgb = apply_smart_privacy_blur(base_img_rgb)
        base_img = base_img_rgb.convert("RGBA")
        # -------------------------------------------------

        # Dark Overlay (For text readability)
        overlay = Image.new('RGBA', base_img.size, (0, 0, 0, 90))
        base_img = Image.alpha_composite(base_img, overlay)
        
        if overlay_text:
            draw = ImageDraw.Draw(base_img)
            try:
                font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
                if not os.path.exists(font_path): font_path = "arialbd.ttf"
                font = ImageFont.truetype(font_path, 80)
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
        base_img.convert("RGB").save(img_byte_arr, format='JPEG', quality=95)
        safe_name = re.sub(r'[^a-zA-Z0-9\s-]', '', filename_title).strip().replace(' ', '-').lower()[:50] + ".jpg"
        return upload_to_github_cdn(img_byte_arr, safe_name)
    except: return None
def select_best_images_batch(model_name, batch_data):
    """
    يعالج دفعة كاملة من الصور لعدة فقرات في طلب واحد للذكاء الاصطناعي.
    batch_data structure:
    {
        0: {"context": "Dashboard UI", "urls": [url1, url2, url3]},
        1: {"context": "Workflow", "urls": [url4, url5, url6]},
        ...
    }
    """
    if not batch_data: return {}
    
    log(f"      🧠 AI Vision: Batch analyzing images for {len(batch_data)} sections...")
    
    headers = {'User-Agent': 'Mozilla/5.0'}
    inputs = []
    prompt_text = "TASK: You are a Photo Editor. I have images for different sections of an article.\n\n"
    
    global_image_index = 0
    image_map = {} # لربط رقم الصورة التسلسلي بالرابط الخاص بها
    
    # 1. تجهيز الصور والنصوص
    for section_idx, data in batch_data.items():
        context = data['context']
        urls = data['urls']
        
        prompt_text += f"--- SECTION {section_idx}: {context} ---\n"
        prompt_text += f"Images for this section are indexed from {global_image_index} to {global_image_index + len(urls) - 1}.\n"
        
        for url in urls:
            try:
                r = requests.get(url, headers=headers, timeout=4)
                if r.status_code == 200:
                    # إضافة الصورة للطلب
                    inputs.append(types.Part.from_bytes(data=r.content, mime_type="image/jpeg"))
                    # حفظ الرابط في الخريطة
                    image_map[global_image_index] = url
                    global_image_index += 1
            except: 
                # إذا فشلت صورة، نتجاهلها ولا نزيد العداد
                pass
        prompt_text += "\n"

    prompt_text += """
    INSTRUCTIONS:
    - For EACH Section, select the SINGLE best image index that represents the context.
    - Return a JSON object mapping the Section ID to the selected Image Index.
    - Example: {"0": 2, "1": 5, "2": 8}
    - Return JSON ONLY.
    """
    
    # نضع النص في بداية القائمة
    inputs.insert(0, prompt_text)

    try:
        key = key_manager.get_current_key()
        client = genai.Client(api_key=key)
        
        # إرسال الطلب الضخم
        response = client.models.generate_content(model="gemini-2.5-flash", contents=inputs)
        
        # استخراج الـ JSON
        from api_manager import master_json_parser
        result = master_json_parser(response.text)
        
        final_selection = {}
        if result:
            for section_id, img_idx in result.items():
                # تحويل الإندكس المختار إلى رابط
                if int(img_idx) in image_map:
                    final_selection[int(section_id)] = image_map[int(img_idx)]
                    
        log(f"      🌟 AI Batch Selection Complete. Selected {len(final_selection)} images.")
        return final_selection

    except Exception as e:
        log(f"      ⚠️ Batch AI Selection Failed: {e}")
        return {}
        
def generate_and_upload_image(prompt_text, overlay_text=""):
    log(f"   🎨 Generating Professional AI Thumbnail for: {prompt_text[:50]}...")
    
    # --- الخلطة السرية للاحترافية ---
    style_prefix = "A high-end cinematic editorial tech photograph visualizing "
    style_suffix = (
        ". Perspective: Close-up POV shot, showing a professional human hand interacting with the subject. "
        "Strictly NO faces, NO people, NO skin beyond the hand. "
        "Style: Professional studio lighting, sharp focus, shallow depth of field, 8k resolution, "
        "realistic textures, storytelling composition, dramatic atmosphere, no text, no distorted features."
    )
    
    # دمج النص القادم من الـ AI مع القالب الاحترافي
    final_prompt_text = f"{style_prefix}'{prompt_text}'{style_suffix}"
    final_prompt = urllib.parse.quote(final_prompt_text)
    
    seed = random.randint(1, 99999)
    image_url = f"https://image.pollinations.ai/prompt/{final_prompt}?width=1280&height=720&model=flux&seed={seed}&nologo=true"
    
    try:
        r = requests.get(image_url, timeout=60)
        if r.status_code != 200: return None
        img = Image.open(BytesIO(r.content)).convert("RGBA")
        if overlay_text:
            draw = ImageDraw.Draw(img)
            try:
                font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
                if not os.path.exists(font_path): font_path = "arial.ttf"
                font = ImageFont.truetype(font_path, 80)
            except: font = ImageFont.load_default()
            text = overlay_text.upper()
            bbox = draw.textbbox((0, 0), text, font=font)
            x, y = (1280 - (bbox[2]-bbox[0]))/2, 720 - (bbox[3]-bbox[1]) - 50
            for dx in range(-4,5):
                for dy in range(-4,5): draw.text((x+dx, y+dy), text, font=font, fill="black")
            draw.text((x,y), text, font=font, fill="yellow")

        img_byte_arr = BytesIO()
        img.convert("RGB").save(img_byte_arr, format='JPEG', quality=95)
        return upload_to_github_cdn(img_byte_arr, f"ai_gen_{seed}.jpg")
    except: return None
        
        
