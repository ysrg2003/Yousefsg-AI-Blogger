"""
quality_loop.py
===============
The main quality loop:
  1. Generate article (simulation)
  2. Run full audit suite
  3. Report all issues
  4. Auto-fix what can be fixed
  5. Repeat until clean
  6. Final SEO score
"""

import sys, datetime, re, json
sys.path.insert(0, '.')

import seo_quality_gate
from bs4 import BeautifulSoup
from pipeline_simulator import generate_realistic_article

# ─────────────────────────────────────────────
# EXTENDED AUDIT — beyond the Iron Gate
# ─────────────────────────────────────────────

FORBIDDEN_AI_PHRASES = [
    "in today's digital age", "in today's fast-paced world",
    "game-changer", "paradigm shift", "delve into", "poised to",
    "cutting-edge realm", "underscore", "testament to", "leverage",
    "it is important to note", "remember that", "in conclusion,",
    "as we have seen", "furthermore,", "moreover,",
    "robust", "it's worth noting",
]

SEO_TITLE_MAX_CHARS = 60
META_DESC_MAX_CHARS = 155


def audit_seo_title(html: str, title: str) -> list:
    issues = []
    if len(title) > SEO_TITLE_MAX_CHARS:
        issues.append(f"❌ TITLE TOO LONG: {len(title)} chars (max {SEO_TITLE_MAX_CHARS}) — gets truncated in Google")
    if title.isupper():
        issues.append("❌ TITLE ALL CAPS — bad UX and against Google guidelines")
    if not any(kw in title.lower() for kw in ["vs", "review", "guide", "how", "best", "2026", "pro", "ai"]):
        issues.append("⚠️  TITLE WEAK: No clear intent keyword (vs/review/guide/how/best)")
    return issues


def audit_duplicate_h1(html: str) -> list:
    soup = BeautifulSoup(html, 'html.parser')
    h1s = soup.find_all('h1')
    if len(h1s) > 1:
        return [f"❌ DUPLICATE H1 ({len(h1s)} found) — Google only reads one; kills page ranking signal"]
    if len(h1s) == 0:
        return ["❌ MISSING H1 — page has no primary heading"]
    return []


def audit_forbidden_phrases(html: str) -> list:
    issues = []
    text = BeautifulSoup(html, 'html.parser').get_text().lower()
    for phrase in FORBIDDEN_AI_PHRASES:
        if phrase in text:
            issues.append(f"❌ AI-PATTERN PHRASE: '{phrase}' — Google's AI content detector flags this")
    return issues


def audit_internal_links(html: str) -> list:
    issues = []
    soup = BeautifulSoup(html, 'html.parser')
    internal = [a for a in soup.find_all('a', href=True)
                if 'latestai.me' in a.get('href', '')]
    if len(internal) == 0:
        issues.append("⚠️  NO INTERNAL LINKS — misses PageRank flow and keeps bounce rate high")
    elif len(internal) > 8:
        issues.append(f"⚠️  TOO MANY INTERNAL LINKS ({len(internal)}) — looks like link spam")
    return issues


def audit_heading_hierarchy(html: str) -> list:
    issues = []
    soup = BeautifulSoup(html, 'html.parser')
    headings = soup.find_all(['h1','h2','h3','h4'])
    if not headings:
        return ["❌ NO HEADINGS — flat wall of text, terrible for SEO and UX"]
    h2s = soup.find_all('h2')
    h3s = soup.find_all('h3')
    if len(h2s) < 3:
        issues.append(f"⚠️  TOO FEW H2s ({len(h2s)}) — Google expects clear sections; target 4–7 H2s")
    if len(h3s) < 2:
        issues.append(f"⚠️  TOO FEW H3s ({len(h3s)}) — missing sub-sections weakens content depth signal")
    return issues


def audit_word_count(html: str) -> list:
    # Strip all HTML tags, scripts, styles before counting
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup.find_all(['script','style','noscript']): tag.decompose()
    text = soup.get_text(separator=' ')
    # Collapse whitespace
    import re
    text = re.sub(r'\s+', ' ', text).strip()
    words = len(text.split())
    if words < 900:
        return [f"❌ TOO SHORT: {words} words (minimum 1,200 for competitive AI topics)"]
    if words < 1200:
        return [f"⚠️  SHORT: {words} words — competitors average 1,800+ for this keyword tier"]
    return [f"✅ Word count: {words} words (good depth)"]


