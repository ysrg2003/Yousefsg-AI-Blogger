import os
import textwrap
import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import ImageClip, concatenate_videoclips, AudioFileClip

class VideoRenderer:
    def __init__(self, assets_dir='assets', output_dir='output'):
        self.assets_dir = assets_dir
        self.output_dir = output_dir
        # تحويل الدقة إلى عرضية (YouTube Standard)
        self.w, self.h = 1920, 1080 
        self.fps = 24
        
        # ألوان عالية التباين (نمط Dark Mode أو Light Mode واضح)
        self.bg_color = (240, 242, 245) # رمادي فاتح جداً (خلفية واتساب/فيسبوك)
        self.sender_color = (0, 132, 255)     # أزرق ماسنجر
        self.receiver_color = (255, 255, 255) # أبيض
        self.text_sender = (255, 255, 255)
        self.text_receiver = (0, 0, 0)
        
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(assets_dir, exist_ok=True)
        
        # تحميل الخط
        self.font_path = os.path.join(assets_dir, "Roboto-Bold.ttf")
        self._ensure_font()
        try:
            # تكبير الخط بشكل ملحوظ
            self.font_size = 70 
            self.font = ImageFont.truetype(self.font_path, self.font_size)
            self.header_font = ImageFont.truetype(self.font_path, 60)
        except:
            self.font = ImageFont.load_default()
            self.header_font = ImageFont.load_default()

        self.snd_sent = self._load_audio("send.wav")
        self.snd_recv = self._load_audio("receive.wav")

    def _ensure_font(self):
        if not os.path.exists(self.font_path):
            url = "https://github.com/google/fonts/raw/main/apache/roboto/Roboto-Bold.ttf"
            try:
                r = requests.get(url)
                with open(self.font_path, 'wb') as f:
                    f.write(r.content)
            except: pass

    def _load_audio(self, filename):
        path = os.path.join(self.assets_dir, filename)
        if os.path.exists(path): return AudioFileClip(path)
        return None

    def draw_bubble(self, draw, text, is_sender, y_pos):
        # هوامش عريضة لأن الشاشة 1920
        margin_side = 100
        padding = 50
        max_bubble_width = 1400 # الفقاعة عريضة جداً لتسهيل القراءة
        
        # حساب التفاف النص
        avg_char_width = self.font.getbbox("x")[2] if hasattr(self.font, 'getbbox') else 35
        chars_per_line = int(max_bubble_width / avg_char_width)
        lines = textwrap.wrap(text, width=chars_per_line)
        
        # حساب الارتفاع
        if hasattr(self.font, 'getbbox'):
            line_height = self.font.getbbox("Ah")[3] + 30
        else:
            line_height = 90

        box_height = (len(lines) * line_height) + (padding * 2)
        
        # حساب العرض الفعلي للنص
        text_width = 0
        for line in lines:
            if hasattr(self.font, 'getbbox'):
                bbox = self.font.getbbox(line)
                text_width = max(text_width, bbox[2])
            else:
                text_width = len(line) * avg_char_width
        
        box_width = text_width + (padding * 2)
        
        # تحديد الإحداثيات
        if is_sender:
            x1 = self.w - margin_side - box_width
            x2 = self.w - margin_side
            color = self.sender_color
            text_col = self.text_sender
        else:
            x1 = margin_side
            x2 = margin_side + box_width
            color = self.receiver_color
            text_col = self.text_receiver
            
        y1 = y_pos
        y2 = y_pos + box_height
        
        # رسم الفقاعة (مستطيل بحواف دائرية)
        draw.rectangle([x1, y1, x2, y2], fill=color, outline=(200,200,200) if not is_sender else None, width=2)
        
        # رسم النص
        curr_y = y1 + padding
        for line in lines:
            draw.text((x1 + padding, curr_y), line, font=self.font, fill=text_col)
            curr_y += line_height
            
        return box_height + 50 # ارتفاع الفقاعة + مسافة بين الفقاعات

    def create_frame(self, history, article_title):
        img = Image.new('RGB', (self.w, self.h), self.bg_color)
        draw = ImageDraw.Draw(img)
        
        # 1. رسم الرأس (Header)
        header_h = 180
        draw.rectangle([0, 0, self.w, header_h], fill=(255,255,255))
        # خط فاصل
        draw.line([(0, header_h), (self.w, header_h)], fill=(200,200,200), width=3)
        
        # كتابة العنوان في الرأس
        title_lines = textwrap.wrap(article_title, width=50)
        if title_lines:
            # نأخذ أول سطر فقط لعدم الازدحام، أو نصغره
            display_title = title_lines[0]
            if len(title_lines) > 1: display_title += "..."
            
            bbox = self.header_font.getbbox(display_title)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            draw.text(((self.w - w)/2, (header_h - h)/2), display_title, fill=(20,20,20), font=self.header_font)

        # 2. منطق التمرير (Scrolling)
        # نريد دائماً أن تكون "آخر رسالة" في منتصف الشاشة أو أسفلها قليلاً
        
        # نحسب الارتفاع الكلي لكل الرسائل
        temp_draw = ImageDraw.Draw(Image.new('RGB', (1,1)))
        bubble_heights = []
        total_h = 0
        for msg in history:
            h = self.draw_bubble(temp_draw, msg['text'], msg['is_sender'], 0)
            bubble_heights.append(h)
            total_h += h
            
        # نقطة البداية (Y) للرسم
        # نريد أن تكون نهاية آخر رسالة عند Y = 900 (تقريباً أسفل الشاشة مع هامش)
        target_bottom = 950
        start_y = header_h + 50 # الوضع الافتراضي (أول رسالة)
        
        # إذا كانت الرسائل أطول من الشاشة، نقوم بالتمرير لأعلى
        if (header_h + 50 + total_h) > target_bottom:
            start_y = target_bottom - total_h
            
        # رسم الفقاعات
        current_y = start_y
        for i, msg in enumerate(history):
            # نرسم فقط ما هو داخل حدود الشاشة (تحسين للأداء)
            if current_y + bubble_heights[i] > header_h and current_y < self.h:
                self.draw_bubble(draw, msg['text'], msg['is_sender'], current_y)
            current_y += bubble_heights[i]
            
        return np.array(img)

    def render_video(self, script_json, article_title, filename="final_video.mp4"):
        print(f"🎬 Rendering Wide Video (16:9) for: {article_title[:30]}...")
        clips = []
        history = []
        
        for idx, msg in enumerate(script_json):
            text = msg['text']
            is_sender = (msg['type'] == 'send')
            msg_obj = {'text': text, 'is_sender': is_sender}
            
            history.append(msg_obj)
            
            # إنشاء الإطار
            frame_img = self.create_frame(history, article_title)
            
            # مدة القراءة (أطول قليلاً لأن النص كبير)
            read_duration = max(3.5, len(text) * 0.12)
            
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
