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
        self.w, self.h = 1080, 1920 # Vertical Video (Shorts/Reels)
        self.fps = 24
        
        # Colors (Modern Chat Style)
        self.bg_color = (240, 242, 245)
        self.sender_color = (0, 132, 255)     # Blue
        self.receiver_color = (228, 230, 235) # Light Gray
        self.text_sender = (255, 255, 255)
        self.text_receiver = (5, 5, 5)
        
        # Ensure directories exist
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(assets_dir, exist_ok=True)
        
        # Setup Font (Download Roboto if missing to ensure English support)
        self.font_path = os.path.join(assets_dir, "Roboto-Bold.ttf")
        self._ensure_font()
        try:
            self.font = ImageFont.truetype(self.font_path, 40)
        except:
            self.font = ImageFont.load_default()

        # Setup Sounds (Optional - code won't crash if missing)
        self.snd_sent = self._load_audio("send.wav")
        self.snd_recv = self._load_audio("receive.wav")

    def _ensure_font(self):
        if not os.path.exists(self.font_path):
            print("⬇️ Downloading font for video...")
            url = "https://github.com/google/fonts/raw/main/apache/roboto/Roboto-Bold.ttf"
            try:
                r = requests.get(url)
                with open(self.font_path, 'wb') as f:
                    f.write(r.content)
            except:
                pass

    def _load_audio(self, filename):
        path = os.path.join(self.assets_dir, filename)
        if os.path.exists(path):
            return AudioFileClip(path)
        return None

    def draw_bubble(self, draw, text, is_sender, y_pos):
        margin = 40
        padding = 30
        max_width = int(self.w * 0.75)
        
        # Wrap Text
        avg_char_width = self.font.getbbox("x")[2] if hasattr(self.font, 'getbbox') else 20
        chars_per_line = max_width // avg_char_width
        lines = textwrap.wrap(text, width=chars_per_line)
        
        # Calculate Dimensions
        # Fallback for older Pillow versions
        if hasattr(self.font, 'getbbox'):
            line_height = self.font.getbbox("Ah")[3] + 15
        else:
            line_height = 50

        box_height = (len(lines) * line_height) + (padding * 2)
        
        # Calculate max width of actual text
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
        
        # Draw Rounded Box (Rectangle if rounded not supported by simple PIL)
        draw.rectangle([x1, y1, x2, y2], fill=color, outline=None)
        
        # Draw Text
        curr_y = y1 + padding
        for line in lines:
            draw.text((x1 + padding, curr_y), line, font=self.font, fill=text_col)
            curr_y += line_height
            
        return box_height + 30 # Return height consumed + margin

    def create_frame(self, history):
        img = Image.new('RGB', (self.w, self.h), self.bg_color)
        draw = ImageDraw.Draw(img)
        
        # Draw Header
        draw.rectangle([0, 0, self.w, 150], fill=(255,255,255))
        draw.text((self.w//2 - 150, 50), "Tech News Chat", fill=(0,0,0), font=self.font)
        
        y_cursor = 180
        
        # Show last 7 messages
        visible_history = history[-7:] 
        
        for msg in visible_history:
            h = self.draw_bubble(draw, msg['text'], msg['is_sender'], y_cursor)
            y_cursor += h
            
        return np.array(img)

    def render_video(self, script_json, filename="final_video.mp4"):
        print("🎬 Rendering Video...")
        clips = []
        history = []
        
        for idx, msg in enumerate(script_json):
            text = msg['text']
            is_sender = (msg['type'] == 'send')
            msg_obj = {'text': text, 'is_sender': is_sender}
            
            # Add current message to history
            history.append(msg_obj)
            
            # Create Frame
            frame_img = self.create_frame(history)
            
            # Calculate Duration (Minimum 2.5s, plus time for reading)
            read_duration = max(2.5, len(text) * 0.08)
            
            clip_main = ImageClip(frame_img).set_duration(read_duration)
            
            # Add Audio
            sound = self.snd_sent if is_sender else self.snd_recv
            if sound:
                clip_main = clip_main.set_audio(sound)
                
            clips.append(clip_main)
            
        if not clips: return None

        final_clip = concatenate_videoclips(clips, method="compose")
        output_path = os.path.join(self.output_dir, filename)
        
        # Write video file
        final_clip.write_videofile(output_path, fps=self.fps, codec='libx264', audio_codec='aac', logger=None)
        print(f"✅ Video Rendered: {output_path}")
        return output_path
