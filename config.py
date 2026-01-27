# FILE: config.py
# ROLE: Shared Configuration & Constants
# UPDATED: Added 'scroll-margin-top' to fix Sticky Header overlap issue.

import datetime

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
]

FORBIDDEN_PHRASES = [
    "In today's digital age", "The world of AI is ever-evolving", "unveils", "unveiled",
    "poised to", "delve into", "game-changer", "paradigm shift", "tapestry", "robust",
    "leverage", "underscore", "testament to", "beacon of", "In conclusion",
    "Remember that", "It is important to note", "Imagine a world", "fast-paced world",
    "cutting-edge", "realm of"
]

BORING_KEYWORDS = [
    "CFO", "CEO", "Quarterly", "Earnings", "Report", "Market Cap", 
    "Dividend", "Shareholders", "Acquisition", "Merger", "Appointment", 
    "Executive", "Knorex", "Partner", "Agreement", "B2B", "Enterprise"
]

# --- UPDATED CSS ---
ARTICLE_STYLE = """
<style>
    .post-body { font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.8; color: #333; font-size: 18px; }
    
    h2 { 
        color: #111; 
        font-weight: 800; 
        margin-top: 50px; 
        border-bottom: 3px solid #f1c40f; 
        padding-bottom: 10px; 
        scroll-margin-top: 100px; /* يمنع اختفاء العنوان تحت الشريط العلوي */
    }
    
    h3 { 
        color: #2980b9; 
        font-weight: 700; 
        margin-top: 30px; 
        scroll-margin-top: 100px; /* نفس الإصلاح للعناوين الفرعية */
    }
    
    blockquote { background: #f9f9f9; border-left: 5px solid #2ecc71; margin: 20px 0; padding: 15px 25px; font-style: italic; }
    a { color: #3498db; text-decoration: none; border-bottom: 1px dotted #3498db; }
    a:hover { color: #e74c3c; border-bottom: 1px solid #e74c3c; }
    
    .toc-box { background: #fdfdfd; border: 1px solid #eee; padding: 20px; border-radius: 10px; margin-bottom: 40px; }
    .toc-box ul { list-style: none; padding: 0; }
    .toc-box li { margin-bottom: 10px; border-bottom: 1px dashed #eee; padding-bottom: 5px; }
    .toc-box a { text-decoration: none; border: none; font-weight: 600; color: #555; }
    
    .ai-sources-box {
        margin-top: 40px; 
        padding: 25px; 
        background-color: #f8f9fa; 
        border-radius: 12px; 
        border-left: 5px solid #3498db;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    .ai-sources-box h3 {
        margin-top: 0 !important;
        color: #2c3e50 !important;
        font-size: 20px !important;
        border-bottom: 1px solid #e1e4e8;
        padding-bottom: 10px;
        margin-bottom: 15px;
    }
    .ai-sources-box ul {
        margin-bottom: 0; 
        padding-left: 20px; 
        color: #555;
    }
    .ai-sources-box li {
        margin-bottom: 8px;
    }
    .ai-sources-box a {
        font-weight: 600;
        color: #3498db;
    }
</style>
"""

def log(msg):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)
