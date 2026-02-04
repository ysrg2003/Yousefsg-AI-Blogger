# FILE: remedy.py
# ROLE: The Content Surgeon (Precision & Evidence Injector)
# VERSION: 5.0 - Executing Detailed Remedy Commands with Targeted Research

import json
import datetime
import re
from config import log
from api_manager import generate_step_strict, master_json_parser
import scraper # نحتاج السكرابر لجلب النصوص من الروابط التي يجدها

def fix_article_content(current_html, audit_report, topic, original_research, iteration=1):
    log(f"   🚑 [Surgeon Agent] Round {iteration} | Executing Precision Surgery...")
    
    weaknesses = audit_report.get('critical_weaknesses', [])
    roadmap = audit_report.get('seo_roadmap', '')
    today_date = str(datetime.date.today())

    # سنمر على كل نقطة ضعف على حدة.
    # بما أن Gemini قد يجد صعوبة في التعديل الجزئي بشكل متكرر، سنستخدم حلقة.
    # الأفضل أن نطلب منه دمج التعديلات في HTML كامل مرة واحدة لتقليل الأخطاء
    # لذا، سنجمع كل الأدلة أولاً، ثم نطلب منه إعادة بناء المقال.

    all_found_evidence = []
    
    # === البحث عن الأدلة المفقودة لكل نقطة ضعف (PHASE 1) ===
    for weakness in weaknesses:
        remedy_cmd = weakness.get("remedy_command", "")
        location = weakness.get("location", "General")
        
        if not remedy_cmd: continue

        log(f"      🔎 Searching for evidence for: '{location}' (Command: {remedy_cmd[:50]}...)")
        
        # استخراج استعلام البحث من الأمر
        search_query_match = re.search(r"SEARCH:\s*'(.*?)'", remedy_cmd, re.IGNORECASE)
        search_query = search_query_match.group(1).strip() if search_query_match else f"{topic} {location} evidence"

        # استخراج نوع الدليل المطلوب (تجربة شخصية، بيانات رقمية، إلخ)
        extract_type_match = re.search(r"EXTRACT:\s*(.*?)\.", remedy_cmd, re.IGNORECASE)
        extract_type = extract_type_match.group(1).strip() if extract_type_match else "relevant information"

        # نطلب من الذكاء الاصطناعي أن يبحث عن الدليل ويستخرجه
        evidence_finder_prompt = f"""
        ROLE: Elite Research Assistant.
        TASK: Find and extract SPECIFIC, VERIFIABLE evidence based on the search query.
        
        SEARCH QUERY: "{search_query}"
        EVIDENCE TYPE NEEDED: "{extract_type}"
        ARTICLE TOPIC: {topic}
        
        INSTRUCTIONS:
        1. Use Google Search to find high-quality sources.
        2. Filter for: real user forums, academic papers, official data releases, reputable tech blogs.
        3. EXTRACT: 1-2 paragraphs of direct evidence (e.g., a user quote, a specific number, a case study finding).
        4. Provide the EXACT URL of the source.
        
        OUTPUT JSON ONLY:
        {{
            "found_evidence": true/false,
            "evidence_text": "Extracted paragraph(s) of proof.",
            "evidence_url": "https://www.source.com/path",
            "search_used": "{search_query}"
        }}
        """
        try:
            evidence_result = generate_step_strict(
                "gemini-2.0-flash-thinking-exp-01-21", 
                evidence_finder_prompt, 
                f"Finding Evidence for '{location}'", 
                required_keys=["found_evidence", "evidence_text"], 
                use_google_search=True
            )
            
            if evidence_result.get("found_evidence"):
                all_found_evidence.append({
                    "location": location,
                    "evidence_text": evidence_result.get("evidence_text"),
                    "evidence_url": evidence_result.get("evidence_url"),
                    "remedy_command": remedy_cmd # نمرر الأمر كاملاً
                })
                log(f"         ✅ Evidence Found for '{location}'.")
            else:
                log(f"         ⚠️ No specific evidence found for '{location}'.")

        except Exception as e:
            log(f"         ❌ Evidence Finder Failed for '{location}': {e}")

    if not all_found_evidence:
        log("      ⚠️ No new evidence gathered. No changes applied by Surgeon.")
        return None # لا يوجد ما يمكن إصلاحه

    # === دمج الأدلة في HTML المقال (PHASE 2) ===
    log(f"      💉 Integrating {len(all_found_evidence)} pieces of new evidence into the article...")

    integration_prompt = f"""
    ROLE: Master HTML Content Editor.
    TASK: Integrate the provided new evidence into the CURRENT HTML of the article.
    
    ARTICLE TOPIC: {topic}
    CURRENT HTML: {current_html}
    
    NEW EVIDENCE TO INTEGRATE (MANDATORY):
    {json.dumps(all_found_evidence)}

    INSTRUCTIONS (STRICT):
    1.  **INTERNAL REASONING:** Before integrating, think about the most natural and impactful way to inject each piece of evidence.
    2.  **TARGET EXACT LOCATION:** Use the "location" specified in the evidence object (e.g., "H2: Performance") to find the precise spot in the `CURRENT HTML`.
    3.  **INTEGRATE WITH E-E-A-T:**
        -   Add the `evidence_text` as a new paragraph.
        -   Wrap the text that refers to the evidence in **bold** or *italics*.
        -   Add a proper HTML citation `<a href="evidence_url" target="_blank" rel="nofollow">Source: [Relevant Part of URL]</a>`.
        -   Ensure the new content flows naturally.
    4.  **PRESERVATION (CRITICAL):**
        -   You MUST preserve ALL existing HTML tags, attributes, media (images, iframes), and code blocks (`<pre><code>`) in their EXACT form. DO NOT DELETE OR MODIFY existing tags unless specifically instructed by the remedy command (e.g., 'INTEGRATE into the existing paragraph').
        -   If `remedy_command` implies modifying an existing sentence, do so surgically, preserving surrounding HTML.
    5.  **NO HALLUCINATIONS:** Only use the `evidence_text` provided. Do not add new information.
    6.  **FINAL HTML ONLY:** The output must be the complete, modified HTML of the article.
    
    OUTPUT JSON ONLY:
    {{
        "fixed_html": "The complete, evidence-rich HTML code."
    }}
    """
    
    try:
        result = generate_step_strict(
            "gemini-2.5-flash", 
            integration_prompt, 
            "Evidence Integration Surgery", 
            required_keys=["fixed_html"],
            use_google_search=False # لا يحتاج للبحث في هذه المرحلة
        )
        return result.get('fixed_html')

    except Exception as e:
        log(f"      ❌ Evidence Integration Failed: {e}")
        return None