def audit_schema_markup(html: str) -> list:
    issues = []
    if 'application/ld+json' not in html:
        issues.append("❌ NO SCHEMA MARKUP — missing JSON-LD; can't get rich results (FAQ, Article)")
    else:
        if 'FAQPage' not in html:
            issues.append("⚠️  Schema missing FAQPage — FAQ rich results = huge CTR boost")
        if 'datePublished' not in html:
            issues.append("⚠️  Schema missing datePublished — critical for freshness signal")
        if 'author' not in html.lower():
            issues.append("⚠️  Schema missing author entity — needed for E-E-A-T")
    return issues


def audit_external_links(html: str) -> list:
    issues = []
    soup = BeautifulSoup(html, 'html.parser')
    ext_links = [a for a in soup.find_all('a', href=True)
                 if a['href'].startswith('http') and 'latestai.me' not in a['href']]
    noopener = [a for a in ext_links if 'noopener' in a.get('rel', [])]
    if ext_links and len(noopener) < len(ext_links) * 0.8:
        issues.append("⚠️  External links missing rel='noopener noreferrer' — security + SEO issue")
    if len(ext_links) < 3:
        issues.append("⚠️  TOO FEW EXTERNAL LINKS — Google values citations to authoritative sources")
    return issues


def audit_image_count(html: str) -> list:
    soup = BeautifulSoup(html, 'html.parser')
    imgs = [i for i in soup.find_all('img') if i.get('src','').strip()]
    if len(imgs) < 2:
        return [f"⚠️  ONLY {len(imgs)} REAL IMAGE(S) — target 3–5 images for engagement and image search traffic"]
    return [f"✅ Images: {len(imgs)} with real URLs"]


def audit_verdict_section(html: str) -> list:
    text = BeautifulSoup(html, 'html.parser').get_text().lower()
    has_verdict = any(k in text for k in ['verdict', 'final recommendation', 'bottom line', 'should you use'])
    if not has_verdict:
        return ["❌ NO VERDICT SECTION — users need a clear recommendation; boosts time-on-page"]
    return []


def audit_comparison_table(html: str) -> list:
    soup = BeautifulSoup(html, 'html.parser')
    tables = soup.find_all('table')
    if not tables:
        return ["❌ NO COMPARISON TABLE — mandatory for review/comparison articles; boosts featured snippets"]
    # Check data-label attributes for mobile responsiveness
    tds = soup.find_all('td')
    labeled = [td for td in tds if td.get('data-label')]
    if tds and len(labeled) < len(tds) * 0.5:
        return ["⚠️  TABLE MISSING data-label — table is not mobile-responsive"]
    return []


def audit_faq_section(html: str) -> list:
    text = BeautifulSoup(html, 'html.parser').get_text().lower()
    soup = BeautifulSoup(html, 'html.parser')
    faq_headers = [h for h in soup.find_all(['h3','h4'])
                   if any(q in h.get_text().lower() for q in ['?','faq','question','common'])]
    if len(faq_headers) < 2:
        return ["⚠️  WEAK FAQ SECTION — FAQ rich results require 2+ proper Q&A pairs with schema"]
    return []


def audit_author_box(html: str) -> list:
    soup = BeautifulSoup(html, 'html.parser')
    text = html.lower()
    has_bio = 'yousef s.' in text or 'author' in text
    has_photo = bool(soup.find('img', attrs={'alt': lambda a: a and 'yousef' in (a or '').lower()}))
    if not has_bio:
        return ["❌ NO AUTHOR BOX — E-E-A-T killer; Google demotes articles without clear authorship"]
    return []


# ─────────────────────────────────────────────
# SCORING ENGINE
# ─────────────────────────────────────────────

CATEGORY_WEIGHTS = {
    "E-E-A-T":       {"weight": 30, "checks": [audit_duplicate_h1, audit_forbidden_phrases, audit_schema_markup, audit_author_box, audit_verdict_section]},
    "Technical SEO": {"weight": 25, "checks": [audit_seo_title, audit_heading_hierarchy, audit_external_links]},
    "Content":       {"weight": 25, "checks": [audit_word_count, audit_comparison_table, audit_faq_section]},
    "UX/CRO":        {"weight": 20, "checks": [audit_internal_links, audit_image_count]},
}

def compute_seo_score(html: str, title: str) -> dict:
    results = {}
    total_weighted = 0
    total_weight = 0

    for category, cfg in CATEGORY_WEIGHTS.items():
        cat_issues = []
        for check_fn in cfg["checks"]:
            if check_fn == audit_seo_title:
                cat_issues.extend(check_fn(html, title))
            else:
                cat_issues.extend(check_fn(html))

        errors = [i for i in cat_issues if i.startswith("❌")]
        warns  = [i for i in cat_issues if i.startswith("⚠️")]
        oks    = [i for i in cat_issues if i.startswith("✅")]

        # Score: start at 100, -20 per error, -8 per warning
        cat_score = max(0, 100 - len(errors)*20 - len(warns)*8)
        weighted = cat_score * cfg["weight"] / 100
        total_weighted += weighted
        total_weight += cfg["weight"]

        results[category] = {
            "score": cat_score,
            "weight": cfg["weight"],
            "issues": cat_issues,
        }

    overall = round(total_weighted * 100 / total_weight) if total_weight else 0
    return {"overall": overall, "categories": results}


