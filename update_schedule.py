import random
import os
import re

def update_workflow_schedule():
    workflow_file = '.github/workflows/daily-publish.yml'
    
    # 1. توليد وقت عشوائي جديد للغد
    # الساعات: نختار عشوائياً بين 1 مساء و 12 مساءً (توقيت عالمي UTC)
    random_hour = random.randint(11, 23)
    # الدقائق: أي دقيقة عشوائية
    random_minute = random.randint(0, 59)
    
    new_cron = f"{random_minute} {random_hour} * * *"
    
    print(f"🎲 Next run scheduled for (UTC): {random_hour}:{random_minute:02d}")

    # 2. قراءة الملف وتحديثه
    if not os.path.exists(workflow_file):
        print(f"❌ Error: {workflow_file} not found!")
        return

    with open(workflow_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # استخدام Regex للبحث عن سطر الـ cron واستبداله بدقة
    # يبحث عن نمط: - cron: '...' ويستبدله بالجديد
    new_content = re.sub(
        r"(- cron:)\s*['\"].*?['\"]", 
        f"\\1 '{new_cron}'", 
        content
    )

    # 3. حفظ التغييرات
    with open(workflow_file, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print("✅ Schedule updated successfully in YAML.")

if __name__ == "__main__":
    update_workflow_schedule()
