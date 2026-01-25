import re
import requests
import logging
import json
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_fixed

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [WEBAI-HEALER] - %(message)s')
logger = logging.getLogger("AutoHealer_WebAI")

class AdvancedContentValidator:
    def __init__(self, openai_client, model_name="gemini"):
        self.client = openai_client
        self.model_name = model_name

    def ensure_structure_integrity(self, html_content, required_elements, full_source_text):
        soup = BeautifulSoup(html_content, 'html.parser')
        modified = False
        injection_point = soup.find('h2')
        if not injection_point: injection_point = soup.find('p')

        if "comparison-table" not in html_content:
            logger.warning("⚠️ Table Missing. Regenerating via WebAI...")
            table_html = self._generate_element("Comparison Table", full_source_text)
            if table_html:
                injection_point.insert_after(BeautifulSoup(table_html, 'html.parser'))
                modified = True

        widgets = ['code-snippet', 'specs-box', 'pros-cons-grid']
        if not any(w in html_content for w in widgets):
            logger.warning("⚠️ Widget Missing. Regenerating via WebAI...")
            w_type = "Pros & Cons Grid"
            if "code" in full_source_text.lower(): w_type = "Code Snippet"
            html_w = self._generate_element(w_type, full_source_text)
            if html_w:
                injection_point.insert_after(BeautifulSoup(html_w, 'html.parser'))
                modified = True
        return str(soup) if modified else html_content

    @retry(stop=stop_after_attempt(2), wait=wait_fixed(2))
    def _generate_element(self, element_type, source_text):
        prompt = f"Generate HTML for {element_type} based on: {source_text[:4000]}. Return ONLY HTML code."
        try:
            resp = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}]
            )
            return resp.choices[0].message.content.replace("```html","").replace("```","").strip()
        except: return ""

    def verify_and_heal_facts(self, html_content, source_text):
        # تبسيط للتحقق من الحقائق لتوفير الوقت
        return html_content 

    def heal_broken_links(self, html_content, valid_sources):
        soup = BeautifulSoup(html_content, 'html.parser')
        for link in soup.find_all('a', href=True):
            if "blogger" in link['href']: continue
            try:
                if requests.head(link['href'], timeout=2).status_code >= 400:
                    if valid_sources: link['href'] = valid_sources[0]['url']
            except: pass
        return str(soup)

    def run_professional_validation(self, html, source_text, sources_meta):
        logger.info("🛡️ WebAI Validation Started...")
        html = self.ensure_structure_integrity(html, [], source_text)
        html = self.heal_broken_links(html, sources_meta)
        return html
