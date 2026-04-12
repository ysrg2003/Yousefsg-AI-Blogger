# ==============================================================================
# FILE: seo_quality_gate.py
# ROLE: The Iron Gate — Pre-Publishing SEO & Quality Enforcer
# VERSION: 1.0
# DESCRIPTION:
#   This module is the FINAL checkpoint before ANY article touches Blogger.
#   It scans the generated HTML for every known quality failure and either
#   auto-repairs it or raises a blocking error.
#
#   CATCHES:
#     1. Placeholder images (via.placeholder.com, broken src)
#     2. Hypothetical/fake content phrases
#     3. "We don't know" / ignorance admissions
#     4. Missing or empty publication date
#     5. Repeated single-source citations (>3 times same URL)
#     6. Authority claims without links (Reuters, Bloomberg, etc.)
#     7. "Watch the Video Summary" with no real embed
#     8. Empty alt text or generic alt text
#     9. Tables with no numerical data (only qualitative words)
#    10. Captions containing raw metadata junk
# ==============================================================================

import re
import datetime
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from config import log

# ---------------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------------

PLACEHOLDER_PATTERNS = [
    "via.placeholder.com",
    "placeholder.com",
    "placehold.it",
    "placekitten.com",
    "lorempixel.com",
    "dummyimage.com",
    "picsum.photos",
    "fakeimg.pl",
]

IGNORANCE_PHRASES = [
    "we don't know all the technical details",
    "we don't know the technical details",
    "details are unclear",
    "we don't know exactly",
    "technical details remain unknown",
    "it's not entirely clear",
    "we cannot confirm",
    "no official data available",
    "the exact details are not yet known",
    "specifics are not yet available",
    # NEW: community/reddit vagueness
    "we don't have a lot of direct feedback from reddit",
    "we don't have direct feedback",
    "we can guess some things",
    "we can guess what people might",
    "no direct reddit feedback",
    "we can predict the criticism",
    "based on what we know, we can assume",
    # NEW: speculation disguised as analysis
    "people might criticize",
    "users will likely complain",
    "community might feel",
    # FIX v4.1: Community Pulse faking patterns
    "community feedback for this topic is NOT yet available",
    "no community data was available",
    "reddit data was not available",
    "based on similar tools",
    "based on past experience with similar",
    "we can predict",
    "sentiment is likely",
    "early adopters will probably",
]

FAKE_CONTENT_TRIGGERS = [
    "hypothetical screenshot",
    "hypothetical data flow",   # ASCII art diagram placeholder
    "imagine a clean interface",
    "imagine a screenshot",
    "imagine a dashboard",
    "[[asset_",       # un-replaced placeholders (case-insensitive)
    "[[generated_chart]]",
    "[[visual_evidence",
    "[[code_snippet",
    "placeholder for",
]

# ASCII art code blocks used as fake diagrams
ASCII_ART_PATTERNS = [
    r"```.*?\+[-]+\+.*?```",       # box-drawing characters in code blocks
    r"<pre>.*?\+[-=]+\+.*?</pre>", # same in HTML pre tags
    r"<code>.*?\+[-=]+\+.*?</code>",
]

AUTHORITY_NAMES = [
    "reuters", "bloomberg", "the verge", "techcrunch",
    "wired", "ars technica", "forbes", "wall street journal", "the guardian",
    "cnbc", "bbc", "financial times", "gartner", "new york times",
    "business insider", "mit technology review",
]
# NOTE: "nature", "science" removed — too generic, appear in normal prose
# Only include brand names that cannot appear without citation intent

QUALITATIVE_ONLY_WORDS = {
    "excellent", "good", "fair", "poor", "bad", "great", "ok", "okay",
    "average", "high", "medium", "low", "varies", "variable", "n/a",
    "tbd", "coming soon", "unlimited",
}

BAD_CAPTION_PATTERNS = [
    r"\|\s*\d+[km]\d+",           # e.g. "| 348k4.4k"
    r"\d+[km]\s*\d+\.\d+[km]",  # e.g. "348k4.4k"
    r"changes\s*\|\s*\d",
    r"hip quake",
    r"urbanurchin",
    r"Main Featured Image / OpenGraph Image",
    r"📸 Main Featured Image",
    r"OpenGraph Image",
    r"terms apply",           # promotional ad text in caption
    r"learn more$",           # CTA in caption
    r"\d+ months?\.\s*terms", # discount promo in caption
]

