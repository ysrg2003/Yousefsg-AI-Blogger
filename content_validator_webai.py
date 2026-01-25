import re
import requests
import logging
import json
import time
from bs4 import BeautifulSoup
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, wait_fixed

# إعداد اللوجر الاحترافي لتتبع عمليات التصحيح التلقائي
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - [🛡️ WEBAI-AUTO-HEALER] - %(levelname)s - %(message)s'
)
logger = logging.getLogger("WebAI_Healer")

class AdvancedContentValidator:
    def __init__(self, openai_client, model_name="gemini"):
        """
        openai_client: العميل المتصل بسيرفر WebAI الخاص بك.
        model_name: اسم الموديل (افتراضياً gemini لأن السيرفر يحول الطلبات إليه).
        """
        self.client = openai_client
        self.model_name = model_name

    def _normalize(self, text):
        """تنظيف النص من المسافات الزائدة لسهولة المقارنة"""
        return re.sub(r'\s+', ' ', text.strip().lower())

    # ==============================================================================
    # 1. STRUCTURAL HEALING (إصلاح الهيكل البرمجي للمقال)
    # ==============================================================================
    def ensure_structure_integrity(self, html_content, full_source_text):
        """
        يفحص وجود العناصر الإجبارية (جدول المقارنة، وصندوق الأدوات).
        إذا كانت مفقودة، يطلب من الذكاء الاصطناعي إعادة بنائها من المصادر.
        """
        logger.info("🛠️ Checking structural integrity...")
        soup = BeautifulSoup(html_content, 'html.parser')
        modified = False

        # تحديد نقطة الحقن (بعد أول عنوان H2 أو أول فقرة)
        injection_point = soup.find('h2') or soup.find('p')

        # 1. فحص وجود جدول المقارنة
        if "comparison-table" not in html_content:
            logger.warning("⚠️ Comparison Table is missing! Generating now...")
            table_html = self._generate_element_via_ai("Comparison Table", full_source_text)
            if table_html and "<table" in table_html:
                new_tag = BeautifulSoup(table_html, 'html.parser')
                if injection_point:
                    injection_point.insert_after(new_tag)
                    modified = True
                    logger.info("✅ Fixed: Comparison Table injected.")

        # 2. فحص وجود صناديق الثقة (Authority Widgets)
        widgets = ['code-snippet', 'specs-box', 'roi-box', 'pros-cons-grid']
        if not any(w in html_content for w in widgets):
            logger.warning("⚠️ Authority Widget is missing! Generating now...")
            # اختيار نوع الصندوق بناءً على سياق النص
            widget_type = "Pros & Cons Grid"
            if "code" in full_source_text.lower() or "python" in full_source_text.lower():
                widget_type = "Code Snippet"
            elif "specs" in full_source_text.lower() or "battery" in full_source_text.lower():
                widget_type = "Specs Box"

            widget_html = self._generate_element_via_ai(widget_type, full_source_text)
            if widget_html:
                new_tag = BeautifulSoup(widget_html, 'html.parser')
                # نحقنه بعد الجدول أو بعد نقطة الحقن الأولى
                if injection_point:
                    injection_point.insert_after(new_tag)
                    modified = True
                    logger.info(f"✅ Fixed: {widget_type} injected.")

        return str(soup) if modified else html_content

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
    def _generate_element_via_ai(self, element_type, source_text):
        """طلب إعادة توليد عنصر محدد فقط من السيرفر"""
        prompt = f"""
        TASK: Generate a missing HTML element for a tech blog.
        ELEMENT TO GENERATE: {element_type}
        SOURCE DATA: {source_text[:6000]}
        
        STRICT HTML RULES:
        - Use ONLY these classes: 'table-wrapper', 'comparison-table', 'code-snippet', 'specs-box', 'pros-cons-grid'.
        - For tables, every <td> MUST have a 'data-label' attribute.
        - Return ONLY the HTML code. No talk.
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content.replace("```html", "").replace("```", "").strip()
        except Exception as e:
            logger.error(f"❌ Failed to generate {element_type}: {e}")
            return ""

    # ==============================================================================
    # 2. FACT HEALING (التدقيق الرقمي والحقائق)
    # ==============================================================================
    def verify_and_heal_facts(self, html_content, source_text):
        """
        يستخرج الفقرات التي تحتوي على أرقام (سعات بطارية، أسعار، نسب)
        ويقارنها بالمصادر الأصلية لتصحيح أي "هلوسة".
        """
        logger.info("🔍 Fact-checking numbers and claims...")
        soup = BeautifulSoup(html_content, 'html.parser')
        paragraphs = soup.find_all(['p', 'li'])
        
        suspicious_nodes = []
        # Regex للبحث عن الأرقام باستثناء السنوات الشائعة
        num_regex = r'\b(?!(?:202[0-9]|2030)\b)\d+(?:\.\d+)?'

        for node in paragraphs:
            if re.search(num_regex, node.get_text()):
                suspicious_nodes.append(str(node))

        if not suspicious_nodes:
            return html_content

        # إرسال الفقرات المشبوهة للتدقيق الجماعي (Batch Fact Check)
        correction_map = self._ai_batch_fact_check(suspicious_nodes, source_text)
        
        final_html = str(soup)
        fixed_count = 0
        for original, corrected in correction_map.items():
            if original != corrected and original in final_html:
                final_html = final_html.replace(original, corrected)
                fixed_count += 1
        
        if fixed_count > 0:
            logger.info(f"✅ Healed {fixed_count} factual errors.")
        return final_html

    def _ai_batch_fact_check(self, nodes_html, source_text):
        """طلب قاموس تصحيحات من السيرفر بصيغة JSON"""
        prompt = f"""
        TASK: Fact-Check HTML snippets against Source Truth.
        SOURCE TRUTH: {source_text[:12000]}
        INPUT SNIPPETS: {json.dumps(nodes_html)}
        
        INSTRUCTIONS:
        1. Compare numbers/claims in snippets with Source Truth.
        2. If a number is wrong, fix it. If a claim is hallucinated, rewrite it to be safe.
        3. Return a JSON object where KEY is the original snippet and VALUE is the corrected snippet.
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"❌ Fact Check AI error: {e}")
            return {}

    # ==============================================================================
    # 3. QUOTE HEALING (استبدال الاقتباسات المزيفة)
    # ==============================================================================
    def verify_and_swap_quotes(self, html_content, source_text):
        """
        يفحص الـ blockquotes. إذا كان الاقتباس غير موجود نصياً في المصدر،
        يتم استبداله باقتباس حقيقي (Verbatim) من المصادر.
        """
        logger.info("💬 Verifying quotes...")
        soup = BeautifulSoup(html_content, 'html.parser')
        quotes = soup.find_all('blockquote')
        
        for bq in quotes:
            text = bq.get_text().lower()
            # فحص: هل 4 كلمات متتالية على الأقل موجودة في المصدر؟
            words = text.split()
            found_real = False
            if len(words) > 5:
                for i in range(len(words)-4):
                    chunk = " ".join(words[i:i+4])
                    if chunk in source_text.lower():
                        found_real = True
                        break
            
            if not found_real:
                logger.warning("⚠️ Fake quote detected! Swapping with a real one...")
                real_quote_html = self._get_real_quote_from_ai(source_text)
                if real_quote_html:
                    bq.replace_with(BeautifulSoup(real_quote_html, 'html.parser'))
                    logger.info("✅ Fixed: Fake quote replaced.")
                else:
                    bq.decompose() # حذفه تماماً إذا لم نجد بديلاً حقيقياً

        return str(soup)

    def _get_real_quote_from_ai(self, source_text):
        prompt = f"Extract ONE exact verbatim quote from this text: {source_text[:8000]}. Format: <blockquote>Quote</blockquote><footer>Source</footer>. If no quote found, return 'NONE'."
        try:
            resp = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}]
            )
            content = resp.choices[0].message.content
            return None if "NONE" in content else content
        except: return None

    # ==============================================================================
    # 4. LINK HEALING (إصلاح الروابط المكسورة)
    # ==============================================================================
    def heal_broken_links(self, html_content, sources_list):
        """
        يتحقق من كل الروابط الخارجية. إذا كان الرابط معطلاً (404)،
        يستبدله برابط المصدر الرئيسي للمقال لضمان عدم وجود روابط ميتة.
        """
        logger.info("🔗 Checking for broken links...")
        soup = BeautifulSoup(html_content, 'html.parser')
        links = soup.find_all('a', href=True)
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

        fixed_links = 0
        for link in links:
            url = link['href']
            if "blogger.com" in url or "#" in url: continue
            
            try:
                # محاولة سريعة للتحقق من الرابط
                res = requests.head(url, headers=headers, timeout=5, allow_redirects=True)
                if res.status_code >= 400:
                    raise Exception("Broken")
            except:
                logger.warning(f"⚠️ Broken link found: {url}. Healing...")
                # استبداله بأول رابط مصدر متاح
                if sources_list:
                    link['href'] = sources_list[0]['url']
                    fixed_links += 1
        
        if fixed_links > 0:
            logger.info(f"✅ Healed {fixed_links} broken links.")
        return str(soup)

    # ==============================================================================
    # MASTER RUNNER (المشغل الرئيسي للمدقق)
    # ==============================================================================
    def run_professional_validation(self, html_content, full_source_text, sources_list_metadata):
        """
        هذا هو المحرك الذي يتم استدعاؤه من الملف الرئيسي.
        """
        logger.info("🛡️ STARTING WEBAI PROFESSIONAL SELF-HEALING PROTOCOL...")
        
        # المرحلة 1: إصلاح الهيكل (جداول، صناديق)
        html = self.ensure_structure_integrity(html_content, full_source_text)
        
        # المرحلة 2: تصحيح الحقائق والأرقام
        html = self.verify_and_heal_facts(html, full_source_text)
        
        # المرحلة 3: التحقق من الاقتباسات
        html = self.verify_and_swap_quotes(html, full_source_text)
        
        # المرحلة 4: إصلاح الروابط
        html = self.heal_broken_links(html, sources_list_metadata)
        
        logger.info("✅ SELF-HEALING PROTOCOL COMPLETE.")
        return html
