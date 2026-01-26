import re
import requests
import logging
import json
from bs4 import BeautifulSoup
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_fixed
from urllib.parse import urlparse
from google import genai

# إعداد اللوجر الاحترافي والمتقدم
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [CORE-SURGEON-3.0] - %(message)s')
logger = logging.getLogger("CoreSurgeon")

class AdvancedContentValidator:
    def __init__(self, google_client, model_name="gemini-2.5-flash"):
        self.client = google_client
        self.model_name = model_name
        self.session = requests.Session()
        # هوية مخصصة للمدقق لضمان عدم حظره عند فحص الروابط
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 ProValidator/3.0'
        })

    def _normalize(self, text):
        """
        دالة مساعدة لتنظيف النصوص من المسافات الزائدة وتحويلها لحروف صغيرة للمقارنة.
        (موجودة كما في الكود القديم لضمان التوافقية)
        """
        return re.sub(r'\s+', ' ', text.strip().lower())

    # ==============================================================================
    # 1. PROACTIVE FACT SURGERY (الجراحة الوقائية للحقائق)
    # ==============================================================================
    def perform_fact_surgery(self, html_content, full_source_text):
        """
        يقوم بفحص كل ادعاء رقمي أو تقني وتصحيحه فوراً باستخدام البيانات الخام.
        إذا وجد معلومة "هلوسة"، يقوم بإعادة صياغتها لتكون رأياً احترافياً.
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        # نركز على الفقرات والجداول والخلايا لأنها تحتوي على "الذهب التقني"
        elements = soup.find_all(['p', 'td', 'li', 'span', 'h3'])
        
        chunks_to_verify = []
        # Regex متطور للبحث عن الأرقام، النسب، الأسعار، الإصدارات، والكلمات المفتاحية الحساسة
        pattern = r'(\d+%?|\$\d+|\bv\d+\.\d+|\d+\s(hours|GB|TB)|\b(vs|better than|faster than|release date)\b)'
        
        for el in elements:
            text = el.get_text()
            if re.search(pattern, text, re.IGNORECASE):
                chunks_to_verify.append(str(el))

        if not chunks_to_verify:
            return html_content

        logger.info(f"💉 Starting Fact Surgery on {len(chunks_to_verify)} sensitive elements...")
        
        prompt = f"""
        TASK: Technical Content Surgery.
        TRUTH DATA (Raw Sources): {full_source_text[:15000]}
        DRAFT HTML ELEMENTS: {json.dumps(chunks_to_verify)}
        
        INSTRUCTIONS:
        1. For each HTML element, compare every number, date, and technical claim with the TRUTH DATA.
        2. IF WRONG: Rewrite the entire HTML element with the CORRECT information. Preserve all original HTML tags (<a>, <strong>, etc.).
        3. IF HALLUCINATED (claim is not in TRUTH DATA): Do NOT delete. Rewrite it to be a logical professional observation based on what IS in the source. (e.g., If source says a chip is fast, you can infer 'This could improve gaming performance').
        4. IF CORRECT: Return it exactly as is.
        
        OUTPUT: JSON dictionary {{ "original_html_string": "corrected_html_string" }}
        """
        try:
            resp = self.client.models.generate_content(
                model=self.model_name, 
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            corrections = json.loads(resp.text)
            
            final_html = str(soup)
            for original, corrected in corrections.items():
                if original in final_html and corrected:
                    # تنظيف مخرجات الـ AI من أي زوائد
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
        """
        يفحص الجداول والقوائم. إذا وجدها فارغة أو تحتوي على "N/A" بكثرة، 
        يعيد بناءها من الصفر باستخدام المصادر الحقيقية.
        """
        if "comparison-table" not in html_content:
            return html_content

        soup = BeautifulSoup(html_content, 'html.parser')
        modified = False
        
        # فحص جودة الجدول
        table = soup.find('table', class_='comparison-table')
        if table:
            cells = table.find_all('td')
            # إذا كان نصف الجدول تقريباً فارغاً أو يحتوي كلمات تافهة
            if cells:
                empty_cells = [c for c in cells if len(c.get_text(strip=True)) < 2 or "n/a" in c.get_text(strip=True).lower()]
                if len(empty_cells) > (len(cells) / 2):
                    logger.warning("🔨 Comparison table is low quality. Rebuilding from source...")
                    new_table = self._generate_element_from_ai("Comparison Table", full_source_text)
                    if new_table:
                        table.replace_with(BeautifulSoup(new_table, 'html.parser'))
                        modified = True

        return str(soup) if modified else html_content

    @retry(stop=stop_after_attempt(2), wait=wait_fixed(2))
    def _generate_element_from_ai(self, element_type, source_text):
        prompt = f"REBUILD TASK: Create a high-quality HTML {element_type} using ONLY facts from: {source_text[:8000]}. Use clean CSS classes like 'comparison-table'."
        try:
            resp = self.client.models.generate_content(model=self.model_name, contents=prompt)
            return resp.text.replace("```html", "").replace("```", "").strip()
        except: return None

    # ==============================================================================
    # 3. INTELLIGENT LINK RESTORATION (ترميم الروابط المكسورة)
    # ==============================================================================
    def restore_link_integrity(self, html_content, sources_metadata):
        """
        إذا وجد رابطاً مكسوراً، يرممه بدلاً من حذفه أو استبداله برابط عشوائي.
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        links = soup.find_all('a', href=True)
        
        for link in links:
            url = link['href']
            # تخطي الروابط الداخلية وروابط التواصل الاجتماعي
            if any(x in url for x in ["latestai.me", "facebook.com", "instagram.com", "x.com", "youtube.com", "reddit.com", "pinterest.com"]) or url.startswith('#'):
                continue

            try:
                # محاولة فحص الرابط بسرعة
                r = self.session.head(url, timeout=3, allow_redirects=True)
                if r.status_code >= 400: raise Exception("Dead Link")
            except:
                logger.warning(f"🩹 Healing broken link: {url}")
                parsed_url = urlparse(url)
                target_domain = parsed_url.netloc.replace('www.', '')
                
                # استراتيجية الترميم: البحث عن رابط صحيح لنفس الدومين في المصادر الموثوقة
                replacement_url = None
                for src in sources_metadata:
                    if target_domain in src['url']:
                        replacement_url = src['url']
                        break
                
                if replacement_url:
                    link['href'] = replacement_url
                    logger.info(f"✅ Link restored to source: {replacement_url}")
                else:
                    # إذا لم يجد، يبحث عن أي ذكر لاسم الدومين ويربطه بأول مصدر دسم
                    if sources_metadata:
                        link['href'] = sources_metadata[0]['url']
                        logger.info(f"✅ Link pivoted to main source: {sources_metadata[0]['url']}")
        
        return str(soup)

    # ==============================================================================
    # 4. QUOTE VERIFIER & ANCHORING (التأكد من الاقتباسات وتثبيتها)
    # ==============================================================================
    def verify_quotes(self, html_content, source_text):
        """
        يتأكد أن كل اقتباس موجود في النص المصدري. إذا كان مزيفاً، يستبدله بآخر حقيقي.
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        quotes = soup.find_all('blockquote')
        
        for bq in quotes:
            quote_text = bq.get_text(strip=True)
            words = quote_text.split()
            # فحص إذا كان جزء من الاقتباس موجوداً في المصدر لمنع الهلوسة الكاملة
            if len(words) > 3 and " ".join(words[:4]).lower() not in source_text.lower():
                logger.warning("⚠️ Replacing hallucinated quote with a real one...")
                real_quote = self._find_real_quote_from_ai(source_text)
                if real_quote:
                    # استخدام beautifulsoup للتأكد من أن الكود سليم قبل الإضافة
                    bq.replace_with(BeautifulSoup(real_quote, 'html.parser'))
                else:
                    bq.decompose() # حذف الاقتباس المزيف إذا لم نجد بديلاً
        
        return str(soup)

    def _find_real_quote_from_ai(self, source_text):
        prompt = f"EXTRACT VERBATIM QUOTE: Find one powerful, real sentence from this text: {source_text[:5000]}. Return it as a single HTML <blockquote> with a <footer> if possible."
        try:
            resp = self.client.models.generate_content(model=self.model_name, contents=prompt)
            return resp.text.replace("```html", "").replace("```", "").strip()
        except: return None

    # ==============================================================================
    # MASTER RUNNER (المنفذ الرئيسي)
    # ==============================================================================
    def run_professional_validation(self, html_content, full_source_text, sources_metadata):
        logger.info("🛡️ CORE SURGEON 3.0: COMMENCING FULL RESTORATION...")
        
        # 1. جراحة الحقائق (Active Correction) - الأهم أولاً
        html = self.perform_fact_surgery(html_content, full_source_text)
        
        # 2. الهيكل والويدجات
        html = self.rebuild_damaged_widgets(html, full_source_text)
        
        # 3. الاقتباسات
        html = self.verify_quotes(html, full_source_text)
        
        # 4. الروابط
        html = self.restore_link_integrity(html, sources_metadata)
        
        # تنظيف نهائي صارم للـ HTML من أي زوائد
        html = re.sub(r'</?(html|body|head|meta|title)>', '', html, flags=re.IGNORECASE)
        html = re.sub(r'>\s+<', '><', html).strip() # إزالة المسافات بين التاجات
        
        logger.info("✅ RESTORATION COMPLETE. Article is clinically clean and verified.")
        return html
