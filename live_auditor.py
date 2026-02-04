# FILE: live_auditor.py
# ROLE: Level 10 Google Search Quality Rater (The Merciless General)
# VERSION: 5.0 - Strategic E-E-A-T Audit with Hyper-Specific Remedy Commands

import json
import datetime
from config import log
from api_manager import generate_step_strict

def audit_live_article(url, target_keyword, iteration=1):
    log(f"   ⚖️ [Investigative Auditor] Round {iteration} | 🚀 PHYSICAL AUDIT: '{url}' vs. Page 1 Competitors...")
    
    today_date = str(datetime.date.today())

    prompt = f"""
    MANDATORY INSTRUCTION: USE GOOGLE SEARCH & INTERNAL REASONING.
    
    TASK: You are Google's Chief Content Inspector. Your ONLY mission is to get this article to Page 1 for "{target_keyword}".
    
    Article URL Under Audit: {url}
    Target Keyword: "{target_keyword}"
    Current Date: {today_date}

    ---
    🧠 PHASE 1: INTERNAL REASONING (The Strategic Assessment)
    ---
    <thought>
    1.  **Initial Scan:** What is the article's current E-E-A-T strength based on its content? (Experience, Expertise, Authoritativeness, Trustworthiness).
    2.  **Competitive Search:** I will perform a Google Search for "{target_keyword}" and identify the Top 3 organic (non-ad) results.
    3.  **Competitor E-E-A-T Dissection (CRITICAL):** For EACH of the Top 3 competitors, I will identify their SPECIFIC E-E-A-T advantages that my article currently lacks.
        -   **Experience:** Do they show first-hand use? A unique case study? A screenshot of a rare bug?
        -   **Expertise:** Do they cite academic papers, specific industry reports, or present advanced technical analysis (e.g., specific code optimization techniques)?
        -   **Authoritativeness:** Do they link to many high-authority sources? Are they recognized leaders in the field?
        -   **Trustworthiness:** Do they present unbiased data? Real user testimonials? Clear disclosures?
    4.  **Identify EXACT GAPS in MY Article:** Based on the competitor analysis, where exactly does my article fail? I need to pinpoint the section (H2) or even the specific claim that needs strengthening.
    5.  **Formulate PRECISE REMEDY COMMANDS:** For each identified gap, I will write an actionable, step-by-step command for the "Surgeon Agent" to execute. This command MUST include:
        -   The type of evidence needed (e.g., "personal anecdote", "quantitative data", "user testimonial").
        -   A highly specific search query to find that evidence.
        -   Instructions on WHERE to insert/modify the HTML (e.g., "after H2 'Performance'").
    </thought>

    ---
    ✍️ PHASE 2: OUTPUT (The Audit Report)
    ---
    Provide your audit report in a strict JSON format.

    OUTPUT JSON ONLY:
    {{
        "quality_score": 0.0 to 10.0, // Overall score
        "is_page_one_ready": true/false, // Based on Page 1 standard
        "critical_weaknesses": [ // List of problems
            {{
                "location": "H2: Getting Started", // The exact section/header where the problem exists
                "exact_problem": "Lack of tangible first-hand user experience/tutorial. It's too generic.", // Specific E-E-A-T deficiency
                "competitor_advantage": "The top result (example.com/guide) features a step-by-step guide with actual developer screenshots and personal tips.", // What makes competitor better
                "remedy_command": "SEARCH: 'Fieldguide API developer experience Reddit' OR 'Fieldguide setup common issues forum'. EXTRACT: 2-3 genuine user experiences/tips. INTEGRATE: as a new paragraph after the 'Getting Started' H2, citing the source URL. EMPHASIZE: practical advice."
            }},
            {{
                "location": "Paragraph after H2: Performance & 'Real World' Benchmarks", // Another example
                "exact_problem": "Missing specific quantitative benchmark data comparing latency to competitors.",
                "competitor_advantage": "Competitor (analytics.com) shows a clear chart of Fieldguide vs. similar tools with latency in milliseconds.",
                "remedy_command": "SEARCH: 'Fieldguide vs [competitor] latency benchmarks' OR 'Fieldguide API response time'. EXTRACT: 1-2 specific latency numbers or comparative data points. INTEGRATE: into the existing paragraph, bolding the numbers and linking to the source. IF NO NUMBERS: State that official benchmarks are scarce, but industry average is X."
            }}
            // Add more weakness objects as needed
        ],
        "seo_roadmap": "Overall strategic recommendations for ranking. Be aggressive.",
        "top_competitors": [
            {{"title": "Competitor 1 Title", "url": "https://competitor1.com"}},
            {{"title": "Competitor 2 Title", "url": "https://competitor2.com"}}
        ]
    }}
    """

    try:
        result = generate_step_strict(
            "gemini-2.0-flash-thinking-exp-01-21", # استخدام موديل التفكير
            prompt, 
            "Deep Investigative Audit", 
            required_keys=["critical_weaknesses", "quality_score"],
            use_google_search=True # يجب أن يستخدم البحث
        )
        return result
    except Exception as e:
        log(f"      ❌ Auditor Error: {e}")
        return None
