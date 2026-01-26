# FILE: content_validator_pro.py
# ROLE: Content Quality Assurance & Repair
# UPDATED: Added TOC Link Sanitizer to fix the "External Link" disaster.

import re
import requests
import logging
import json
from bs4 import BeautifulSoup
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_fixed
from urllib.parse import urlparse

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [CORE-SURGEON-3.0] - %(message)s')
logger = logging.getLogger("CoreSurgeon")

class AdvancedContentValidator:
    def __init__(self, google_client, model_name="gemini-2.5-flash"):
        self.client = google_client
        self.model_name = model_name
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 ProValidator/3.0'
        })

    def _clean_json_text(self, text):
        if not text: return "{}"
        clean = text.replace("```json", "").replace("```", "").strip()
        return clean

    # --- NEW FIX: TOC SANITIZER ---
    def sanitize_toc_links(self, html_content):
        """
        Fixes the fatal SEO error where TOC links point to external sites.
        Converts 'https://external.com/page#section' to '#section'.
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find all links that have a hash (#) in them
        for link in soup.find_all('a', href=True):
            href = link['href']
            if '#' in href and len(href) > 1:
                # If it's a full URL ending with a hash (The Bug)
                if href.startswith('http'):
                    anchor = href.split('#')[-1]
                    link['href'] = f"#{anchor}"
                    logger.info(f"🔧 Fixed broken TOC link: {href} -> #{anchor}")
                    
                    # Ensure the target ID exists, if not, create it on the nearest header
                    # This is complex, so we rely on the AI usually putting IDs on headers.
                    # If not, the link won't scroll, but at least it won't exit the site.
        
        return str(soup)

    def perform_fact_surgery(self, html_content, full_source_text):
        soup = BeautifulSoup(html_content, 'html.parser')
        elements = soup.find_all(['p', 'td', 'li', 'span', 'h3'])
        chunks_to_verify = []
        pattern = r'(\d+%?|\$\d+|\bv\d+\.\d+|\d+\s(hours|GB|TB)|\b(vs|better than|faster than|release date)\b)'
        
        for el in elements:
            text = el.get_text()
            if len(text) < 300 and re.search(pattern, text, re.IGNORECASE):
                chunks_to_verify.append(str(el))

        if not chunks_to_verify: return html_content
        chunks_to_verify = chunks_to_verify[:50]

        logger.info(f"💉 Starting Fact Surgery on {len(chunks_to_verify)} sensitive elements...")
        
        prompt = f"""
        TASK: Technical Content Surgery.
        TRUTH DATA: {full_source_text[:20000]}
        DRAFT HTML ELEMENTS: {json.dumps(chunks_to_verify)}
        INSTRUCTIONS:
        1. Compare numbers/facts in HTML elements with TRUTH DATA.
        2. IF WRONG: Rewrite the element with CORRECT info. Keep HTML tags.
        3. IF HALLUCINATED: Rewrite as a logical inference or delete the specific claim.
        4. IF CORRECT: Return null or skip.
        OUTPUT: JSON dictionary {{ "original_html_string": "corrected_html_string" }}
        """
        try:
            resp = self.client.models.generate_content(
                model=self.model_name, 
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1)
            )
            json_text = self._clean_json_text(resp.text)
            corrections = json.loads(json_text)
            
            final_html = str(soup)
            for original, corrected in corrections.items():
                if original in final_html and corrected and corrected != original:
                    clean_fix = re.sub(r'</?(html|body|head)>', '', corrected, flags=re.IGNORECASE)
                    final_html = final_html.replace(original, clean_fix)
            return final_html
        except Exception as e:
            logger.error(f"❌ Fact Surgery Failed: {e}")
            return html_content

    def rebuild_damaged_widgets(self, html_content, full_source_text):
        if "comparison-table" not in html_content: return html_content
        soup = BeautifulSoup(html_content, 'html.parser')
        modified = False
        table = soup.find('table', class_='comparison-table')
        if table:
            cells = table.find_all('td')
            if cells:
                empty_cells = [c for c in cells if len(c.get_text(strip=True)) < 2 or "n/a" in c.get_text(strip=True).lower()]
                if len(empty_cells) > (len(cells) / 2):
                    logger.warning("🔨 Rebuilding low-quality table...")
                    new_table = self._generate_element_from_ai("Comparison Table", full_source_text)
                    if new_table:
                        new_soup = BeautifulSoup(new_table, 'html.parser')
                        if new_soup.find('table'): table.replace_with(new_soup.find('table'))
                        else: table.replace_with(new_soup)
                        modified = True
        return str(soup) if modified else html_content

    @retry(stop=stop_after_attempt(2), wait=wait_fixed(2))
    def _generate_element_from_ai(self, element_type, source_text):
        prompt = f"REBUILD TASK: Create a high-quality HTML {element_type} using ONLY facts from: {source_text[:8000]}. Use clean CSS classes. Output ONLY HTML."
        try:
            resp = self.client.models.generate_content(model=self.model_name, contents=prompt)
            return resp.text.replace("```html", "").replace("```", "").strip()
        except: return None

    def restore_link_integrity(self, html_content, sources_metadata):
        soup = BeautifulSoup(html_content, 'html.parser')
        links = soup.find_all('a', href=True)
        for link in links:
            url = link['href']
            if any(x in url for x in ["latestai.me", "facebook.com", "instagram.com", "x.com", "youtube.com", "reddit.com"]) or url.startswith('#'):
                continue
            try:
                r = self.session.head(url, timeout=3, allow_redirects=True)
                if r.status_code >= 400: raise Exception("Dead Link")
            except:
                logger.warning(f"🩹 Healing broken link: {url}")
                parsed = urlparse(url)
                domain = parsed.netloc.replace('www.', '')
                replacement = None
                for src in sources_metadata:
                    if domain in src['url']:
                        replacement = src['url']
                        break
                if replacement: link['href'] = replacement
                elif sources_metadata: link['href'] = sources_metadata[0]['url']
        return str(soup)

    def verify_quotes(self, html_content, source_text):
        soup = BeautifulSoup(html_content, 'html.parser')
        quotes = soup.find_all('blockquote')
        for bq in quotes:
            text = bq.get_text(strip=True)
            words = text.split()
            if len(words) > 3 and " ".join(words[:4]).lower() not in source_text.lower():
                logger.warning("⚠️ Replacing hallucinated quote...")
                real_quote = self._find_real_quote_from_ai(source_text)
                if real_quote:
                    new_soup = BeautifulSoup(real_quote, 'html.parser')
                    if new_soup.find('blockquote'): bq.replace_with(new_soup.find('blockquote'))
                    else: bq.replace_with(new_soup)
                else: bq.decompose()
        return str(soup)

    def _find_real_quote_from_ai(self, source_text):
        prompt = f"EXTRACT VERBATIM QUOTE: Find one powerful, real sentence from this text: {source_text[:5000]}. Return as HTML <blockquote>. Output ONLY HTML."
        try:
            resp = self.client.models.generate_content(model=self.model_name, contents=prompt)
            return resp.text.replace("```html", "").replace("```", "").strip()
        except: return None

    def run_professional_validation(self, html_content, full_source_text, sources_metadata):
        logger.info("🛡️ CORE SURGEON 3.0: COMMENCING FULL RESTORATION...")
        
        # 1. Fix the TOC Disaster FIRST
        html = self.sanitize_toc_links(html_content)
        
        # 2. Facts
        html = self.perform_fact_surgery(html, full_source_text)
        
        # 3. Widgets
        html = self.rebuild_damaged_widgets(html, full_source_text)
        
        # 4. Quotes
        html = self.verify_quotes(html, full_source_text)
        
        # 5. Links
        html = self.restore_link_integrity(html, sources_metadata)
        
        # Final Cleanup
        html = re.sub(r'</?(html|body|head|meta|title)>', '', html, flags=re.IGNORECASE)
        html = re.sub(r'>\s+<', '><', html).strip()
        
        logger.info("✅ RESTORATION COMPLETE.")
        return html
