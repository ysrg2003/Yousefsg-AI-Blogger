import os
import textwrap
import numpy as np
import requests
import datetime
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import ImageClip, concatenate_videoclips, AudioFileClip

class VideoRenderer:
    def __init__(self, assets_dir='assets', output_dir='output'):
        self.assets_dir = assets_dir
        self.output_dir = output_dir
        self.w, self.h = 1920, 1080 
        self.fps = 24
        
        # --- WhatsApp Colors ---
        self.bg_color = (236, 229, 221)      # WhatsApp Beige Background
        self.header_color = (0, 128, 105)    # WhatsApp Teal Green
        self.sender_bg = (220, 248, 198)     # Light Green Bubble
        self.receiver_bg = (255, 255, 255)   # White Bubble
        self.text_color = (0, 0, 0)
        self.time_color = (153, 153, 153)
        self.name_color = (255, 255, 255)
        
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(assets_dir, exist_ok=True)
        
        # --- Fonts ---
        self.font_path = os.path.join(assets_dir, "Roboto-Regular.ttf")
        self.font_bold_path = os.path.join(assets_dir, "Roboto-Bold.ttf")
        self._ensure_fonts()
        
        try:
            self.font_size = 65 # خط كبير جداً
            self.font = ImageFont.truetype(self.font_path, self.font_size)
            self.header_font = ImageFont.truetype(self.font_bold_path, 55)
            self.sub_header_font = ImageFont.truetype(self.font_path, 35)
            self.time_font = ImageFont.truetype(self.font_path, 30)
        except:
            self.font = ImageFont.load_default()
            self.header_font = ImageFont.load_default()
            self.sub_header_font = ImageFont.load_default()
            self.time_font = ImageFont.load_default()

        self.snd_sent = self._load_audio("send.wav")
        self.snd_recv = self._load_audio("receive.wav")

    def _ensure_fonts(self):
        # تحميل خطوط روبوتو لضمان الشكل الأصلي
        urls = {
            self.font_path: "https://github.com/google/fonts/raw/main/apache/roboto/Roboto-Regular.ttf",
            self.font_bold_path: "https://github.com/google/fonts/raw/main/apache/roboto/Roboto-Bold.ttf"
        }
        for path, url in urls.items():
            if not os.path.exists(path):
                try:
                    r = requests.get(url)
                    with open(path, 'wb') as f:
                        f.write(r.content)
                except: pass

    def _load_audio(self, filename):
        path = os.path.join(self.assets_dir, filename)
        if os.path.exists(path): return AudioFileClip(path)
        return None

    def draw_whatsapp_header(self, draw, title):
        # رسم الشريط الأخضر
        header_h = 160
        draw.rectangle([0, 0, self.w, header_h], fill=self.header_color)
        
        # رسم دائرة البروفايل (وهمية)
        profile_x, profile_y = 120, 80
        r = 50
        draw.ellipse([profile_x-r, profile_y-r, profile_x+r, profile_y+r], fill=(200, 200, 200))
        # أيقونة شخص بسيطة
        draw.ellipse([profile_x-20, profile_y-20, profile_x+20, profile_y], fill=(255, 255, 255))
        draw.pieslice([profile_x-30, profile_y+10, profile_x+30, profile_y+70], 180, 360, fill=(255, 255, 255))

        # زر الرجوع (سهم)
        arrow_x, arrow_y = 40, 80
        draw.line([(arrow_x, arrow_y), (arrow_x+20, arrow_y-20)], fill="white", width=5)
        draw.line([(arrow_x, arrow_y), (arrow_x+20, arrow_y+20)], fill="white", width=5)
        draw.line([(arrow_x, arrow_y), (arrow_x+40, arrow_y)], fill="white", width=5)

        # الاسم
        text_x = 200
        draw.text((text_x, 45), title[:25], font=self.header_font, fill="white")
        draw.text((text_x, 105), "Online", font=self.sub_header_font, fill="white")
        
        # أيقونات القائمة (ثلاث نقاط)
        dots_x = self.w - 50
        draw.ellipse([dots_x-5, 60-5, dots_x+5, 60+5], fill="white")
        draw.ellipse([dots_x-5, 80-5, dots_x+5, 80+5], fill="white")
        draw.ellipse([dots_x-5, 100-5, dots_x+5, 100+5], fill="white")
        
        return header_h

    def draw_bubble(self, draw, text, is_sender, y_pos, time_str="10:30 PM"):
        # إعدادات الفقاعة
        max_width = 1400
        padding_x = 40
        padding_y = 30
        
        # التفاف النص
        avg_char_width = self.font.getbbox("x")[2] if hasattr(self.font, 'getbbox') else 35
        chars_per_line = int(max_width / avg_char_width)
        lines = textwrap.wrap(text, width=chars_per_line)
        
        # حساب الأبعاد
        if hasattr(self.font, 'getbbox'):
            line_height = self.font.getbbox("Ah")[3] + 25
        else:
            line_height = 80

        text_height = len(lines) * line_height
        box_height = text_height + (padding_y * 2) + 30 # +30 للتوقيت
        
        # حساب عرض الفقاعة بناءً على أطول سطر
        max_line_w = 0
        for line in lines:
            bbox = self.font.getbbox(line)
            max_line_w = max(max_line_w, bbox[2])
        
        box_width = max_line_w + (padding_x * 2)
        # تأكد أن العرض يكفي للتوقيت
        if box_width < 200: box_width = 200

        # الإحداثيات
        margin_side = 50
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
        
        # رسم الفقاعة (مستطيل بحواف دائرية)
        draw.rounded_rectangle([x1, y1, x2, y2], radius=30, fill=bg)
        
        # رسم "الذيل" (Tail) الصغير للفقاعة
        if is_sender:
            draw.polygon([(x2, y1), (x2+20, y1), (x2, y1+20)], fill=bg)
        else:
            draw.polygon([(x1, y1), (x1-20, y1), (x1, y1+20)], fill=bg)

        # رسم النص
        curr_y = y1 + padding_y
        for line in lines:
            draw.text((x1 + padding_x, curr_y), line, font=self.font, fill="black")
            curr_y += line_height
            
        # رسم التوقيت وعلامة الصح
        time_w = self.time_font.getbbox(time_str)[2]
        time_x = x2 - time_w - 20
        time_y = y2 - 45
        draw.text((time_x, time_y), time_str, font=self.time_font, fill=self.time_color)
        
        if is_sender:
            # رسم صحين زرق (Blue Ticks)
            tick_x = time_x - 35
            # الصح الأول
            draw.line([(tick_x, time_y+15), (tick_x+5, time_y+20), (tick_x+15, time_y+5)], fill="#34B7F1", width=3)
            # الصح الثاني
            draw.line([(tick_x+8, time_y+15), (tick_x+13, time_y+20), (tick_x+23, time_y+5)], fill="#34B7F1", width=3)

        return box_height + 40 # المسافة بين الفقاعات

    def create_frame(self, history, article_title):
        img = Image.new('RGB', (self.w, self.h), self.bg_color)
        draw = ImageDraw.Draw(img)
        
        # 1. رسم الهيدر
        header_h = self.draw_whatsapp_header(draw, "Tech News Update") # اسم ثابت أو عنوان المقال
        
        # 2. حساب الارتفاعات للتمرير (Scrolling)
        temp_draw = ImageDraw.Draw(Image.new('RGB', (1,1)))
        bubble_heights = []
        total_h = 0
        
        # محاكاة التوقيت
        base_time = datetime.datetime(2024, 1, 1, 10, 0)
        
        for i, msg in enumerate(history):
            msg_time = base_time + datetime.timedelta(minutes=i*2)
            time_str = msg_time.strftime("%I:%M %p")
            h = self.draw_bubble(temp_draw, msg['text'], msg['is_sender'], 0, time_str)
            bubble_heights.append(h)
            total_h += h
            
        # 3. تحديد نقطة البداية (Y)
        # نريد آخر رسالة تكون ظاهرة فوق الكيبورد الوهمي (أو أسفل الشاشة)
        target_bottom = self.h - 50
        start_y = header_h + 30
        
        if (start_y + total_h) > target_bottom:
            start_y = target_bottom - total_h
            
        # 4. رسم الفقاعات
        current_y = start_y
        for i, msg in enumerate(history):
            msg_time = base_time + datetime.timedelta(minutes=i*2)
            time_str = msg_time.strftime("%I:%M %p")
            
            # رسم فقط ما هو داخل الشاشة
            if current_y + bubble_heights[i] > header_h and current_y < self.h:
                self.draw_bubble(draw, msg['text'], msg['is_sender'], current_y, time_str)
            current_y += bubble_heights[i]
            
        return np.array(img)

    def render_video(self, script_json, article_title, filename="final_video.mp4"):
        print(f"🎬 Rendering WhatsApp Style Video for: {article_title[:30]}...")
        clips = []
        history = []
        
        for idx, msg in enumerate(script_json):
            text = msg['text']
            is_sender = (msg['type'] == 'send')
            msg_obj = {'text': text, 'is_sender': is_sender}
            
            history.append(msg_obj)
            
            # إنشاء الإطار
            frame_img = self.create_frame(history, article_title)
            
            # مدة القراءة
            read_duration = max(2.5, len(text) * 0.12)
            
            clip_main = ImageClip(frame_img).set_duration(read_duration)
            
            sound = self.snd_sent if is_sender else self.snd_recv
            if sound:
                clip_main = clip_main.set_audio(sound)
                
            clips.append(clip_main)
            
        if not clips: return None

        final_clip = concatenate_videoclips(clips, method="compose")
        output_path = os.path.join(self.output_dir, filename)
        
        final_clip.write_videofile(output_path, fps=self.fps, codec='libx264', audio_codec='aac', logger=None)
        print(f"✅ Video Rendered: {output_path}")
        return output_path
