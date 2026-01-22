import os
import textwrap
import numpy as np
import requests
import datetime
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageOps
from moviepy.editor import ImageClip, concatenate_videoclips, AudioFileClip

class VideoRenderer:
    def __init__(self, assets_dir='assets', output_dir='output', width=1920, height=1080):
        self.assets_dir = assets_dir
        self.output_dir = output_dir
        self.w = width
        self.h = height
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
        
        base_font_size = 90 if self.w > 1500 else 60 
        
        self.font = self._load_best_font(base_font_size)
        self.header_font = self._load_best_font(int(base_font_size * 0.6))
        self.sub_header_font = self._load_best_font(int(base_font_size * 0.4))
        self.time_font = self._load_best_font(int(base_font_size * 0.35))

        self.profile_pic = self._load_profile_image("https://blogger.googleusercontent.com/img/a/AVvXsEiBbaQkbZWlda1fzUdjXD69xtyL8TDw44wnUhcPI_l2drrbyNq-Bd9iPcIdOCUGbonBc43Ld8vx4p7Zo0DxsM63TndOywKpXdoPINtGT7_S3vfBOsJVR5AGZMoE8CJyLMKo8KUi4iKGdI023U9QLqJNkxrBxD_bMVDpHByG2wDx_gZEFjIGaYHlXmEdZ14=s791")

        # ✅ FIX: Download Audio Assets Automatically
        self.snd_sent = self._load_or_download_audio("send.wav", "https://github.com/adephagia/whatsapp-web-sound/raw/master/src/assets/sent.mp3")
        self.snd_recv = self._load_or_download_audio("receive.wav", "https://github.com/adephagia/whatsapp-web-sound/raw/master/src/assets/received.mp3")

    def _load_best_font(self, size):
        font_path = os.path.join(self.assets_dir, "Roboto-Bold.ttf")
        if not os.path.exists(font_path):
            try:
                url = "https://github.com/google/fonts/raw/main/apache/roboto/Roboto-Bold.ttf"
                r = requests.get(url)
                with open(font_path, 'wb') as f: f.write(r.content)
            except: pass
        
        try: return ImageFont.truetype(font_path, size)
        except: return ImageFont.load_default()

    def _load_profile_image(self, url):
        try:
            response = requests.get(url)
            img = Image.open(BytesIO(response.content)).convert("RGBA")
            size = (120, 120)
            img = img.resize(size, Image.LANCZOS)
            mask = Image.new('L', size, 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0) + size, fill=255)
            output = ImageOps.fit(img, mask.size, centering=(0.5, 0.5))
            output.putalpha(mask)
            return output
        except: return None

    # ✅ FIX: Audio Downloader
    def _load_or_download_audio(self, filename, url):
        path = os.path.join(self.assets_dir, filename)
        if not os.path.exists(path):
            print(f"   ⬇️ Downloading missing audio: {filename}...")
            try:
                r = requests.get(url)
                with open(path, 'wb') as f: f.write(r.content)
            except Exception as e:
                print(f"   ⚠️ Could not download audio: {e}")
                return None
        try:
            return AudioFileClip(path)
        except: return None

    def draw_whatsapp_header(self, draw, title, base_img):
        header_h = 180
        draw.rectangle([0, 0, self.w, header_h], fill=self.header_color)
        
        if self.profile_pic:
            base_img.paste(self.profile_pic, (130, 30), self.profile_pic)
        else:
            draw.ellipse([130, 30, 250, 150], fill=(200, 200, 200))

        arrow_x, arrow_y = 40, 90
        draw.line([(arrow_x, arrow_y), (arrow_x+25, arrow_y-25)], fill="white", width=6)
        draw.line([(arrow_x, arrow_y), (arrow_x+25, arrow_y+25)], fill="white", width=6)
        draw.line([(arrow_x, arrow_y), (arrow_x+50, arrow_y)], fill="white", width=6)

        text_x = 270
        max_chars = 22 if self.w < 1500 else 40
        display_title = title[:max_chars] + "..." if len(title) > max_chars else title
        
        draw.text((text_x, 50), display_title, font=self.header_font, fill="white")
        draw.text((text_x, 120), "Online", font=self.sub_header_font, fill="white")
        return header_h

    def calculate_bubble_height(self, text):
        max_width = int(self.w * 0.75) 
        padding_y = 40
        try:
            line_height = self.font.getbbox("Ah")[3] + 30
            avg_char_width = self.font.getbbox("x")[2]
        except:
            line_height = 100
            avg_char_width = 40

        chars_per_line = int(max_width / avg_char_width)
        lines = textwrap.wrap(text, width=chars_per_line)
        return (len(lines) * line_height) + (padding_y * 2) + 40 

    def draw_bubble(self, draw, text, is_sender, y_pos, time_str):
        max_width = int(self.w * 0.75)
        padding_x = 50
        padding_y = 40
        
        try:
            line_height = self.font.getbbox("Ah")[3] + 30
            avg_char_width = self.font.getbbox("x")[2]
        except:
            line_height = 100
            avg_char_width = 40

        chars_per_line = int(max_width / avg_char_width)
        lines = textwrap.wrap(text, width=chars_per_line)
        
        max_line_w = 0
        for line in lines:
            try:
                bbox = self.font.getbbox(line)
                max_line_w = max(max_line_w, bbox[2])
            except:
                max_line_w = len(line) * avg_char_width
        
        box_width = max_line_w + (padding_x * 2)
        if box_width < 250: box_width = 250

        box_height = (len(lines) * line_height) + (padding_y * 2) + 40

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
        
        draw.rounded_rectangle([x1+5, y1+5, x2+5, y2+5], radius=35, fill=(200,200,200))
        draw.rounded_rectangle([x1, y1, x2, y2], radius=35, fill=bg)
        
        curr_y = y1 + padding_y
        for line in lines:
            draw.text((x1 + padding_x, curr_y), line, font=self.font, fill="black")
            curr_y += line_height
            
        try: time_w = self.time_font.getbbox(time_str)[2]
        except: time_w = 100
            
        time_x = x2 - time_w - 30
        time_y = y2 - 50
        draw.text((time_x, time_y), time_str, font=self.time_font, fill=self.time_color)
        
        if is_sender:
            tick_x = time_x - 40
            draw.line([(tick_x, time_y+20), (tick_x+10, time_y+30), (tick_x+25, time_y+10)], fill="#34B7F1", width=4)
            draw.line([(tick_x+12, time_y+20), (tick_x+22, time_y+30), (tick_x+37, time_y+10)], fill="#34B7F1", width=4)

        return box_height

    def create_frame(self, history, article_title):
        img = Image.new('RGBA', (self.w, self.h), self.bg_color)
        draw = ImageDraw.Draw(img)
        
        bubble_heights = []
        spacing = 40
        for msg in history:
            h = self.calculate_bubble_height(msg['text'])
            bubble_heights.append(h)
            
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
        
        for item in reversed(draw_queue):
            self.draw_bubble(draw, item['text'], item['is_sender'], item['y'], item['time'])
            
        self.draw_whatsapp_header(draw, article_title, img)
            
        return np.array(img.convert("RGB"))

    def render_video(self, script_json, article_title, filename="final_video.mp4"):
        print(f"🎬 Rendering Video ({self.w}x{self.h}) for: {article_title[:30]}...")
        clips = []
        history = []
        
        for idx, msg in enumerate(script_json):
            text = msg['text']
            # ✅ FIX: Robust Logic for Sender Type
            msg_type = str(msg.get('type', '')).lower().strip()
            is_sender = (msg_type == 'send')
            
            msg_obj = {'text': text, 'is_sender': is_sender}
            history.append(msg_obj)
            
            frame_img = self.create_frame(history, article_title)
            
            # Dynamic Duration
            base_dur = 2.5
            char_dur = len(text) * 0.08
            read_duration = min(max(base_dur, char_dur), 6.0) # Min 2.5s, Max 6s
            
            clip_main = ImageClip(frame_img).set_duration(read_duration)
            
            sound = self.snd_sent if is_sender else self.snd_recv
            if sound: clip_main = clip_main.set_audio(sound)
                
            clips.append(clip_main)
            
        if not clips: return None

        final_clip = concatenate_videoclips(clips, method="compose")
        output_path = os.path.join(self.output_dir, filename)
        
        # Write file with fallback fps
        final_clip.write_videofile(
            output_path, 
            fps=self.fps, 
            codec='libx264', 
            audio_codec='aac', 
            logger=None,
            ffmpeg_params=['-pix_fmt', 'yuv420p'] # Better compatibility
        )
        print(f"✅ Video Rendered: {output_path}")
        return output_path