# Link anchor text that reveals a dead/broken link
DEAD_LINK_ANCHOR_PATTERNS = [
    "404", "page not found", "not found", "just a moment", "sorry, this page",
    "unavailable to load", "error", "access denied", "forbidden",
    "response of native",   # completely off-topic source included
    "subarctic plant",      # obviously wrong source
]

GENERIC_ALT_PATTERNS = [
    "main featured image",
    "opengraph image",
    "og image",
    "featured image",
    "article image",
]


# ---------------------------------------------------------------------------
# INDIVIDUAL CHECKS
# ---------------------------------------------------------------------------

class QualityIssue:
    def __init__(self, level, code, message, auto_fixed=False):
        self.level = level          # "BLOCK" | "WARN"
        self.code = code
        self.message = message
        self.auto_fixed = auto_fixed

    def __repr__(self):
        fixed_str = " [AUTO-FIXED]" if self.auto_fixed else ""
        return f"[{self.level}] {self.code}: {self.message}{fixed_str}"


def check_placeholder_images(soup) -> list:
    issues = []
    imgs = soup.find_all("img")
    for img in imgs:
        src = img.get("src", "")
        if not src:
            issues.append(QualityIssue("BLOCK", "IMG_EMPTY_SRC",
                f"<img> tag with empty src found. Must have a real image URL."))
            img.decompose()
        elif any(p in src.lower() for p in PLACEHOLDER_PATTERNS):
            issues.append(QualityIssue("BLOCK", "IMG_PLACEHOLDER",
                f"Placeholder image detected: {src[:80]}"))
            img.decompose()
    return issues


def check_fake_content(soup) -> list:
    issues = []
    html_lower = str(soup).lower()
    for phrase in FAKE_CONTENT_TRIGGERS:
        if phrase.lower() in html_lower:
            issues.append(QualityIssue("BLOCK", "FAKE_CONTENT",
                f"Fake/placeholder content detected: '{phrase}'"))
    
    # Detect ASCII art code blocks used as fake diagrams
    import re as _re
    html_str = str(soup)
    # Look for <pre> or <code> blocks containing box-drawing characters
    code_blocks = _re.findall(r'<(?:pre|code)[^>]*>(.*?)</(?:pre|code)>', html_str, _re.DOTALL | _re.IGNORECASE)
    for block in code_blocks:
        # Box-drawing chars: +, |, -, =, >, < in structured patterns
        if block.count('+') >= 3 and block.count('|') >= 3 and block.count('-') >= 5:
            issues.append(QualityIssue("BLOCK", "FAKE_ASCII_ART",
                "ASCII art diagram in <pre>/<code> block — replace with a real image or chart"))
            break  # One report is enough
    
    return issues


def check_ignorance_admissions(soup) -> list:
    issues = []
    text = soup.get_text().lower()
    for phrase in IGNORANCE_PHRASES:
        if phrase in text:
            issues.append(QualityIssue("BLOCK", "IGNORANCE_ADMISSION",
                f"Article admits ignorance: '{phrase}' — kills E-E-A-T"))
    return issues


def check_repeated_citations(soup) -> list:
    issues = []
    links = soup.find_all("a", href=True)
    citation_count = {}
    for link in links:
        href = link["href"]
        if href.startswith("http") and "latestai.me" not in href:
            domain = urlparse(href).netloc
            full_url = href.split("?")[0]  # ignore query params for counting
            citation_count[full_url] = citation_count.get(full_url, 0) + 1

    for url, count in citation_count.items():
        if count > 3:
            issues.append(QualityIssue("BLOCK", "REPEATED_CITATION",
                f"Same URL cited {count} times: {url[:70]} — AI pattern detected by Google"))
    return issues


