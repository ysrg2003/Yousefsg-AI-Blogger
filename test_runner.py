# test_runner.py
# Simple runner used by GitHub Actions workflow to call get_community_intel
import os
from reddit_manager import get_community_intel

q = os.getenv("TEST_KEYWORD") or "Sora 2 OpenAI discussion"
print("Searching for:", q)

text, media = get_community_intel(q)

print("=== TEXT LENGTH ===", len(text))
print("=== MEDIA COUNT ===", len(media))

if text:
    print("=== SAMPLE TEXT (first 800 chars) ===")
    print(text[:800])

if media:
    print("=== SAMPLE MEDIA (first 5) ===")
    for m in media[:5]:
        print(m)
