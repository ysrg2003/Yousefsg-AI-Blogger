# FILE: content_validator_pro.py
# DESCRIPTION: Advanced content validation and healing using Gemini & BeautifulSoup.

import re
import requests
import logging
import json
from bs4 import BeautifulSoup
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_fixed
from urllib.parse import urlparse

# إعداد اللوجر
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [CORE-SURGEON-3.0] - %(message)s')
logger = logging.getLogger("CoreSurgeon")

class AdvancedContentValidator:
    def __init__(self, google_client, model_name="gemini-2.5-flash"):
        self.client = google_client
        self.model_name = model_name
        self.session = requests.Session()
        # هوية مخصصة لتجنب الحظر
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 ProValidator/3.0'
        })

    def _clean_json_text(self, text):
        """تنظيف النص من علامات المارك داون لضمان تحويله لـ JSON بنجاح"""
        if not text: return "{}"
        clean = text.replace("```json", "").replace("```", "").strip()
        return clean

    # ==============================================================================
    # 1. PROACTIVE FACT SURGERY (الجراحة الوقائية للحقائق)
    # ==============================================================================
    def perform_fact_surgery(self, html_content, full_source_text):
        """
        يفحص الأرقام والحقائق التقنية ويصححها بناءً على المصادر.
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        elements = soup.find_all(['p', 'td', 'li', 'span', 'h3'])
        
        chunks_to_verify = []
        # Regex للبحث عن الأرقام والبيانات الحساسة
        pattern = r'(\d+%?|\$\d+|\bv\d+\.\d+|\d+\s(hours|GB|TB)|\b(vs|better than|faster than|release date)\b)'
        
        for el in elements:
            text = el.get_text()
            if len(text) < 300 and re.search(pattern, text, re.IGNORECASE): # تجاهل الفقرات الطويلة جداً لتوفير التوكنز
                chunks_to_verify.append(str(el))

        if not chunks_to_verify:
            return html_content

        # نرسل دفعات صغيرة (50 عنصر كحد أقصى) لتجنب تجاوز حدود التوكنز
        chunks_to_verify = chunks_to_verify[:50]

        logger.info(f"💉 Starting Fact Surgery on {len(chunks_to_verify)} sensitive elements...")
        
        prompt = f"""
        TASK: Technical Content Surgery.
        TRUTH DATA (Raw Sources): {full_source_text[:20000]}
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
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1 # حرارة منخفضة للدقة
                )
            )
            
            # حماية ضد أخطاء JSON
            json_text = self._clean_json_text(resp.text)
            corrections = json.loads(json_text)
            
            final_html = str(soup)
            for original, corrected in corrections.items():
                if original in final_html and corrected and corrected != original:
                    # تنظيف التصحيح من أي تاجات هيكلية زائدة
                    clean_fix = re.sub(r'</?(html|body|head)>', '', corrected, flags=re.IGNORECASE)
                    final_html = final_html.replace(original, clean_fix)
            
            return final_html
        except Exception as e:
            logger.error(f"❌ Fact Surgery Failed: {e}")
            return html_content

    # ==============================================================================
    # 2. WIDGET RECONSTRUCTION (إعادة بناء العناصر التالفة)
    # ==============================================================================
    def rebuild_damaged_widgets(self, html_content, full_source_text):
        if "comparison-table" not in html_content:
            return html_content

        soup = BeautifulSoup(html_content, 'html.parser')
        modified = False
        
        table = soup.find('table', class_='comparison-table')
        if table:
            cells = table.find_all('td')
            if cells:
                # إذا كان الجدول فارغاً أو سيئاً
                empty_cells = [c for c in cells if len(c.get_text(strip=True)) < 2 or "n/a" in c.get_text(strip=True).lower()]
                if len(empty_cells) > (len(cells) / 2):
                    logger.warning("🔨 Comparison table is low quality. Rebuilding...")
                    new_table_html = self._generate_element_from_ai("Comparison Table", full_source_text)
                    if new_table_html:
                        # استبدال آمن باستخدام BeautifulSoup
                        new_soup = BeautifulSoup(new_table_html, 'html.parser')
                        if new_soup.find('table'):
                            table.replace_with(new_soup.find('table'))
                        else:
                            table.replace_with(new_soup)
                        modified = True

        return str(soup) if modified else html_content

    @retry(stop=stop_after_attempt(2), wait=wait_fixed(2))
    def _generate_element_from_ai(self, element_type, source_text):
        prompt = f"REBUILD TASK: Create a high-quality HTML {element_type} using ONLY facts from: {source_text[:8000]}. Use clean CSS classes like 'comparison-table'. Output ONLY HTML."
        try:
            resp = self.client.models.generate_content(model=self.model_name, contents=prompt)
            return resp.text.replace("```html", "").replace("```", "").strip()
        except: return None

    # ==============================================================================
    # 3. INTELLIGENT LINK RESTORATION (ترميم الروابط المكسورة)
    # ==============================================================================
    def restore_link_integrity(self, html_content, sources_metadata):
        soup = BeautifulSoup(html_content, 'html.parser')
        links = soup.find_all('a', href=True)
        
        for link in links:
            url = link['href']
            # تخطي الروابط الداخلية وروابط السوشيال ميديا
            if any(x in url for x in ["latestai.me", "facebook.com", "instagram.com", "x.com", "youtube.com", "reddit.com"]) or url.startswith('#'):
                continue

            try:
                # التحقق من الرابط (Head Request)
                r = self.session.head(url, timeout=3, allow_redirects=True)
                if r.status_code >= 400: raise Exception("Dead Link")
            except:
                logger.warning(f"🩹 Healing broken link: {url}")
                parsed_url = urlparse(url)
                target_domain = parsed_url.netloc.replace('www.', '')
                
                # البحث عن بديل في المصادر
                replacement_url = None
                for src in sources_metadata:
                    if target_domain in src['url']:
                        replacement_url = src['url']
                        break
                
                if replacement_url:
                    link['href'] = replacement_url
                    logger.info(f"✅ Link restored to source: {replacement_url}")
                else:
                    # الربط بالمصدر الرئيسي كحل أخير
                    if sources_metadata:
                        link['href'] = sources_metadata[0]['url']
                        logger.info(f"✅ Link pivoted to main source: {sources_metadata[0]['url']}")
        
        return str(soup)

    # ==============================================================================
    # 4. QUOTE VERIFIER (التحقق من الاقتباسات)
    # ==============================================================================
    def verify_quotes(self, html_content, source_text):
        soup = BeautifulSoup(html_content, 'html.parser')
        quotes = soup.find_all('blockquote')
        
        for bq in quotes:
            quote_text = bq.get_text(strip=True)
            words = quote_text.split()
            # إذا لم نجد كلمات الاقتباس في المصدر
            if len(words) > 3 and " ".join(words[:4]).lower() not in source_text.lower():
                logger.warning("⚠️ Replacing hallucinated quote...")
                real_quote_html = self._find_real_quote_from_ai(source_text)
                if real_quote_html:
                    new_soup = BeautifulSoup(real_quote_html, 'html.parser')
                    # نحاول استخراج blockquote فقط لتجنب التاجات الزائدة
                    if new_soup.find('blockquote'):
                        bq.replace_with(new_soup.find('blockquote'))
                    else:
                        bq.replace_with(new_soup)
                else:
                    bq.decompose() # حذف الاقتباس إذا لم يوجد بديل
        
        return str(soup)

    def _find_real_quote_from_ai(self, source_text):
        prompt = f"EXTRACT VERBATIM QUOTE: Find one powerful, real sentence from this text: {source_text[:5000]}. Return it as a single HTML <blockquote> with a <footer> if possible. Output ONLY HTML."
        try:
            resp = self.client.models.generate_content(model=self.model_name, contents=prompt)
            return resp.text.replace("```html", "").replace("```", "").strip()
        except: return None

    # ==============================================================================
    # MASTER RUNNER
    # ==============================================================================
    def run_professional_validation(self, html_content, full_source_text, sources_metadata):
        logger.info("🛡️ CORE SURGEON 3.0: COMMENCING FULL RESTORATION...")
        
        # 1. Facts
        html = self.perform_fact_surgery(html_content, full_source_text)
        
        # 2. Widgets
        html = self.rebuild_damaged_widgets(html, full_source_text)
        
        # 3. Quotes
        html = self.verify_quotes(html, full_source_text)
        
        # 4. Links
        html = self.restore_link_integrity(html, sources_metadata)
        
        # Final Cleanup
        html = re.sub(r'</?(html|body|head|meta|title)>', '', html, flags=re.IGNORECASE)
        html = re.sub(r'>\s+<', '><', html).strip()
        
        logger.info("✅ RESTORATION COMPLETE.")
        return html
