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

ARTICLE_STYLE = """
<style>
    .post-body { font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.8; color: #333; font-size: 18px; }
    h2 { color: #111; font-weight: 800; margin-top: 50px; border-bottom: 3px solid #f1c40f; padding-bottom: 10px; }
    h3 { color: #2980b9; font-weight: 700; margin-top: 30px; }
    blockquote { background: #f9f9f9; border-left: 5px solid #2ecc71; margin: 20px 0; padding: 15px 25px; font-style: italic; }
    a { color: #3498db; text-decoration: none; border-bottom: 1px dotted #3498db; }
    a:hover { color: #e74c3c; border-bottom: 1px solid #e74c3c; }
    .toc-box { background: #fdfdfd; border: 1px solid #eee; padding: 20px; border-radius: 10px; margin-bottom: 40px; }
    .toc-box ul { list-style: none; padding: 0; }
    .toc-box li { margin-bottom: 10px; border-bottom: 1px dashed #eee; padding-bottom: 5px; }
    .toc-box a { text-decoration: none; border: none; font-weight: 600; color: #555; }
</style>
"""

def log(msg):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)
