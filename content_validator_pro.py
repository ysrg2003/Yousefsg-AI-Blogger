import re
import requests
import logging
import json
import time
from bs4 import BeautifulSoup
from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_fixed
from urllib.parse import urlparse
from api_manager import key_manager  # <--- IMPORT KEY MANAGER
from config import MIN_UNIQUE_SCORE, MIN_READABILITY_SCORE, MAX_AI_DETECTION_SCORE

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [CORE-SURGEON-3.0] - %(message)s')
logger = logging.getLogger("CoreSurgeon")

class AdvancedContentValidator:
    def __init__(self, model_name="gemini-2.5-flash"):
        self.model_name = model_name
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 ProValidator/3.0'
        })

    def _get_client(self):
        """Generates a fresh client using the currently active API key."""
        key = key_manager.get_current_key()
        return genai.Client(api_key=key)

    def _safe_generate(self, prompt, config=None):
        """
        The Core Protection Mechanism:
        Wraps the API call. If a 429/Quota error occurs, it switches keys and retries.
        """
        max_retries = len(key_manager.keys) + 2
        for attempt in range(max_retries):
            client = self._get_client()
            try:
                if config:
                    return client.models.generate_content(model=self.model_name, contents=prompt, config=config)
                else:
                    return client.models.generate_content(model=self.model_name, contents=prompt)
            except Exception as e:
                error_str = str(e).lower()
                if "429" in error_str or "quota" in error_str or "exhausted" in error_str:
                    logger.warning(f"      ⚠️ Validator Quota Error (Key #{key_manager.current_index + 1}). Switching Key...")
                    if key_manager.switch_key():
                        time.sleep(2) # Cool down slightly
                        continue # Retry loop with new key
                    else:
                        logger.error("      ❌ FATAL: All keys exhausted during validation.")
                        raise e
                else:
                    raise e
        return None

    def _clean_json_text(self, text):
        if not text: return "{}"
        clean = text.replace("```json", "").replace("```", "").strip()
        return clean

    def inject_ids_and_rebuild_toc(self, html_content):
        soup = BeautifulSoup(html_content, 'html.parser')
        headers = soup.find_all(['h2', 'h3'])
        if not headers: return html_content

        toc_items = []
        for i, header in enumerate(headers):
            header_id = f"section-{i+1}"
            header['id'] = header_id
            toc_items.append({'id': header_id, 'text': header.get_text(strip=True), 'tag': header.name})

        toc_div = soup.find('div', class_='toc-box')
        if not toc_div:
            toc_div = soup.new_tag('div', attrs={'class': 'toc-box'})
            first_p = soup.find('p')
            if first_p: first_p.insert_after(toc_div)
            else: soup.insert(0, toc_div)

        toc_div.clear()
        toc_title = soup.new_tag('h3')
        toc_title.string = "Table of Contents"
        toc_div.append(toc_title)
        
        toc_ul = soup.new_tag('ul')
        for item in toc_items:
            li = soup.new_tag('li')
            a = soup.new_tag('a', href=f"#{item['id']}")
            a.string = item['text']
            if item['tag'] == 'h3': li['style'] = "margin-left: 20px; list-style-type: circle;"
            li.append(a)
            toc_ul.append(li)
            
        toc_div.append(toc_ul)
        return str(soup)

    def style_ai_generated_sources(self, html_content):
        soup = BeautifulSoup(html_content, 'html.parser')
        targets = ['sources', 'references', 'bibliography', 'citations', 'sources & references']
        
        for header in soup.find_all(['h2', 'h3', 'h4', 'h5']):
            text = header.get_text().strip().lower()
            if any(t in text for t in targets):
                next_elem = header.find_next_sibling()
                if next_elem and next_elem.name in ['ul', 'ol']:
                    logger.info(f"🎨 Styling AI Sources section: {text}")
                    wrapper = soup.new_tag('div', attrs={'class': 'ai-sources-box'})
                    header.insert_before(wrapper)
                    wrapper.append(header)
                    wrapper.append(next_elem)
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
            resp = self._safe_generate(
                prompt,
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
        soup = BeautifulSoup(html_content, 'html.parser')
        modified = False
        
        if not soup.find('table'):
            new_table = self._generate_element_from_ai("Comparison Table", full_source_text)
            if new_table and "<table>" in new_table:
                headers = soup.find_all('h2')
                if len(headers) >= 2:
                    headers[1].insert_after(BeautifulSoup(new_table, 'html.parser'))
                    modified = True
        
        table = soup.find('table', class_='comparison-table')
        if table:
            cells = table.find_all('td')
            if cells:
                empty_cells = [c for c in cells if len(c.get_text(strip=True)) < 2 or "n/a" in c.get_text(strip=True).lower()]
                if len(empty_cells) > (len(cells) / 2):
                    new_table = self._generate_element_from_ai("Comparison Table", full_source_text)
                    if new_table:
                        new_soup = BeautifulSoup(new_table, 'html.parser')
                        if new_soup.find('table'): table.replace_with(new_soup.find('table'))
                        else: table.replace_with(new_soup)
                        modified = True
                        
        return str(soup) if modified else html_content

    def _generate_element_from_ai(self, element_type, source_text):
        prompt = f"REBUILD TASK: Create a high-quality HTML {element_type} using ONLY facts from: {source_text[:8000]}. Use clean CSS classes. Output ONLY HTML."
        try:
            resp = self._safe_generate(prompt)
            return resp.text.replace("```html", "").replace("```", "").strip()
        except: return None

    def restore_link_integrity(self, html_content, sources_metadata):
        soup = BeautifulSoup(html_content, 'html.parser')
        links = soup.find_all('a', href=True)
        
        TRUSTED_DOMAINS = [
            "reddit.com", "youtube.com", "youtu.be", "twitter.com", "x.com", 
            "facebook.com", "instagram.com", "linkedin.com", "t.co", "discord.com",
            "discord.gg", "github.com", "google.com", "wikipedia.org"
        ]

        for link in links:
            url = link['href']
            
            if url.startswith('www.'):
                url = 'https://' + url
                link['href'] = url
            
            if any(x in url for x in ["latestai.me", "#", "javascript:", "mailto:"]) or not url.startswith('http'):
                continue

            if any(domain in url.lower() for domain in TRUSTED_DOMAINS):
                continue 

            try:
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
                r = self.session.head(url, headers=headers, timeout=3, allow_redirects=True)
                
                if r.status_code in [404, 500, 502, 503]: 
                    raise Exception("Dead Link")
            except:
                parsed = urlparse(url)
                domain = parsed.netloc.replace('www.', '')
                replacement = None
                
                if sources_metadata:
                    for src in sources_metadata:
                        if domain in src['url']:
                            replacement = src['url']
                            break
                    
                    if replacement: 
                        link['href'] = replacement
                    else:
                        pass 

        return str(soup)

    def _calculate_readability(self, text):
        words = re.findall(r'\b\w+\b', text.lower())
        sentences = re.split(r'[.!?]', text)
        syllables = sum([self._count_syllables(word) for word in words])

        if len(words) == 0 or len(sentences) == 0: return 0

        score = 0.39 * (len(words) / len(sentences)) + 11.8 * (syllables / len(words)) - 15.59
        return max(0, round(score))

    def _count_syllables(self, word):
        word = word.lower()
        count = 0
        vowels = "aeiouy"
        if word and word[0] in vowels: count += 1
        for index in range(1, len(word)): 
            if word[index] in vowels and word[index - 1] not in vowels: count += 1
        if word.endswith("e"): count -= 1
        if count == 0: count += 1
        return count

    def _check_ai_detection(self, text):
        ai_keywords = ["as an AI language model", "I cannot", "in conclusion", "therefore", "however"]
        words = text.split()
        if not words: return 0.0
        score = sum(1 for keyword in ai_keywords if keyword in text.lower()) / len(words)
        return score * 10 

    def _check_uniqueness(self, html_content, full_source_text):
        soup = BeautifulSoup(html_content, 'html.parser')
        generated_text = soup.get_text()

        def get_ngrams(text, n=3):
            words = re.findall(r'\b\w+\b', text.lower())
            return set(tuple(words[i:i+n]) for i in range(len(words) - n + 1))

        generated_ngrams = get_ngrams(generated_text)
        source_ngrams = get_ngrams(full_source_text)

        if not generated_ngrams: return 0.0
        
        common_ngrams = len(generated_ngrams.intersection(source_ngrams))
        uniqueness_score = 1.0 - (common_ngrams / len(generated_ngrams))
        return uniqueness_score

    def _evaluate_eeat(self, html_content, sources_metadata):
        prompt = f"""
        TASK: Evaluate the following HTML content for E-E-A-T (Experience, Expertise, Authoritativeness, Trustworthiness).
        Content: {html_content[:10000]}
        Sources: {json.dumps(sources_metadata)}

        Focus on:
        - Does the content show first-hand experience or practical knowledge?
        - Is the content written by or does it cite experts?
        - Is the source reputable and recognized as an authority?
        - Is the content accurate, verifiable, and free from misleading information?

        Output JSON with scores (0-100) for each E-E-A-T factor and an overall confidence score.
        {{
            "experience_score": 75,
            "expertise_score": 80,
            "authoritativeness_score": 90,
            "trustworthiness_score": 85,
            "overall_eeat_confidence": 82,
            "recommendations": "Add more direct quotes from experts."
        }}
        """
        try:
            resp = self._safe_generate(
                prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.2)
            )
            json_text = self._clean_json_text(resp.text)
            return json.loads(json_text)
        except Exception as e:
            logger.error(f"      ❌ E-E-A-T Evaluation Failed: {e}")
            return {"overall_eeat_confidence": 50, "recommendations": "Could not evaluate E-E-A-T."}

    def verify_quotes(self, html_content, source_text):
        soup = BeautifulSoup(html_content, 'html.parser')
        quotes = soup.find_all('blockquote')
        for bq in quotes:
            text = bq.get_text(strip=True)
            words = text.split()
            if len(words) > 3 and " ".join(words[:4]).lower() not in source_text.lower():
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
            resp = self._safe_generate(prompt)
            return resp.text.replace("```html", "").replace("```", "").strip()
        except: return None

    def run_professional_validation(self, html_content, full_source_text, sources_metadata):
        logger.info("🛡️ CORE SURGEON 3.0: COMMENCING FULL RESTORATION...")
        
        html = self.inject_ids_and_rebuild_toc(html_content)
        html = self.style_ai_generated_sources(html)
        html = self.perform_fact_surgery(html, full_source_text)
        html = self.rebuild_damaged_widgets(html, full_source_text)
        html = self.verify_quotes(html, full_source_text)
        html = self.restore_link_integrity(html, sources_metadata)

        uniqueness_score = self._check_uniqueness(html, full_source_text)
        readability_score = self._calculate_readability(BeautifulSoup(html, 'html.parser').get_text())
        ai_detection_score = self._check_ai_detection(BeautifulSoup(html, 'html.parser').get_text())
        eeat_evaluation = self._evaluate_eeat(html, sources_metadata)

        logger.info(f"📊 Quality Metrics: Uniqueness: {uniqueness_score:.2f}, Readability (FKGL): {readability_score}, AI Detection: {ai_detection_score:.2f}")
        logger.info(f"🌟 E-E-A-T Confidence: {eeat_evaluation['overall_eeat_confidence']} - Recommendations: {eeat_evaluation['recommendations']}")

        if uniqueness_score < MIN_UNIQUE_SCORE:
            logger.warning(f"      ⚠️ Content uniqueness ({uniqueness_score:.2f}) is below threshold ({MIN_UNIQUE_SCORE}). Consider re-writing.")
        if readability_score < MIN_READABILITY_SCORE:
            logger.warning(f"      ⚠️ Content readability ({readability_score}) is below threshold ({MIN_READABILITY_SCORE}). Consider simplifying.")
        if ai_detection_score > MAX_AI_DETECTION_SCORE:
            logger.warning(f"      ⚠️ AI detection score ({ai_detection_score:.2f}) is above threshold ({MAX_AI_DETECTION_SCORE}). Consider humanizing.")
        if eeat_evaluation['overall_eeat_confidence'] < 70:
            logger.warning(f"      ⚠️ Low E-E-A-T confidence ({eeat_evaluation['overall_eeat_confidence']}). Review recommendations: {eeat_evaluation['recommendations']}")
        
        html = re.sub(r'</?(html|body|head|meta|title)>', '', html, flags=re.IGNORECASE)
        html = re.sub(r'>\s+<', '><', html).strip()
        
        logger.info("✅ RESTORATION COMPLETE.")
        return html