# ─────────────────────────────────────────────
# AUTO-FIX ENGINE
# ─────────────────────────────────────────────

def auto_fix_html(html: str, issues: list, gate_result: dict) -> str:
    """Apply all possible auto-fixes to the HTML."""
    soup = BeautifulSoup(html, 'html.parser')

    # Fix 1: Remove duplicate H1
    h1s = soup.find_all('h1')
    if len(h1s) > 1:
        for extra_h1 in h1s[1:]:
            extra_h1.decompose()
        print("   🔧 AUTO-FIX: Removed duplicate H1 tags")

    # Fix 2: Remove forbidden AI phrases
    text_nodes_fixed = 0
    for tag in soup.find_all(string=True):
        original = tag.string if tag.string else str(tag)
        new_text = original
        for phrase in FORBIDDEN_AI_PHRASES:
            if phrase in new_text.lower():
                # Context-sensitive replacements
                replacements = {
                    "in today's digital age": "Today",
                    "in today's fast-paced world": "In 2026",
                    "game-changer": "significant advancement",
                    "paradigm shift": "major shift",
                    "delve into": "explore",
                    "cutting-edge realm": "field",
                    "underscore": "highlight",
                    "testament to": "proof of",
                    "leverage": "use",
                    "it is important to note": "",
                    "remember that": "",
                    "in conclusion,": "",
                    "as we have seen,": "",
                    "furthermore,": "Also,",
                    "moreover,": "Also,",
                    "robust": "reliable",
                    "poised to": "set to",
                    "it's worth noting": "",
                }
                for old, new in replacements.items():
                    if old in new_text.lower():
                        # Case-insensitive replace
                        import re
                        new_text = re.sub(re.escape(old), new, new_text, flags=re.IGNORECASE)
                        text_nodes_fixed += 1
        if new_text != original and tag.parent:
            try:
                tag.replace_with(new_text)
            except Exception:
                pass
    if text_nodes_fixed:
        print(f"   🔧 AUTO-FIX: Replaced {text_nodes_fixed} forbidden AI phrases")

    # Fix 3: Add rel="noopener noreferrer" to external links
    ext_links_fixed = 0
    for a in soup.find_all('a', href=True):
        href = a['href']
        if href.startswith('http') and 'latestai.me' not in href:
            existing_rel = a.get('rel', [])
            if isinstance(existing_rel, str):
                existing_rel = existing_rel.split()
            if 'noopener' not in existing_rel:
                a['rel'] = 'noopener noreferrer'
                a['target'] = '_blank'
                ext_links_fixed += 1
    if ext_links_fixed:
        print(f"   🔧 AUTO-FIX: Added rel='noopener noreferrer' to {ext_links_fixed} external links")

    # Fix 4: Use gate's cleaned HTML (applies its own auto-fixes)
    html = gate_result['cleaned_html']
    soup = BeautifulSoup(html, 'html.parser')

    # Re-apply structural fixes on gate-cleaned HTML
    h1s = soup.find_all('h1')
    if len(h1s) > 1:
        for extra_h1 in h1s[1:]:
            extra_h1.decompose()

    return str(soup)


# ─────────────────────────────────────────────
# MAIN LOOP
# ─────────────────────────────────────────────