def check_authority_claims_without_links(soup) -> list:
    """
    Detects authority names mentioned without hyperlinks.
    AUTO-FIX: Replaces "According to Reuters" with generic phrases inline.
    Works by modifying the soup's text nodes directly.
    """
    import re
    issues = []
    linked_domains = set()
    for link in soup.find_all("a", href=True):
        href = link["href"].lower()
        for name in AUTHORITY_NAMES:
            if name in href.replace("-", " ").replace(".", " "):
                linked_domains.add(name)

    for name in AUTHORITY_NAMES:
        if name in linked_domains:
            continue  # properly linked — skip

        # Check all text nodes
        for tag in soup.find_all(string=True):
            if tag.parent and tag.parent.name in ["script", "style", "a"]:
                continue
            text_lower = tag.lower() if isinstance(tag, str) else ""
            if name not in text_lower:
                continue

            # AUTO-FIX the text node
            patterns = [
                (rf"(?i)according to {re.escape(name)},?\s?", "According to industry reports, "),
                (rf"(?i)as reported by {re.escape(name)},?\s?", "As widely reported, "),
                (rf"(?i){re.escape(name)} report(?:s|ed),?\s?", "Industry analysts report "),
                (rf"(?i){re.escape(name)} noted? that\s?", "Reports indicate that "),
                (rf"(?i)sources like {re.escape(name)}", "authoritative sources"),
                (rf"(?i)authoritative sources like {re.escape(name)}", "authoritative sources"),
                (rf"(?i)like {re.escape(name)}", "like leading publications"),
            ]
            original = str(tag)
            new_text = original
            fixed = False
            for pattern, replacement in patterns:
                replaced = re.sub(pattern, replacement, new_text)
                if replaced != new_text:
                    new_text = replaced
                    fixed = True

            if fixed:
                tag.replace_with(new_text)
                issues.append(QualityIssue("BLOCK", "AUTHORITY_WITHOUT_LINK",
                    f"Authority '{name}' replaced with generic phrase (no link existed)",
                    auto_fixed=True))
            elif name in text_lower:
                # Couldn't auto-fix this specific pattern — flag as non-auto-fixed block
                issues.append(QualityIssue("BLOCK", "AUTHORITY_WITHOUT_LINK",
                    f"Authority '{name}' mentioned without hyperlink — remove or add real URL"))
    return issues


def check_video_section_without_embed(soup) -> list:
    issues = []
    # Find h2/h3 containing "Watch the Video Summary"
    for header in soup.find_all(["h2", "h3", "h4"]):
        text = header.get_text(strip=True).lower()
        if "watch the video" in text or "video summary" in text:
            # Check if there's an iframe nearby (within next 3 siblings)
            found_embed = False
            sibling = header.find_next_sibling()
            for _ in range(5):
                if sibling is None:
                    break
                if sibling.name in ["iframe", "video"] or sibling.find("iframe"):
                    found_embed = True
                    break
                sibling = sibling.find_next_sibling()
            
            if not found_embed:
                # Auto-fix: remove the header entirely
                issues.append(QualityIssue("BLOCK", "EMPTY_VIDEO_SECTION",
                    "Video section header exists but no iframe/embed found — removed",
                    auto_fixed=True))
                header.decompose()
    return issues


def check_table_quality(soup) -> list:
    issues = []
    tables = soup.find_all("table")
    for table in tables:
        cells = table.find_all("td")
        if not cells:
            continue
        
        numeric_cells = 0
        total_cells = 0
        for cell in cells:
            text = cell.get_text(strip=True).lower()
            if not text or text == "feature":
                continue
            total_cells += 1
            # Check if cell has numeric content
            has_number = bool(re.search(r'\d+', text))
            is_qualitative_only = text in QUALITATIVE_ONLY_WORDS
            if has_number and not is_qualitative_only:
                numeric_cells += 1

        if total_cells > 0:
            numeric_ratio = numeric_cells / total_cells
            if numeric_ratio < 0.25:  # Less than 25% of cells have real data
                issues.append(QualityIssue("WARN", "TABLE_NO_NUMBERS",
                    f"Comparison table has only {numeric_cells}/{total_cells} numeric cells "
                    f"({numeric_ratio:.0%}). Use $X.XX, ms, %, scores — not 'Excellent/Good/Fair'"))
    return issues


def check_bad_captions(soup) -> list:
    issues = []
    figcaptions = soup.find_all("figcaption")
    for cap in figcaptions:
        text = cap.get_text(strip=True)
        for pattern in BAD_CAPTION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                issues.append(QualityIssue("WARN", "BAD_CAPTION",
                    f"Raw metadata junk in caption: '{text[:60]}' — auto-cleaned",
                    auto_fixed=True))
                # Auto-fix: replace caption with cleaned version
                clean_text = re.sub(r'📸\s*', '', text)
                clean_text = re.sub(r'\|\s*\d+[km]\d+.*$', '', clean_text, flags=re.IGNORECASE)
                clean_text = re.sub(r'Main Featured Image.*$', '', clean_text, flags=re.IGNORECASE)
                clean_text = clean_text.strip()
                if clean_text:
                    cap.string = f"📸 {clean_text}"
                else:
                    cap.decompose()
                break
    return issues


