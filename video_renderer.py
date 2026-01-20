import os
import textwrap
import numpy as np
import requests
import datetime
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageOps
from moviepy.editor import ImageClip, concatenate_videoclips, AudioFileClip

class VideoRenderer:
    def __init__(self, assets_dir='assets', output_dir='output'):
        self.assets_dir = assets_dir
        self.output_dir = output_dir
        self.w, self.h = 1920, 1080 
        self.fps = 24
        
        # Colors
        self.bg_color = (236, 229, 221)      
        self.header_color = (0, 128, 105)    
        self.sender_bg = (220, 248, 198)     
        self.receiver_bg = (255, 255, 255)   
        self.text_color = (0, 0, 0)
        self.time_color = (120, 120, 120)
        
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(assets_dir, exist_ok=True)
        
        # --- 1. تحميل الخطوط (الحل الجذري) ---
        # نحاول استخدام خطوط النظام في لينكس (GitHub Actions) مباشرة
        # هذا يمنع المشكلة التي تجعل الخط يعود للحجم الصغير
        self.font = self._load_best_font(100) # حجم ضخم 100
        self.header_font = self._load_best_font(60)
        self.sub_header_font = self._load_best_font(40)
        self.time_font = self._load_best_font(35)

        # --- 2. تحميل صورة البروفايل ---
        self.profile_pic = self._load_profile_image("https://blogger.googleusercontent.com/img/a/AVvXsEiBbaQkbZWlda1fzUdjXD69xtyL8TDw44wnUhcPI_l2drrbyNq-Bd9iPcIdOCUGbonBc43Ld8vx4p7Zo0DxsM63TndOywKpXdoPINtGT7_S3vfBOsJVR5AGZMoE8CJyLMKo8KUi4iKGdI023U9QLqJNkxrBxD_bMVDpHByG2wDx_gZEFjIGaYHlXmEdZ14=s791")

        self.snd_sent = self._load_audio("send.wav")
        self.snd_recv = self._load_audio("receive.wav")

    def _load_best_font(self, size):
        """يحاول العثور على أفضل خط متاح في النظام لتجنب الخط الافتراضي الصغير."""
        font_candidates = [
            # مسارات خطوط لينكس (Ubuntu/GitHub Actions)
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
            # مسار محلي احتياطي
            os.path.join(self.assets_dir, "Roboto-Bold.ttf")
        ]
        
        for path in font_candidates:
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size)
                except: continue
        
        # محاولة أخيرة لتحميل روبوتو من النت إذا لم نجد شيئاً
        try:
            font_path = os.path.join(self.assets_dir, "Roboto-Bold.ttf")
            if not os.path.exists(font_path):
                url = "https://github.com/google/fonts/raw/main/apache/roboto/Roboto-Bold.ttf"
                r = requests.get(url)
                with open(font_path, 'wb') as f: f.write(r.content)
            return ImageFont.truetype(font_path, size)
        except:
            print("⚠️ WARNING: Using default font! Text will be tiny.")
            return ImageFont.load_default()

    def _load_profile_image(self, url):
        """تحميل وقص صورة البروفايل كدائرة."""
        try:
            response = requests.get(url)
            img = Image.open(BytesIO(response.content)).convert("RGBA")
            
            # تغيير الحجم
            size = (120, 120)
            img = img.resize(size, Image.LANCZOS)
            
            # عمل قناع دائري
            mask = Image.new('L', size, 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0) + size, fill=255)
            
            output = ImageOps.fit(img, mask.size, centering=(0.5, 0.5))
            output.putalpha(mask)
            return output
        except Exception as e:
            print(f"⚠️ Failed to load profile pic: {e}")
            return None

    def _load_audio(self, filename):
        path = os.path.join(self.assets_dir, filename)
        if os.path.exists(path): return AudioFileClip(path)
        return None

    def draw_whatsapp_header(self, draw, title, base_img):
        # رسم الخلفية الخضراء
        header_h = 180
        draw.rectangle([0, 0, self.w, header_h], fill=self.header_color)
        
        # رسم صورة البروفايل
        if self.profile_pic:
            # لصق الصورة (نحتاج للصقها على الـ Base Image لأن Draw لا يدعم لصق الصور)
            base_img.paste(self.profile_pic, (130, 30), self.profile_pic)
        else:
            # رسم دائرة بديلة إذا فشل التحميل
            draw.ellipse([130, 30, 250, 150], fill=(200, 200, 200))

        # زر الرجوع
        arrow_x, arrow_y = 40, 90
        draw.line([(arrow_x, arrow_y), (arrow_x+25, arrow_y-25)], fill="white", width=6)
        draw.line([(arrow_x, arrow_y), (arrow_x+25, arrow_y+25)], fill="white", width=6)
        draw.line([(arrow_x, arrow_y), (arrow_x+50, arrow_y)], fill="white", width=6)

        # الاسم والحالة
        text_x = 270
        draw.text((text_x, 50), title[:20], font=self.header_font, fill="white")
        draw.text((text_x, 120), "Online", font=self.sub_header_font, fill="white")
        
        return header_h

    def calculate_bubble_height(self, text):
        max_width = 1500 
        padding_y = 40
        
        # استخدام دالة getbbox بأمان
        try:
            avg_char_width = self.font.getbbox("x")[2]
            line_height = self.font.getbbox("Ah")[3] + 30
        except:
            avg_char_width = 50 # قيمة تقريبية للخط الكبير
            line_height = 120

        chars_per_line = int(max_width / avg_char_width)
        lines = textwrap.wrap(text, width=chars_per_line)
        
        text_height = len(lines) * line_height
        return text_height + (padding_y * 2) + 40 

    def draw_bubble(self, draw, text, is_sender, y_pos, time_str):
        max_width = 1500
        padding_x = 50
        padding_y = 40
        
        try:
            avg_char_width = self.font.getbbox("x")[2]
            line_height = self.font.getbbox("Ah")[3] + 30
        except:
            avg_char_width = 50
            line_height = 120

        chars_per_line = int(max_width / avg_char_width)
        lines = textwrap.wrap(text, width=chars_per_line)
        
        # حساب العرض
        max_line_w = 0
        for line in lines:
            try:
                bbox = self.font.getbbox(line)
                max_line_w = max(max_line_w, bbox[2])
            except:
                max_line_w = len(line) * avg_char_width
        
        box_width = max_line_w + (padding_x * 2)
        if box_width < 300: box_width = 300

        box_height = (len(lines) * line_height) + (padding_y * 2) + 40

        # الإحداثيات
        margin_side = 60
        if is_sender:
            x1 = self.w - margin_side - box_width
            x2 = self.w - margin_side
            bg = self.sender_bg
        else:
            x1 = margin_side
            x2 = margin_side + box_width
            bg = self.receiver_bg
            
        y1 = y_pos
        y2 = y_pos + box_height
        
        # رسم الفقاعة
        draw.rounded_rectangle([x1, y1, x2, y2], radius=35, fill=bg)
        
        # رسم النص
        curr_y = y1 + padding_y
        for line in lines:
            draw.text((x1 + padding_x, curr_y), line, font=self.font, fill="black")
            curr_y += line_height
            
        # رسم التوقيت
        try:
            time_w = self.time_font.getbbox(time_str)[2]
        except:
            time_w = 100
            
        time_x = x2 - time_w - 30
        time_y = y2 - 50
        draw.text((time_x, time_y), time_str, font=self.time_font, fill=self.time_color)
        
        if is_sender:
            tick_x = time_x - 40
            draw.line([(tick_x, time_y+20), (tick_x+10, time_y+30), (tick_x+25, time_y+10)], fill="#34B7F1", width=4)
            draw.line([(tick_x+12, time_y+20), (tick_x+22, time_y+30), (tick_x+37, time_y+10)], fill="#34B7F1", width=4)

        return box_height

    def create_frame(self, history, article_title):
        img = Image.new('RGBA', (self.w, self.h), self.bg_color) # RGBA للصق الصورة
        draw = ImageDraw.Draw(img)
        
        # 1. حساب الارتفاعات
        bubble_heights = []
        spacing = 40
        for msg in history:
            h = self.calculate_bubble_height(msg['text'])
            bubble_heights.append(h)
            
        # 2. منطق التموضع (من الأسفل للأعلى)
        bottom_anchor = self.h - 100
        reversed_history = list(reversed(history))
        reversed_heights = list(reversed(bubble_heights))
        
        current_bottom_y = bottom_anchor
        draw_queue = [] 
        
        base_time = datetime.datetime(2024, 1, 1, 10, 0)
        total_msgs = len(history)

        for i, msg in enumerate(reversed_history):
            h = reversed_heights[i]
            top_y = current_bottom_y - h
            
            original_index = total_msgs - 1 - i
            msg_time = base_time + datetime.timedelta(minutes=original_index*2)
            time_str = msg_time.strftime("%I:%M %p")
            
            draw_queue.append({
                "text": msg['text'],
                "is_sender": msg['is_sender'],
                "y": top_y,
                "time": time_str
            })
            
            current_bottom_y = top_y - spacing
            if current_bottom_y < -500: break
        
        # 3. رسم الرسائل
        for item in reversed(draw_queue):
            self.draw_bubble(draw, item['text'], item['is_sender'], item['y'], item['time'])
            
        # 4. رسم الهيدر (فوق الرسائل)
        self.draw_whatsapp_header(draw, article_title, img)
            
        return np.array(img.convert("RGB"))

    def render_video(self, script_json, article_title, filename="final_video.mp4"):
        print(f"🎬 Rendering Video (System Fonts) for: {article_title[:30]}...")
        clips = []
        history = []
        
        for idx, msg in enumerate(script_json):
            text = msg['text']
            is_sender = (msg['type'] == 'send')
            msg_obj = {'text': text, 'is_sender': is_sender}
            history.append(msg_obj)
            
            frame_img = self.create_frame(history, article_title)
            read_duration = max(3.0, len(text) * 0.13)
            
            clip_main = ImageClip(frame_img).set_duration(read_duration)
            
            sound = self.snd_sent if is_sender else self.snd_recv
            if sound: clip_main = clip_main.set_audio(sound)
                
            clips.append(clip_main)
            
        if not clips: return None

        final_clip = concatenate_videoclips(clips, method="compose")
        output_path = os.path.join(self.output_dir, filename)
        final_clip.write_videofile(output_path, fps=self.fps, codec='libx264', audio_codec='aac', logger=None)
        print(f"✅ Video Rendered: {output_path}")
        return output_path
