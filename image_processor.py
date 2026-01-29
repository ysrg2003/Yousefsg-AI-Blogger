# FILE: image_processor.py
# ROLE: Smart Image Processing (Source First -> AI Backup).

import os
import re
import requests
import random
import datetime
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from github import Github
from config import log

def upload_to_github_cdn(image_bytes, filename):
    try:
        gh_token = os.getenv('MY_GITHUB_TOKEN')
        image_repo_name = os.getenv('GITHUB_IMAGE_REPO') or os.getenv('GITHUB_REPO_NAME')
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
            else: return None
        
        return f"https://cdn.jsdelivr.net/gh/{image_repo_name}@main/{file_path}"
    except Exception as e:
        log(f"      ❌ GitHub Upload Error: {e}")
        return None

def create_overlay_image(base_img, overlay_text):
    """Adds a dark overlay and punchy text to the image."""
    try:
        # Resize to standard thumbnail size
        target_w, target_h = 1280, 720
        base_img = base_img.convert("RGBA").resize((target_w, target_h), Image.Resampling.LANCZOS)
        
        # Dark Overlay
        overlay = Image.new('RGBA', base_img.size, (0, 0, 0, 80))
        base_img = Image.alpha_composite(base_img, overlay)
        
        if overlay_text:
            draw = ImageDraw.Draw(base_img)
            try:
                font_path = "assets/Roboto-Bold.ttf"
                if not os.path.exists(font_path): font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
                font = ImageFont.truetype(font_path, 90)
            except: font = ImageFont.load_default()
            
            text = overlay_text.upper()
            bbox = draw.textbbox((0, 0), text, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            
            x = (target_w - text_w) / 2
            y = target_h - text_h - 80 # Bottom center
            
            # Text Outline
            for dx in range(-4, 5):
                for dy in range(-4, 5):
                    draw.text((x+dx, y+dy), text, font=font, fill="black")
            
            # Main Text
            draw.text((x, y), text, font=font, fill="#FFD700") # Gold color

        return base_img
    except Exception as e:
        log(f"      ⚠️ Overlay Error: {e}")
        return base_img

def process_source_image(source_url, overlay_text, title):
    """Attempts to download, edit, and upload a source image."""
    log(f"   🖼️ Attempting to use Source Image: {source_url[:50]}...")
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(source_url, headers=headers, timeout=10)
        if r.status_code != 200: return None
        
        img = Image.open(BytesIO(r.content))
        
        # Filter small images
        if img.width < 400 or img.height < 300: 
            log("      ⚠️ Source image too small. Skipping.")
            return None
            
        final_img = create_overlay_image(img, overlay_text)
        
        img_byte_arr = BytesIO()
        final_img.convert("RGB").save(img_byte_arr, format='JPEG', quality=90)
        
        safe_name = re.sub(r'[^a-zA-Z0-9]', '', title[:20]) + f"_{random.randint(100,999)}.jpg"
        return upload_to_github_cdn(img_byte_arr, safe_name)
        
    except Exception as e:
        log(f"      ❌ Source Image Processing Failed: {e}")
        return None

def generate_and_upload_image(prompt_text, overlay_text="", source_url=None, title="image"):
    # 1. Try Source Image First (If provided)
    if source_url:
        result = process_source_image(source_url, overlay_text, title)
        if result: return result
    
    # 2. Fallback to AI Generation
    log(f"   🎨 Generating AI Thumbnail (Fallback) for: {prompt_text[:30]}...")
    seed = random.randint(1, 99999)
    encoded_prompt = requests.utils.quote(f"cinematic tech photo, {prompt_text}, 8k, realistic")
    image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1280&height=720&model=flux&seed={seed}&nologo=true"
    
    try:
        r = requests.get(image_url, timeout=45)
        if r.status_code == 200:
            img = Image.open(BytesIO(r.content))
            final_img = create_overlay_image(img, overlay_text)
            
            img_byte_arr = BytesIO()
            final_img.convert("RGB").save(img_byte_arr, format='JPEG', quality=95)
            return upload_to_github_cdn(img_byte_arr, f"ai_gen_{seed}.jpg")
    except: pass
    
    return None