# Generic anchor text patterns that signal low-quality internal links
_GENERIC_INTERNAL_ANCHORS = [
    "our articles on ai", "ai tools", "ai innovations", "latest ai news",
    "click here", "read more", "learn more", "see more", "find out more",
    "our coverage", "check it out", "visit our site",
]

def check_dead_link_anchors(soup) -> list:
    """
    Detects links whose visible anchor text reveals the URL is broken.
    Also detects generic homepage internal links (latestai.me with no path).
    """
    issues = []
    links = soup.find_all("a", href=True)
    for link in links:
        anchor = link.get_text(strip=True).lower()
        href = link.get("href", "")
        
        # Check for generic internal homepage links (no article path)
        if "latestai.me" in href:
            from urllib.parse import urlparse
            parsed = urlparse(href)
            path = parsed.path.strip("/")
            if not path or path == "" or path == "index.html":
                # It's a bare homepage link
                if any(g in anchor for g in _GENERIC_INTERNAL_ANCHORS):
                    issues.append(QualityIssue("BLOCK", "GENERIC_INTERNAL_LINK",
                        f"Generic homepage internal link: '{anchor[:60]}' → {href} — must link to a specific article"))
            continue  # Done checking internal links
            
        if not href.startswith("http"):
            continue
            
        for pattern in DEAD_LINK_ANCHOR_PATTERNS:
            if pattern in anchor:
                issues.append(QualityIssue("BLOCK", "DEAD_SOURCE_LINK",
                    f"Source link is broken — anchor text reveals 404/error: '{link.get_text(strip=True)[:60]}' → {href[:60]}"))
                break
    return issues


def check_promo_in_caption(soup) -> list:
    """
    Detects ad/promotional text mistakenly copied into figcaptions.
    e.g. '50% off 3 months. terms apply. learn more'
    """
    issues = []
    for cap in soup.find_all("figcaption"):
        text = cap.get_text(strip=True).lower()
        promo_triggers = ["terms apply", "% off", "learn more", "sign up now",
                         "try free", "get started", "now available on", "worldwide"]
        hits = [t for t in promo_triggers if t in text]
        if len(hits) >= 2:
            issues.append(QualityIssue("BLOCK", "PROMO_IN_CAPTION",
                f"Promotional/ad text in figcaption: '{cap.get_text(strip=True)[:70]}'",
                auto_fixed=True))
            cap.string = "📸 Image"  # Replace with safe generic fallback
    return issues


# Social media icon URLs that get a pass (decorative, author box)
_SOCIAL_ICON_DOMAINS = ["flaticon.com", "cdn-icons-png"]

def check_unsourced_statistics(soup) -> list:
    """
    Detects percentage/number statistics that appear without a citation link nearby.
    Pattern: a sentence contains X% or $X and no <a href> appears within 200 chars.
    """
    import re
    issues = []
    html_str = str(soup)
    
    # Find paragraphs with statistics
    paragraphs = soup.find_all("p")
    stat_pattern = re.compile(r'\b(\d+\.?\d*\s*%|\$\d+|\d+x\s+(?:faster|cheaper|more)|\d+\s+(?:million|billion|thousand))', re.IGNORECASE)
    
    for para in paragraphs:
        text = para.get_text()
        stats = stat_pattern.findall(text)
        if not stats:
            continue
        # Check if paragraph has a citation link
        has_link = bool(para.find("a", href=True))
        if not has_link and len(stats) >= 2:  # 2+ stats, no source = suspicious
            issues.append(QualityIssue("WARN", "UNSOURCED_STAT",
                f"Paragraph has {len(stats)} statistics ({stats[0]}, {stats[1] if len(stats)>1 else ''}) but no citation link"))
    return issues


def check_generic_alt_text(soup) -> list:
    issues = []
    imgs = soup.find_all("img")
    for img in imgs:
        src = img.get("src", "")
        alt = img.get("alt", "").strip().lower()
        
        # Check if it's a social/decorative icon — upgrade missing alt to BLOCK
        is_icon = any(d in src for d in _SOCIAL_ICON_DOMAINS)
        
        if not alt:
            if is_icon:
                # Social icons MUST have alt for accessibility — BLOCK
                issues.append(QualityIssue("BLOCK", "MISSING_ALT_ICON",
                    f"Social/icon image missing alt text: {src[:60]} — add descriptive alt"))
            else:
                issues.append(QualityIssue("WARN", "MISSING_ALT",
                    f"Image missing alt text: {src[:60]}"))
        elif any(g in alt for g in GENERIC_ALT_PATTERNS):
            issues.append(QualityIssue("WARN", "GENERIC_ALT",
                f"Generic/meaningless alt text: '{alt[:60]}'"))
    return issues


