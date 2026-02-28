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
    "cutting-edge", "realm of",
    "dive deep", "explore the depths", "unraveling", "intricate dance",
    "pivotal role", "cornerstone", "myriad", "plethora", "trove",
    "seamless integration", "synergy", "holistic approach", "robust framework",
    "unparalleled", "transformative", "disruptive innovation", "game-changing solution",
    "future-proof", "scalable architecture", "optimizing efficiency", "maximizing ROI",
    "empowering users", "unlocking potential", "harnessing the power of", "delivering value",
    "stay ahead of the curve", "navigate the complexities", "strategic imperative",
    "key takeaways", "in essence", "ultimately", "at the end of the day",
    "without further ado", "in a nutshell", "last but not least", "the bottom line is"
]

BORING_KEYWORDS = [
    "CFO", "CEO", "Quarterly", "Earnings", "Report", "Market Cap", 
    "Dividend", "Shareholders", "Acquisition", "Merger", "Appointment", 
    "Executive", "Knorex", "Partner", "Agreement", "B2B", "Enterprise",
    "synergistic", "proactive", "scalable", "disruptive", "innovative",
    "optimization", "leverage", "streamline", "maximize", "strategize",
    "implement", "facilitate", "orchestrate", "calibrate", "monetize",
    "ecosystem", "verticals", "horizontal integration", "value proposition",
    "thought leadership", "best practices", "core competencies", "competitive advantage",
    "market leader", "industry standard", "cutting-edge technology", "next-generation platform"
]

# --- UPDATED CSS ---
ARTICLE_STYLE = " "

# --- NEW: ADVANCED UNIQUNESS & QUALITY PROTOCOL ---
MIN_UNIQUE_SCORE = 0.85 # Minimum acceptable uniqueness score (0.0 - 1.0)
MIN_READABILITY_SCORE = 60 # Flesch-Kincaid Grade Level (higher is better for tech content)
MAX_AI_DETECTION_SCORE = 0.10 # Maximum acceptable AI detection score (0.0 - 1.0)

# --- NEW: E-E-A-T GUIDELINES ---
EEAT_GUIDELINES = {
    "experience": "Does the content demonstrate first-hand experience or practical knowledge?",
    "expertise": "Is the content written by or does it cite experts in the field?",
    "authoritativeness": "Is the source reputable and recognized as an authority on the topic?",
    "trustworthiness": "Is the content accurate, verifiable, and free from misleading information?"
}

def log(msg):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)
