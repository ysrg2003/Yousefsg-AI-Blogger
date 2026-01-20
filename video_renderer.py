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
        self.w, self.h = 1080, 1920 
        self.fps = 24
        
        # Colors (High Contrast for readability)
        self.bg_color = (255, 255, 255) # White background
        self.sender_color = (0, 122, 255)     # iMessage Blue
        self.receiver_color = (229, 229, 234) # Light Gray
        self.text_sender = (255, 255, 255)
        self.text_receiver = (0, 0, 0)
        
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(assets_dir, exist_ok=True)
        
        # Font Setup (Larger Font)
        self.font_path = os.path.join(assets_dir, "Roboto-Bold.ttf")
        self._ensure_font()
        try:
            self.font_size = 60 # خط كبير جداً للقراءة
            self.font = ImageFont.truetype(self.font_path, self.font_size)
            self.header_font = ImageFont.truetype(self.font_path, 40)
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
        margin = 50
        padding = 40
        max_width = int(self.w * 0.85) # استغلال عرض الشاشة
        
        # Wrap Text
        avg_char_width = self.font.getbbox("x")[2] if hasattr(self.font, 'getbbox') else 30
        chars_per_line = int(max_width / avg_char_width)
        lines = textwrap.wrap(text, width=chars_per_line)
        
        # Calculate Dimensions
        if hasattr(self.font, 'getbbox'):
            line_height = self.font.getbbox("Ah")[3] + 20
        else:
            line_height = 70

        box_height = (len(lines) * line_height) + (padding * 2)
        
        # Calculate Width
        text_width = 0
        for line in lines:
            if hasattr(self.font, 'getbbox'):
                bbox = self.font.getbbox(line)
                text_width = max(text_width, bbox[2])
            else:
                text_width = len(line) * avg_char_width
        
        box_width = text_width + (padding * 2)
        
        # Position
        if is_sender:
            x1 = self.w - margin - box_width
            x2 = self.w - margin
            color = self.sender_color
            text_col = self.text_sender
        else:
            x1 = margin
            x2 = margin + box_width
            color = self.receiver_color
            text_col = self.text_receiver
            
        y1 = y_pos
        y2 = y_pos + box_height
        
        # Draw Bubble
        draw.rectangle([x1, y1, x2, y2], fill=color, outline=None)
        
        # Draw Text
        curr_y = y1 + padding
        for line in lines:
            draw.text((x1 + padding, curr_y), line, font=self.font, fill=text_col)
            curr_y += line_height
            
        return box_height + 40 # Return height + spacing

    def create_frame(self, history, article_title):
        img = Image.new('RGB', (self.w, self.h), self.bg_color)
        draw = ImageDraw.Draw(img)
        
        # 1. Draw Header (Article Title)
        header_h = 200
        draw.rectangle([0, 0, self.w, header_h], fill=(245,245,245))
        
        # Wrap Title
        title_lines = textwrap.wrap(article_title, width=40)
        title_y = 60
        for line in title_lines[:2]: # Max 2 lines for title
            bbox = self.header_font.getbbox(line)
            w = bbox[2] - bbox[0]
            draw.text(((self.w - w)/2, title_y), line, fill=(50,50,50), font=self.header_font)
            title_y += 50
            
        # 2. Smart Scrolling Logic
        # We only draw the last few messages to simulate "Zoom/Focus"
        # Calculate total height needed
        temp_draw = ImageDraw.Draw(Image.new('RGB', (1,1)))
        total_h = 0
        bubble_heights = []
        
        for msg in history:
            h = self.draw_bubble(temp_draw, msg['text'], msg['is_sender'], 0)
            bubble_heights.append(h)
            total_h += h
            
        # Determine Start Y to keep latest message visible
        # We want the last message to end around y=1600
        target_bottom = 1600
        start_y = header_h + 50
        
        if (start_y + total_h) > target_bottom:
            start_y = target_bottom - total_h
            
        # Draw visible bubbles
        current_y = start_y
        for i, msg in enumerate(history):
            # Only draw if it's within visible area (optimization)
            if current_y + bubble_heights[i] > header_h:
                self.draw_bubble(draw, msg['text'], msg['is_sender'], current_y)
            current_y += bubble_heights[i]
            
        return np.array(img)

    def render_video(self, script_json, article_title, filename="final_video.mp4"):
        print(f"🎬 Rendering Video for: {article_title[:30]}...")
        clips = []
        history = []
        
        for idx, msg in enumerate(script_json):
            text = msg['text']
            is_sender = (msg['type'] == 'send')
            msg_obj = {'text': text, 'is_sender': is_sender}
            
            history.append(msg_obj)
            
            # Create Frame
            frame_img = self.create_frame(history, article_title)
            
            # Duration logic
            read_duration = max(3.0, len(text) * 0.1) # Slower reading speed
            
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
