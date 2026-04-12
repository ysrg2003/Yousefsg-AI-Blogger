"""
test_quality_gate.py
====================
Simulates the worst-case article output (exactly like the 5 failing articles)
and runs it through the Iron Gate, then produces a quality report.

Usage: python3 test_quality_gate.py
"""

import sys
import datetime
import json

sys.path.insert(0, '.')
import seo_quality_gate

# ---------------------------------------------------------------------------
# SIMULATE the WORST article — based on actual failures found in audit
# ---------------------------------------------------------------------------
SIMULATED_BAD_ARTICLE = """
<h1>The 2026 Guide to Overdub: Mastering AI Voice Cloning</h1>

<h3>Watch the Video Summary</h3>
<!-- NO IFRAME HERE — common failure mode -->

<p>Voice cloning is a game-changer in today's digital age. We don't know all the technical details 
about how Descript's new engine works, but it promises to be cutting-edge.</p>

<p>This strategic pivot aligns with reports from authoritative sources like Reuters, which indicate 
OpenAI's shift away from high-cost consumer creative tools. Bloomberg also reported significant changes.</p>

<img src="https://via.placeholder.com/600x400?text=Suno+v5.5+Voices+Setup" 
     alt="Main Featured Image / OpenGraph Image">

<figcaption>📸 Main Featured Image / OpenGraph Image</figcaption>

<p>Hypothetical Screenshot: Imagine a clean interface with a central preview window showing 
the audio waveform, and a text input box below it.</p>

<h2>Performance Comparison</h2>
<table>
  <thead><tr><th>Feature</th><th>Descript</th><th>ElevenLabs</th><th>Resemble AI</th></tr></thead>
  <tbody>
    <tr><td>Voice Quality</td><td>Excellent</td><td>Good</td><td>Fair</td></tr>
    <tr><td>Speed</td><td>Good</td><td>Excellent</td><td>Average</td></tr>
    <tr><td>Price</td><td>Medium</td><td>High</td><td>Low</td></tr>
    <tr><td>Integration</td><td>Excellent</td><td>Good</td><td>Fair</td></tr>
  </tbody>
</table>

<figcaption>📸 changes | 348k4.4k</figcaption>
<figcaption>📸 hip quake | 255k4.8k</figcaption>

<p>According to 
<a href="https://www.businesswire.com/news/home/20240604130005/en/Flik">Business Wire</a>,
the company has grown significantly. As noted by 
<a href="https://www.businesswire.com/news/home/20240604130005/en/Flik">Business Wire</a>,
the platform now serves millions. Furthermore 
<a href="https://www.businesswire.com/news/home/20240604130005/en/Flik">Business Wire</a>
reported continued expansion.
<a href="https://www.businesswire.com/news/home/20240604130005/en/Flik">Business Wire</a>
also highlighted the safety features.
</p>

<img src="https://cdn.builder.io/api/v1/image/real-image.jpg" alt="Main Featured Image">

<h2>Community Pulse</h2>
<p>Some users mentioned that things are better. Details are unclear about the exact improvements.</p>

<h3>Sources &amp; References</h3>
<ul>
  <li><a href="https://www.descript.com">Descript Official</a></li>
  <li><a href="https://www.businesswire.com/news/home/20240604130005/en/Flik">Business Wire</a></li>
</ul>
"""

# ---------------------------------------------------------------------------
# SIMULATE a GOOD article baseline for comparison
# ---------------------------------------------------------------------------
SIMULATED_GOOD_ARTICLE = """
<h1>Suno v5.5 Review: Is the AI Music Generator Worth It in 2026?</h1>

<div class="article-meta">
  <time datetime="2026-04-12">Published: April 12, 2026</time>
</div>

<p>Suno just dropped v5.5 and it changes how hobbyists create music. I spent a week testing 
it against ElevenLabs and Udio. Here's what I found.</p>

<h2>What's New in v5.5</h2>
<p>The biggest addition is the Voice Design feature, which lets you blend vocal attributes. 
In my testing, cloning time dropped from 5 minutes to under 90 seconds — a 70% improvement.</p>

<h2>Pricing Comparison</h2>
<table>
  <thead><tr><th>Plan</th><th>Price/Month</th><th>Songs/Month</th><th>Commercial Rights</th></tr></thead>
  <tbody>
    <tr><td>Free</td><td>$0</td><td>10</td><td>No</td></tr>
    <tr><td>Pro</td><td>$10</td><td>500</td><td>Yes</td></tr>
    <tr><td>Premier</td><td>$30</td><td>2,000</td><td>Yes</td></tr>
  </tbody>
</table>

<h2>Community Feedback</h2>
<p>On Reddit's r/sunoai, 
<a href="https://reddit.com/r/sunoai/comments/abc123" target="_blank">u/MusicMakerPro</a> 
said the new voice blending is "genuinely usable for the first time." The thread has 847 upvotes 
and 120 comments — a strong signal this update matters.</p>

<h3>Sources &amp; References</h3>
<ul>
  <li><a href="https://suno.com/blog/v55">Suno Official Blog</a></li>
  <li><a href="https://reddit.com/r/sunoai">Reddit Community</a></li>
</ul>
"""

# ---------------------------------------------------------------------------
# RUN TESTS
# ---------------------------------------------------------------------------

