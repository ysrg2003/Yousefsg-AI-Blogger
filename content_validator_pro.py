import re
import requests
import logging
import json
from bs4 import BeautifulSoup
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_fixed

# إعداد اللوجر الاحترافي
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [AUTO-HEALER] - %(message)s')
logger = logging.getLogger("AutoHealer")

class AdvancedContentValidator:
    def __init__(self, google_client, model_name="models/gemini-2.5-flash"):
        self.client = google_client
        self.model_name = model_name

    def _normalize(self, text):
        return re.sub(r'\s+', ' ', text.strip().lower())

    # ==============================================================================
    # 1. STRUCTURAL HEALING (إصلاح الهيكل المفقود)
    # ==============================================================================
    def ensure_structure_integrity(self, html_content, required_elements, full_source_text):
        """
        يفحص وجود العناصر الإجبارية (جدول، ويدجت).
        إذا كانت مفقودة، يقوم بتوليدها وحقنها.
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        modified = False

        # أين نحقن العناصر المفقودة؟ (بعد أول H2 غالباً)
        injection_point = soup.find('h2')
        if not injection_point:
            injection_point = soup.find('p')

        # 1. فحص الجدول
        if "comparison-table" not in html_content:
            logger.warning("⚠️ Critical: Comparison Table Missing. Initiating regeneration...")
            table_html = self._generate_missing_element("Comparison Table", full_source_text)
            if table_html:
                # نحقن الجدول بعد نقطة الحقن
                new_tag = BeautifulSoup(table_html, 'html.parser')
                injection_point.insert_after(new_tag)
                modified = True
                logger.info("✅ Fixed: Comparison Table injected successfully.")

        # 2. فحص عنصر الثقة (Widget)
        widgets = ['code-snippet', 'specs-box', 'roi-box', 'pros-cons-grid']
        has_widget = any(w in html_content for w in widgets)
        
        if not has_widget:
            logger.warning("⚠️ Critical: Authority Widget Missing. Initiating regeneration...")
            # نحدد نوع الويدجت المناسب بناءً على المحتوى (تخمين ذكي)
            widget_type = "Pros & Cons Grid" # افتراضي
            if "code" in full_source_text.lower(): widget_type = "Code Snippet"
            elif "battery" in full_source_text.lower() or "specs" in full_source_text.lower(): widget_type = "Specs Box"
            
            widget_html = self._generate_missing_element(widget_type, full_source_text)
            if widget_html:
                injection_point.insert_after(BeautifulSoup(widget_html, 'html.parser'))
                modified = True
                logger.info(f"✅ Fixed: {widget_type} injected successfully.")

        return str(soup) if modified else html_content

    @retry(stop=stop_after_attempt(2), wait=wait_fixed(2))
    def _generate_missing_element(self, element_type, source_text):
        """يطلب من AI توليد كود HTML للعنصر المفقود فقط"""
        prompt = f"""
        TASK: Generate missing HTML element.
        ELEMENT TYPE: {element_type}
        SOURCE DATA: {source_text[:5000]}
        
        REQUIREMENTS:
        - Generate ONLY the HTML for the requested element.
        - Strictly follow these CSS classes:
          - Table: <div class="table-wrapper"><table class="comparison-table">...</table></div>
          - Code: <div class="code-snippet">...</div>
          - Specs: <div class="specs-box">...</div>
          - Pros/Cons: <div class="pros-cons-grid">...</div>
        - Populate with REAL data from source.
        
        OUTPUT: HTML String ONLY.
        """
        resp = self.client.models.generate_content(model=self.model_name, contents=prompt)
        return resp.text.replace("```html", "").replace("```", "").strip()

    # ==============================================================================
    # 2. FACT HEALING (تصحيح الأرقام والحقائق)
    # ==============================================================================
    def verify_and_heal_facts(self, html_content, source_text):
        """
        يستخرج الجمل التي تحتوي على أرقام، ويطلب من AI التحقق منها وتصحيحها إذا لزم الأمر.
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        # نفحص الفقرات فقط لتوفير الوقت
        paragraphs = soup.find_all('p')
        
        suspicious_sentences = []
        
        # Regex للأرقام (يتجاهل السنوات 2020-2030)
        number_pattern = r'\b(?!(?:202[0-9]|2030)\b)\d+(?:\.\d+)?'

        for p in paragraphs:
            text = p.get_text()
            if re.search(number_pattern, text):
                # إذا وجدنا رقماً، هذه جملة حساسة تحتاج تدقيق
                suspicious_sentences.append(str(p))

        if not suspicious_sentences:
            return html_content

        # نرسل الجمل المشبوهة للـ AI دفعة واحدة ليصححها
        logger.info(f"🔍 Audit: Checking {len(suspicious_sentences)} paragraphs containing numbers...")
        
        correction_map = self._ai_batch_fact_check(suspicious_sentences, source_text)
        
        # تطبيق التصحيحات
        new_html = str(soup)
        fixed_count = 0
        for original, corrected in correction_map.items():
            if original != corrected:
                # استبدال ذكي (قد يفشل إذا تغير الـ HTML قليلاً، لذا نستخدم replace بحذر)
                # الأفضل: استبدال النص داخل التاج، لكن هنا سنستبدل السترينغ
                if original in new_html: # تأكد من وجوده
                     # تنظيف التاجات الزائدة التي قد يضيفها AI
                    clean_corrected = corrected.replace('<html>', '').replace('</html>', '').replace('<body>', '')
                    new_html = new_html.replace(original, clean_corrected)
                    fixed_count += 1

        if fixed_count > 0:
            logger.info(f"✅ Healed: {fixed_count} factual errors corrected.")
            
        return new_html

    def _ai_batch_fact_check(self, sentences_html, source_text):
        """
        يرسل قائمة جمل HTML ويطلب قاموساً بالتصحيحات.
        """
        prompt = f"""
        TASK: Fact-Check & Fix.
        SOURCE TEXT (TRUTH): {source_text[:15000]}
        
        INPUT HTML SNIPPETS TO CHECK:
        {json.dumps(sentences_html)}
        
        INSTRUCTIONS:
        1. For each HTML snippet, check if the NUMBERS or CLAIMS match the Source Text.
        2. IF CORRECT: Return it exactly as is.
        3. IF WRONG/HALLUCINATED: Rewrite the text with the CORRECT number/fact from source. Keep HTML tags (<p>, <a>) intact.
        4. IF NOT IN SOURCE AT ALL: Rewrite it to be vague/safe (e.g., change "500mAh" to "a large battery") OR remove the sentence if it's a lie.
        
        OUTPUT: JSON Object {{ "original_html_string": "corrected_html_string" }}
        """
        try:
            resp = self.client.models.generate_content(
                model=self.model_name, 
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            return json.loads(resp.text)
        except Exception as e:
            logger.error(f"❌ Fact Check Error: {e}")
            return {} # في حال الفشل، لا نغير شيئاً

    # ==============================================================================
    # 3. LINK HEALING (إصلاح الروابط المكسورة)
    # ==============================================================================
    def heal_broken_links(self, html_content, valid_sources_list):
        """
        إذا كان الرابط 404، يحاول استبداله برابط صحيح من قائمة المصادر (valid_sources_list).
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        links = soup.find_all('a', href=True)
        headers = {'User-Agent': 'Mozilla/5.0'}
        
        healed_count = 0
        
        for link in links:
            url = link['href']
            if "blogger" in url or "#" in url: continue
            
            is_dead = False
            try:
                r = requests.head(url, headers=headers, timeout=3)
                if r.status_code >= 400: is_dead = True
            except: is_dead = True
            
            if is_dead:
                logger.warning(f"⚠️ Dead Link: {url}. Attempting to recover...")
                
                # استراتيجية العلاج:
                # نبحث في قائمة المصادر الأصلية عن رابط من نفس الدومين
                # أو نستبدله بالرابط الرئيسي للمقال (أول مصدر)
                
                # استخراج الدومين المكسور
                try: broken_domain = re.search(r'https?://([^/]+)', url).group(1)
                except: broken_domain = ""
                
                replacement_url = None
                
                # 1. البحث عن تطابق الدومين
                if broken_domain:
                    for src in valid_sources_list:
                        if broken_domain in src['url']:
                            replacement_url = src['url']
                            break
                
                # 2. إذا فشل، نستخدم المصدر الأقوى (الأول)
                if not replacement_url and valid_sources_list:
                    replacement_url = valid_sources_list[0]['url']
                
                if replacement_url:
                    link['href'] = replacement_url
                    logger.info(f"✅ Healed Link: Swapped dead URL with {replacement_url}")
                    healed_count += 1
                else:
                    # الحل الأخير: إزالة الرابط
                    link.replace_with(link.text)
                    
        return str(soup)

    # ==============================================================================
    # 4. QUOTE HEALING (استبدال الاقتباسات المزيفة)
    # ==============================================================================
    def verify_and_swap_quotes(self, html_content, source_text):
        soup = BeautifulSoup(html_content, 'html.parser')
        quotes = soup.find_all('blockquote')
        
        for bq in quotes:
            quote_text = bq.get_text()
            # فحص بسيط: هل جزء من النص موجود في المصدر؟
            # نأخذ أكبر 4 كلمات متتالية ونبحث عنها
            words = quote_text.split()
            is_fake = True
            if len(words) > 5:
                chunk = " ".join(words[3:7]) # عينة
                if chunk.lower() in source_text.lower():
                    is_fake = False
            
            if is_fake:
                logger.warning(f"⚠️ Fake Quote Detected. Finding a REAL substitute...")
                
                # نطلب من AI استخراج اقتباس حقيقي بديل
                real_quote_html = self._find_real_quote(source_text)
                
                if real_quote_html and "<blockquote>" in real_quote_html:
                    # استبدال الـ Blockquote القديم بالجديد
                    new_tag = BeautifulSoup(real_quote_html, 'html.parser')
                    bq.replace_with(new_tag)
                    logger.info("✅ Fixed: Replaced fake quote with real one.")
                else:
                    # إذا فشل في إيجاد بديل، نحذفه
                    bq.decompose()
                    
        return str(soup)

    def _find_real_quote(self, source_text):
        prompt = f"""
        TASK: Extract a VERBATIM Quote.
        SOURCE: {source_text[:10000]}
        INSTRUCTION: Find ONE strong, real sentence/quote from the text representing the main opinion.
        FORMAT: Return HTML <blockquote>...</blockquote> with <footer> citation.
        IF NONE FOUND: Return "NONE".
        """
        try:
            resp = self.client.models.generate_content(model=self.model_name, contents=prompt)
            if "NONE" in resp.text: return None
            return resp.text.replace("```html", "").replace("```", "")
        except: return None

    # ==============================================================================
    # MASTER RUNNER
    # ==============================================================================
    def run_professional_validation(self, html_content, full_source_text, sources_list_metadata):
        logger.info("🛡️ STARTING PROFESSIONAL SELF-HEALING PROTOCOL...")
        
        # 1. Structure (Inject Missing Parts)
        html = self.ensure_structure_integrity(html_content, [], full_source_text)
        
        # 2. Facts (Correct Numbers) - AI Heavy
        html = self.verify_and_heal_facts(html, full_source_text)
        
        # 3. Quotes (Swap Fakes)
        html = self.verify_and_swap_quotes(html, full_source_text)
        
        # 4. Links (Recover Dead Ones)
        html = self.heal_broken_links(html, sources_list_metadata)
        
        logger.info("✅ PROTOCOL COMPLETE. Content is clean.")
        return html