def run_quality_loop(topic="Gemini 2.5 Pro vs GPT-5", max_iterations=4):
    print(f"\n{'█'*65}")
    print(f"  QUALITY LOOP — Topic: {topic}")
    print(f"  Target: SEO Score ≥ 85 | Gate: PASS | Zero blocking issues")
    print(f"{'█'*65}")

    history = []

    for iteration in range(1, max_iterations + 1):
        print(f"\n\n{'='*65}")
        print(f"  ITERATION {iteration}/{max_iterations}")
        print(f"{'='*65}")

        # Step 1: Generate article
        print(f"\n📝 Generating article (iteration {iteration})...")
        html = generate_realistic_article(topic, iteration)
        title = f"{topic}: The Definitive 2026 Comparison"
        print(f"   Article generated: {len(html):,} characters")

        # Step 2: Run Iron Gate
        print(f"\n🔒 Running Iron Gate...")
        gate_result = seo_quality_gate.run_quality_gate(html, title, datetime.date.today())

        # Step 3: Run full SEO audit
        print(f"\n🔬 Running full SEO audit...")
        all_issues = []
        all_issues.extend(audit_duplicate_h1(html))
        all_issues.extend(audit_forbidden_phrases(html))
        all_issues.extend(audit_seo_title(html, title))
        all_issues.extend(audit_heading_hierarchy(html))
        all_issues.extend(audit_word_count(html))
        all_issues.extend(audit_schema_markup(html))
        all_issues.extend(audit_external_links(html))
        all_issues.extend(audit_image_count(html))
        all_issues.extend(audit_comparison_table(html))
        all_issues.extend(audit_faq_section(html))
        all_issues.extend(audit_internal_links(html))
        all_issues.extend(audit_verdict_section(html))
        all_issues.extend(audit_author_box(html))

        score_data = compute_seo_score(html, title)

        # Print full audit report
        print(f"\n{'─'*65}")
        print(f"  AUDIT REPORT — Iteration {iteration}")
        print(f"{'─'*65}")
        print(f"\n  🎯 OVERALL SEO SCORE: {score_data['overall']}/100")
        print(f"  🔒 IRON GATE: {'✅ PASSED' if gate_result['passed'] else '❌ BLOCKED'}")
        print(f"  🔧 AUTO-FIXED: {gate_result['auto_fixes']} issues silently cleaned")

        print(f"\n  CATEGORY SCORES:")
        for cat, data in score_data['categories'].items():
            bar = "█" * (data['score'] // 10) + "░" * (10 - data['score'] // 10)
            print(f"    {cat:<16} [{bar}] {data['score']:>3}/100 (weight: {data['weight']}%)")

        errors   = [i for i in all_issues if i.startswith("❌")]
        warnings = [i for i in all_issues if i.startswith("⚠️")]
        oks      = [i for i in all_issues if i.startswith("✅")]

        if errors:
            print(f"\n  BLOCKING ISSUES ({len(errors)}):")
            for e in errors:
                print(f"    {e}")

        if warnings:
            print(f"\n  WARNINGS ({len(warnings)}):")
            for w in warnings:
                print(f"    {w}")

        if oks:
            print(f"\n  PASSING ({len(oks)}):")
            for o in oks:
                print(f"    {o}")

        gate_blocks = gate_result['blocking_issues']
        if gate_blocks:
            print(f"\n  GATE BLOCKS ({len(gate_blocks)}):")
            for b in gate_blocks:
                print(f"    🚫 {b}")

        history.append({
            "iteration": iteration,
            "score": score_data['overall'],
            "gate_passed": gate_result['passed'],
            "errors": len(errors),
            "warnings": len(warnings),
            "gate_blocks": len(gate_blocks),
        })

        # Step 4: Check if we're done
        passed_all = (
            gate_result['passed'] and
            len(errors) == 0 and
            score_data['overall'] >= 85
        )

        if passed_all:
            print(f"\n\n{'█'*65}")
            print(f"  ✅ SUCCESS AT ITERATION {iteration}!")
            print(f"  Score: {score_data['overall']}/100 | Gate: PASSED | Errors: 0")
            print(f"{'█'*65}")
            break

        # Step 5: Auto-fix and iterate
        if iteration < max_iterations:
            print(f"\n\n  🔧 APPLYING AUTO-FIXES for iteration {iteration+1}...")
            fixed_html = auto_fix_html(html, all_issues, gate_result)
            print(f"  ➡️  Moving to iteration {iteration+1}...")

    # Final summary
    print(f"\n\n{'█'*65}")
    print(f"  LOOP SUMMARY")
    print(f"{'█'*65}")
    print(f"\n  {'Iter':<6} {'Score':<8} {'Gate':<10} {'Errors':<10} {'Warnings':<10} {'Gate Blocks'}")
    print(f"  {'─'*60}")
    for h in history:
        gate_str = "✅ PASS" if h['gate_passed'] else "❌ FAIL"
        print(f"  {h['iteration']:<6} {h['score']:<8} {gate_str:<10} {h['errors']:<10} {h['warnings']:<10} {h['gate_blocks']}")

    final = history[-1]
    print(f"\n  Final score: {final['score']}/100")
    if final['gate_passed'] and final['errors'] == 0 and final['score'] >= 85:
        print(f"  Status: ✅ PRODUCTION READY")
    elif final['score'] >= 70:
        print(f"  Status: ⚠️  NEEDS MORE WORK (below 85 threshold)")
    else:
        print(f"  Status: ❌ NOT READY — major issues remain")

    return history


if __name__ == "__main__":
    run_quality_loop("Gemini 2.5 Pro vs GPT-5", max_iterations=4)