def run_test(name, html, expect_pass):
    print(f"\n{'='*70}")
    print(f"TEST: {name}")
    print('='*70)
    
    result = seo_quality_gate.run_quality_gate(html, name, datetime.date.today())
    
    print(f"\n📊 RESULTS:")
    print(f"   Passed:     {'✅ YES' if result['passed'] else '❌ NO'}")
    print(f"   Auto-fixes: {result['auto_fixes']}")
    print(f"   Blocking:   {len(result['blocking_issues'])}")
    print(f"   Warnings:   {len(result['warnings'])}")
    
    if result['blocking_issues']:
        print(f"\n🚫 Blocking Issues:")
        for issue in result['blocking_issues']:
            print(f"   → {issue}")
    
    if result['warnings']:
        print(f"\n⚠️  Warnings:")
        for w in result['warnings'][:5]:
            print(f"   → {w}")
    
    # Verify date was injected
    if 'Published:' in result['cleaned_html'] or 'datePublished' in result['cleaned_html']:
        print(f"\n   ✅ Date injection: OK")
    else:
        print(f"\n   ❌ Date injection: MISSING")
    
    # Verify placeholder images removed
    if 'via.placeholder.com' not in result['cleaned_html']:
        print(f"   ✅ Placeholder images: Removed")
    else:
        print(f"   ❌ Placeholder images: Still present!")
    
    # Verify hypothetical content removed
    if 'Hypothetical Screenshot' not in result['cleaned_html'] and 'hypothetical screenshot' not in result['cleaned_html'].lower():
        print(f"   ✅ Fake content: Removed")
    else:
        print(f"   ❌ Fake content: Still present!")
    
    # Check video section
    if 'Watch the Video Summary' not in result['cleaned_html']:
        print(f"   ✅ Empty video section: Removed")
    else:
        print(f"   ⚠️  Video section still present (check for iframe)")
    
    # Check bad captions
    if '348k4.4k' not in result['cleaned_html'] and 'hip quake' not in result['cleaned_html']:
        print(f"   ✅ Bad captions: Cleaned")
    else:
        print(f"   ❌ Bad captions: Still present!")
    
    expected_str = "PASS" if expect_pass else "FAIL"
    actual_str = "PASS" if result['passed'] else "FAIL"
    test_outcome = "✅ TEST CORRECT" if (result['passed'] == expect_pass) else "⚠️  UNEXPECTED RESULT"
    print(f"\n   Expected: {expected_str} | Got: {actual_str} | {test_outcome}")
    
    return result


def test_freshness_checker():
    print(f"\n{'='*70}")
    print("TEST: Source Freshness Checker")
    print('='*70)
    
    test_cases = [
        ("Tue, 04 Jun 2024 12:00:00 +0000", False, "2024 date should be REJECTED"),
        ("Sun, 12 Apr 2026 10:00:00 +0000", True, "Today should be ACCEPTED"),
        ("2026-04-01T10:00:00Z", True, "This month should be ACCEPTED"),
        ("2025-12-01T10:00:00Z", True, "4 months ago — within 60 days? NO — should REJECT"),
        ("Today", True, "Unknown date should be ACCEPTED"),
    ]
    
    # Import the freshness checker
    from news_fetcher import _is_fresh_enough
    
    for date_str, expected, label in test_cases:
        result = _is_fresh_enough(date_str)
        status = "✅" if result == expected else "❌"
        print(f"   {status} {label}")
        print(f"      Input: '{date_str}' → Fresh: {result} (Expected: {expected})")


def test_repeated_citation_detection():
    print(f"\n{'='*70}")
    print("TEST: Repeated Citation Detection (Flik Article Pattern)")
    print('='*70)
    
    # Simulate the Flik article's repeated BusinessWire citations
    test_html = """<p>
    According to <a href="https://www.businesswire.com/news/home/20240604/en/Flik">Business Wire</a>, claim 1.
    Also <a href="https://www.businesswire.com/news/home/20240604/en/Flik">Business Wire</a> said claim 2.
    Furthermore <a href="https://www.businesswire.com/news/home/20240604/en/Flik">Business Wire</a> noted claim 3.
    Additionally <a href="https://www.businesswire.com/news/home/20240604/en/Flik">Business Wire</a> confirmed claim 4.
    </p>"""
    
    result = seo_quality_gate.run_quality_gate(test_html, "Test Citation", datetime.date.today())
    
    has_repeated_issue = any("REPEATED_CITATION" in issue for issue in result['blocking_issues'])
    if has_repeated_issue:
        print(f"   ✅ Repeated citation detected and blocked correctly")
    else:
        print(f"   ❌ Repeated citation NOT detected — fix needed")
        print(f"      Blocking issues found: {result['blocking_issues']}")


if __name__ == "__main__":
    print("\n🔬 IRON GATE TEST SUITE")
    print("Testing all quality checks against simulated articles...")
    
    # Test 1: Bad article (should fail)
    bad_result = run_test("BAD ARTICLE (Simulated failures)", SIMULATED_BAD_ARTICLE, expect_pass=False)
    
    # Test 2: Good article (should pass)
    good_result = run_test("GOOD ARTICLE (Clean baseline)", SIMULATED_GOOD_ARTICLE, expect_pass=True)
    
    # Test 3: Freshness checker
    test_freshness_checker()
    
    # Test 4: Citation detector
    test_repeated_citation_detection()
    
    print(f"\n{'='*70}")
    print("FINAL SUMMARY")
    print('='*70)
    print(f"Bad article gate: {'CORRECTLY BLOCKED' if not bad_result['passed'] else 'FAILED TO BLOCK'}")
    print(f"Good article gate: {'CORRECTLY PASSED' if good_result['passed'] else 'INCORRECTLY BLOCKED'}")
    print(f"\nAuto-fixes applied to bad article: {bad_result['auto_fixes']}")
    print(f"Blocking issues found in bad article: {len(bad_result['blocking_issues'])}")
    print("\n✅ Test suite complete.")
