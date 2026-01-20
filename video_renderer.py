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
        # دقة Full HD عرضية
        self.w, self.h = 1920, 1080 
        self.fps = 24
        
        # ألوان عالية التباين جداً للقراءة في 144p
        self.bg_color = (255, 255, 255) 
        self.sender_color = (0, 100, 255)     # أزرق قوي
        self.receiver_color = (230, 230, 230) # رمادي فاتح
        self.text_sender = (255, 255, 255)
        self.text_receiver = (0, 0, 0)
        
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(assets_dir, exist_ok=True)
        
        # تحميل الخط
        self.font_path = os.path.join(assets_dir, "Roboto-Bold.ttf")
        self._ensure_font()
        try:
            # خط ضخم جداً (Huge Font)
            self.font_size = 90 
            self.font = ImageFont.truetype(self.font_path, self.font_size)
            self.header_font = ImageFont.truetype(self.font_path, 50)
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
        # هوامش جانبية
        margin_side = 50
        padding = 60 # حشوة كبيرة
        max_bubble_width = 1600 # استغلال كامل عرض الشاشة تقريباً
        
        # حساب التفاف النص
        avg_char_width = self.font.getbbox("x")[2] if hasattr(self.font, 'getbbox') else 45
        chars_per_line = int(max_bubble_width / avg_char_width)
        lines = textwrap.wrap(text, width=chars_per_line)
        
        # حساب الارتفاع
        if hasattr(self.font, 'getbbox'):
            line_height = self.font.getbbox("Ah")[3] + 40
        else:
            line_height = 110

        box_height = (len(lines) * line_height) + (padding * 2)
        
        # حساب العرض الفعلي
        text_width = 0
        for line in lines:
            if hasattr(self.font, 'getbbox'):
                bbox = self.font.getbbox(line)
                text_width = max(text_width, bbox[2])
            else:
                text_width = len(line) * avg_char_width
        
        box_width = text_width + (padding * 2)
        
        # تحديد المكان (يمين أو يسار)
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
        
        # رسم الفقاعة
        draw.rectangle([x1, y1, x2, y2], fill=color, outline=None)
        
        # رسم النص
        curr_y = y1 + padding
        for line in lines:
            draw.text((x1 + padding, curr_y), line, font=self.font, fill=text_col)
            curr_y += line_height
            
        return box_height

    def create_frame(self, current_msg, article_title):
        """
        يرسم إطاراً يركز فقط على الرسالة الحالية لتكون ضخمة وواضحة.
        """
        img = Image.new('RGB', (self.w, self.h), self.bg_color)
        draw = ImageDraw.Draw(img)
        
        # 1. رسم الرأس (Header)
        header_h = 150
        draw.rectangle([0, 0, self.w, header_h], fill=(240,240,240))
        draw.line([(0, header_h), (self.w, header_h)], fill=(200,200,200), width=2)
        
        # عنوان المقال في الأعلى
        title_short = article_title[:60] + "..." if len(article_title) > 60 else article_title
        bbox = self.header_font.getbbox(title_short)
        w = bbox[2] - bbox[0]
        draw.text(((self.w - w)/2, 50), title_short, fill=(50,50,50), font=self.header_font)

        # 2. رسم الرسالة الحالية في المنتصف تماماً
        # نحسب ارتفاعها أولاً لتوسيطها عمودياً
        temp_draw = ImageDraw.Draw(Image.new('RGB', (1,1)))
        msg_h = self.draw_bubble(temp_draw, current_msg['text'], current_msg['is_sender'], 0)
        
        # حساب نقطة البداية لتكون في منتصف الشاشة (تحت الهيدر)
        available_h = self.h - header_h
        start_y = header_h + (available_h - msg_h) // 2
        
        # رسم الرسالة
        self.draw_bubble(draw, current_msg['text'], current_msg['is_sender'], start_y)
            
        return np.array(img)

    def render_video(self, script_json, article_title, filename="final_video.mp4"):
        print(f"🎬 Rendering Huge Text Video for: {article_title[:30]}...")
        clips = []
        
        for idx, msg in enumerate(script_json):
            text = msg['text']
            is_sender = (msg['type'] == 'send')
            msg_obj = {'text': text, 'is_sender': is_sender}
            
            # إنشاء الإطار (نمرر الرسالة الحالية فقط للتركيز عليها)
            frame_img = self.create_frame(msg_obj, article_title)
            
            # مدة القراءة (أطول قليلاً للتركيز)
            # معادلة: 2 ثانية كحد أدنى + 0.15 ثانية لكل حرف
            read_duration = max(2.5, len(text) * 0.15)
            
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
