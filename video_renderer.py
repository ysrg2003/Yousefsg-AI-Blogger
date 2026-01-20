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
        
        # Colors
        self.bg_color = (236, 229, 221)      # WhatsApp Beige
        self.header_color = (0, 128, 105)    # WhatsApp Green
        self.sender_bg = (220, 248, 198)     # Light Green
        self.receiver_bg = (255, 255, 255)   # White
        self.text_color = (0, 0, 0)
        self.time_color = (120, 120, 120)
        
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(assets_dir, exist_ok=True)
        
        # --- Fonts Setup (HUGE SIZE) ---
        self.font_path = os.path.join(assets_dir, "Roboto-Regular.ttf")
        self.font_bold_path = os.path.join(assets_dir, "Roboto-Bold.ttf")
        self._ensure_fonts()
        
        try:
            # تكبير الخط بشكل هائل
            self.font_size = 90 
            self.font = ImageFont.truetype(self.font_path, self.font_size)
            self.header_font = ImageFont.truetype(self.font_bold_path, 60)
            self.sub_header_font = ImageFont.truetype(self.font_path, 40)
            self.time_font = ImageFont.truetype(self.font_path, 35)
        except:
            self.font = ImageFont.load_default()
            self.header_font = ImageFont.load_default()
            self.sub_header_font = ImageFont.load_default()
            self.time_font = ImageFont.load_default()

        self.snd_sent = self._load_audio("send.wav")
        self.snd_recv = self._load_audio("receive.wav")

    def _ensure_fonts(self):
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
        header_h = 180
        draw.rectangle([0, 0, self.w, header_h], fill=self.header_color)
        
        # Profile Pic
        profile_x, profile_y = 130, 90
        r = 60
        draw.ellipse([profile_x-r, profile_y-r, profile_x+r, profile_y+r], fill=(210, 210, 210))
        draw.ellipse([profile_x-25, profile_y-25, profile_x+25, profile_y], fill=(255, 255, 255))
        draw.pieslice([profile_x-35, profile_y+10, profile_x+35, profile_y+80], 180, 360, fill=(255, 255, 255))

        # Back Arrow
        arrow_x, arrow_y = 40, 90
        draw.line([(arrow_x, arrow_y), (arrow_x+25, arrow_y-25)], fill="white", width=6)
        draw.line([(arrow_x, arrow_y), (arrow_x+25, arrow_y+25)], fill="white", width=6)
        draw.line([(arrow_x, arrow_y), (arrow_x+50, arrow_y)], fill="white", width=6)

        # Name & Status
        text_x = 220
        draw.text((text_x, 50), title[:20], font=self.header_font, fill="white")
        draw.text((text_x, 120), "Online", font=self.sub_header_font, fill="white")
        
        return header_h

    def calculate_bubble_height(self, text):
        max_width = 1500 # عرض الفقاعة الأقصى
        padding_y = 40
        
        avg_char_width = self.font.getbbox("x")[2] if hasattr(self.font, 'getbbox') else 45
        chars_per_line = int(max_width / avg_char_width)
        lines = textwrap.wrap(text, width=chars_per_line)
        
        if hasattr(self.font, 'getbbox'):
            line_height = self.font.getbbox("Ah")[3] + 30
        else:
            line_height = 110

        text_height = len(lines) * line_height
        return text_height + (padding_y * 2) + 40 # +40 للتوقيت

    def draw_bubble(self, draw, text, is_sender, y_pos, time_str):
        max_width = 1500
        padding_x = 50
        padding_y = 40
        
        avg_char_width = self.font.getbbox("x")[2] if hasattr(self.font, 'getbbox') else 45
        chars_per_line = int(max_width / avg_char_width)
        lines = textwrap.wrap(text, width=chars_per_line)
        
        if hasattr(self.font, 'getbbox'):
            line_height = self.font.getbbox("Ah")[3] + 30
        else:
            line_height = 110

        # حساب عرض الفقاعة
        max_line_w = 0
        for line in lines:
            bbox = self.font.getbbox(line)
            max_line_w = max(max_line_w, bbox[2])
        
        box_width = max_line_w + (padding_x * 2)
        if box_width < 250: box_width = 250 # حد أدنى للعرض

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
        
        # رسم الظل الخفيف
        draw.rounded_rectangle([x1+5, y1+5, x2+5, y2+5], radius=35, fill=(200,200,200))
        # رسم الفقاعة
        draw.rounded_rectangle([x1, y1, x2, y2], radius=35, fill=bg)
        
        # رسم النص
        curr_y = y1 + padding_y
        for line in lines:
            draw.text((x1 + padding_x, curr_y), line, font=self.font, fill="black")
            curr_y += line_height
            
        # رسم التوقيت
        time_w = self.time_font.getbbox(time_str)[2]
        time_x = x2 - time_w - 30
        time_y = y2 - 50
        draw.text((time_x, time_y), time_str, font=self.time_font, fill=self.time_color)
        
        if is_sender:
            # صحين زرق
            tick_x = time_x - 40
            draw.line([(tick_x, time_y+20), (tick_x+10, time_y+30), (tick_x+25, time_y+10)], fill="#34B7F1", width=4)
            draw.line([(tick_x+12, time_y+20), (tick_x+22, time_y+30), (tick_x+37, time_y+10)], fill="#34B7F1", width=4)

        return box_height

    def create_frame(self, history, article_title):
        img = Image.new('RGB', (self.w, self.h), self.bg_color)
        draw = ImageDraw.Draw(img)
        
        # 1. حساب ارتفاعات جميع الرسائل في التاريخ
        # نحتاج هذا لنعرف أين نضع الرسالة الأخيرة
        bubble_heights = []
        spacing = 40 # مسافة بين الفقاعات
        
        for msg in history:
            h = self.calculate_bubble_height(msg['text'])
            bubble_heights.append(h)
            
        # 2. تحديد مكان الرسالة الأخيرة (The Anchor)
        # نريد أن تكون نهاية الرسالة الأخيرة عند Y = 950 (أسفل الشاشة)
        bottom_anchor = self.h - 100
        
        # 3. الرسم من الأسفل إلى الأعلى (Backwards Drawing Logic)
        # نبدأ من آخر رسالة ونضعها في الأسفل، ثم نحسب مكان التي قبلها فوقها وهكذا
        
        # عكس القوائم للحساب من الأسفل
        reversed_history = list(reversed(history))
        reversed_heights = list(reversed(bubble_heights))
        
        current_bottom_y = bottom_anchor
        
        # قائمة لتخزين إحداثيات الرسم الصحيحة (سنعيد عكسها للرسم)
        draw_queue = [] 
        
        base_time = datetime.datetime(2024, 1, 1, 10, 0)
        total_msgs = len(history)

        for i, msg in enumerate(reversed_history):
            h = reversed_heights[i]
            top_y = current_bottom_y - h
            
            # حساب الوقت (بناءً على الفهرس الأصلي)
            original_index = total_msgs - 1 - i
            msg_time = base_time + datetime.timedelta(minutes=original_index*2)
            time_str = msg_time.strftime("%I:%M %p")
            
            # نضيف للأوامر
            draw_queue.append({
                "text": msg['text'],
                "is_sender": msg['is_sender'],
                "y": top_y,
                "time": time_str
            })
            
            # تحديث النقطة السفلية للرسالة التالية (التي هي السابقة زمنياً)
            current_bottom_y = top_y - spacing
            
            # إذا خرجنا عن الشاشة من الأعلى بكثير، نتوقف عن الحساب
            if current_bottom_y < -500:
                break
        
        # 4. تنفيذ الرسم (Draw Messages)
        # نرسم الرسائل أولاً
        for item in reversed(draw_queue): # نعيد الترتيب للرسم الصحيح
            self.draw_bubble(draw, item['text'], item['is_sender'], item['y'], item['time'])
            
        # 5. رسم الهيدر (Header) في النهاية
        # هذا هو السر! نرسم الهيدر فوق كل شيء ليغطي أي رسالة تصعد تحته
        self.draw_whatsapp_header(draw, article_title)
            
        return np.array(img)

    def render_video(self, script_json, article_title, filename="final_video.mp4"):
        print(f"🎬 Rendering Fixed WhatsApp Video for: {article_title[:30]}...")
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
            read_duration = max(3.0, len(text) * 0.13)
            
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