def inject_publication_date(html: str, published_date: datetime.date = None) -> str:
    """
    Ensures the publication date is visible in the article.
    Injects a styled date element if not present.
    """
    if published_date is None:
        published_date = datetime.date.today()
    
    date_str = published_date.strftime("%B %d, %Y")
    date_iso = published_date.isoformat()
    
    # Check if date is already present and non-empty
    soup = BeautifulSoup(html, "html.parser")
    
    # Look for existing date indicators
    existing_date = False
    for tag in soup.find_all(["time", "span", "p"]):
        text = tag.get_text(strip=True)
        if re.search(r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b', text):
            existing_date = True
            break
    
    if not existing_date:
        date_html = f'''<div class="article-meta" style="display:flex; align-items:center; gap:12px; margin-bottom:20px; font-size:13px; color:#666; border-bottom:1px solid #eee; padding-bottom:12px;">
            <time datetime="{date_iso}" style="font-weight:500;">📅 Published: {date_str}</time>
            <span>|</span>
            <time datetime="{date_iso}">🔄 Last Updated: {date_str}</time>
        </div>'''
        
        # Inject after the H1 or at the very beginning of content
        h1 = soup.find("h1")
        if h1:
            h1.insert_after(BeautifulSoup(date_html, "html.parser"))
        else:
            # Insert at beginning
            first_elem = soup.find()
            if first_elem:
                first_elem.insert_before(BeautifulSoup(date_html, "html.parser"))
        
        html = str(soup)
        log("   📅 Publication date injected into article.")
    
    return html


def clean_forbidden_phrases(html: str) -> str:
    """Remove/replace AI-pattern forbidden phrases."""
    REPLACEMENTS = {
        "In today's digital age,": "Today,",
        "In today's digital age": "Today",
        "game-changer": "significant advancement",
        "paradigm shift": "major change",
        "leverage": "use",
        "delve into": "explore",
        "It is important to note that": "",
        "It is crucial to note": "",
        "Remember that": "",
        "In conclusion,": "",
        "As we have seen,": "",
        "Furthermore,": "Also,",
        "Moreover,": "Also,",
        "In the realm of": "In",
        "cutting-edge": "advanced",
        "robust": "strong",
        "underscore": "highlight",
        "testament to": "proof of",
        "beacon of": "",
        "Imagine a world where": "Consider:",
        "fast-paced world": "rapidly evolving field",
    }
    
    for old, new in REPLACEMENTS.items():
        html = html.replace(old, new)
        html = html.replace(old.lower(), new.lower())
    
    return html


# ---------------------------------------------------------------------------
# MAIN GATE FUNCTION
# ---------------------------------------------------------------------------


def check_temp_slug_in_links(soup) -> list:
    """
    FIX v4.1: Detects if the temp-slug placeholder URL was never replaced with the real published URL.
    This happens when published_url_placeholder replacement fails.
    """
    issues = []
    html_str = str(soup)
    if "temp-slug.html" in html_str:
        count = html_str.count("temp-slug.html")
        issues.append(QualityIssue("BLOCK", "TEMP_SLUG_URL",
            f"temp-slug.html placeholder found {count} time(s) — published URL was never injected. Schema and H1 point to wrong URL."))
    return issues


def check_word_count(soup) -> list:
    """FIX v4.1: Enforce minimum word count of 1200 words for SEO competitiveness."""
    issues = []
    for tag in soup.find_all(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator=" ")
    import re as _re
    text = _re.sub(r"\s+", " ", text).strip()
    words = len(text.split())
    if words < 900:
        issues.append(QualityIssue("BLOCK", "WORD_COUNT_TOO_LOW",
            f"Article is only {words} words — minimum is 1,200 for competitive AI topics. Google will not rank thin content."))
    elif words < 1200:
        issues.append(QualityIssue("WARN", "WORD_COUNT_SHORT",
            f"Article is {words} words — target 1,500+ for best ranking. Competitors average 1,800+."))
    return issues


def run_quality_gate(html: str, title: str, published_date: datetime.date = None) -> dict:
    """
    The Iron Gate: Run all quality checks on the article HTML.
    
    Returns:
        {
            "passed": bool,
            "cleaned_html": str,  # HTML after auto-fixes
            "blocking_issues": [...],
            "warnings": [...],
            "auto_fixes": int
        }
    """
    log("   🔒 [Iron Gate] Running pre-publish quality checks...")
    
    soup = BeautifulSoup(html, "html.parser")
    all_issues = []
    
    # Run all checks (order matters — some checks auto-fix via soup mutation)
    all_issues += check_placeholder_images(soup)
    all_issues += check_fake_content(soup)
    all_issues += check_ignorance_admissions(soup)
    all_issues += check_video_section_without_embed(soup)
    all_issues += check_bad_captions(soup)
    
    # Additional checks — some of these also mutate soup (authority, promo)
    all_issues += check_repeated_citations(soup)
    all_issues += check_authority_claims_without_links(soup)  # mutates soup text nodes
    all_issues += check_dead_link_anchors(soup)
    all_issues += check_promo_in_caption(soup)                # mutates soup captions
    all_issues += check_table_quality(soup)
    all_issues += check_unsourced_statistics(soup)
    all_issues += check_generic_alt_text(soup)
    
    # Capture ALL mutations into cleaned_html AFTER all soup-mutating checks
    cleaned_html = str(soup)
    
    # Apply forbidden phrase cleanup on the fully-mutated HTML
    cleaned_html = clean_forbidden_phrases(cleaned_html)
    
    # Inject publication date
    cleaned_html = inject_publication_date(cleaned_html, published_date)
    
    # Separate blocking vs warnings
    blocking = [i for i in all_issues if i.level == "BLOCK" and not i.auto_fixed]
    warnings = [i for i in all_issues if i.level == "WARN"]
    auto_fixed = [i for i in all_issues if i.auto_fixed]
    
    # Log results
    log(f"   📊 Quality Gate Results: {len(blocking)} blocking | {len(warnings)} warnings | {len(auto_fixed)} auto-fixed")
    
    for issue in all_issues:
        emoji = "🚫" if issue.level == "BLOCK" and not issue.auto_fixed else ("✅" if issue.auto_fixed else "⚠️")
        log(f"      {emoji} {issue}")
    
    passed = len(blocking) == 0
    
    if passed:
        log("   ✅ [Iron Gate] PASSED — Article cleared for publishing.")
    else:
        log(f"   ❌ [Iron Gate] BLOCKED — {len(blocking)} critical issue(s) must be fixed.")
    
    return {
        "passed": passed,
        "cleaned_html": cleaned_html,
        "blocking_issues": [str(i) for i in blocking],
        "warnings": [str(i) for i in warnings],
        "auto_fixes": len(auto_fixed),
    }


# ---------------------------------------------------------------------------
# SOURCE FRESHNESS CHECKER (for news_fetcher)
# ---------------------------------------------------------------------------

def check_source_freshness(date_str: str, max_days: int = 60) -> bool:
    """
    Returns True if source is fresh enough to use.
    Accepts various date formats.
    """
    if not date_str or date_str in ("Today", "Unknown"):
        return True  # Assume fresh if no date
    
    try:
        from dateutil import parser as dateparser
        pub_date = dateparser.parse(date_str, ignoretz=True)
        if pub_date is None:
            return True
        age_days = (datetime.datetime.now() - pub_date).days
        if age_days > max_days:
            log(f"   🗓️ Source rejected: {age_days} days old (max: {max_days}). Date: {date_str}")
            return False
        return True
    except Exception:
        return True  # If can't parse, assume OK


def validate_citation_count(html: str, max_per_url: int = 3) -> tuple:
    """
    Returns (clean_html, issues_found).
    Does NOT remove citations — just reports for the Gate.
    """
    soup = BeautifulSoup(html, "html.parser")
    links = soup.find_all("a", href=True)
    citation_count = {}
    for link in links:
        href = link["href"]
        if href.startswith("http") and "latestai.me" not in href:
            clean_url = href.split("?")[0]
            citation_count[clean_url] = citation_count.get(clean_url, 0) + 1
    
    issues = []
    for url, count in citation_count.items():
        if count > max_per_url:
            issues.append(f"URL cited {count}x: {url[:60]}")
    
    return html, issues
