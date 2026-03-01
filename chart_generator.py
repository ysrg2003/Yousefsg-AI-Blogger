# FILE: chart_generator.py (fixed numeric coercion + robust checks)
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import os
import time
import re
from io import BytesIO
from config import log
from image_processor import upload_to_github_cdn

os.makedirs("output", exist_ok=True)

def _coerce_to_number(v):
    """Try converting common numeric string formats to float. Return None if impossible."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if s == "":
        return None
    # Remove percent sign, commas, and surrounding whitespace
    s = s.replace("%", "")
    s = s.replace(",", "")
    # Remove any non-numeric trailing/leading characters (keep dot and minus)
    s = re.sub(r'^[^\d\.-]+|[^\d\.-]+$', '', s)
    try:
        return float(s)
    except Exception:
        return None

def create_chart_from_data(data_points, title, filename_prefix="chart"):
    """
    Generates a bar chart from a dictionary of data points.
    data_points: dict e.g., {"Gemini 1.5": 90, "GPT-4": "85"}
    Returns: public URL or None.
    """
    if not data_points or not isinstance(data_points, dict) or len(data_points) < 2:
        log(" ⚠️ Chart Generator: Insufficient or invalid data_points.")
        return None

    # Coerce values to numeric, drop non-numeric
    items = []
    for k, v in data_points.items():
        num = _coerce_to_number(v)
        if num is None:
            log(f" ℹ️ Skipping non-numeric chart value for '{k}': {v}")
            continue
        items.append((k, num))

    if len(items) < 2:
        log(" ⚠️ Chart Generator: Not enough numeric data points after coercion.")
        return None

    try:
        sns.set_theme(style="whitegrid")
        plt.figure(figsize=(10, 6))

        df = pd.DataFrame(items, columns=['Entity', 'Value'])
        df = df.sort_values('Value', ascending=False)

        ax = sns.barplot(x='Entity', y='Value', data=df)
        plt.title(title if title else "Comparison", fontsize=16, fontweight='bold', pad=12)
        plt.xlabel("", fontsize=12)
        plt.ylabel("Value", fontsize=12)
        plt.xticks(rotation=25, fontsize=10)
        plt.yticks(fontsize=10)
        sns.despine(left=True, bottom=True)

        for container in ax.containers:
            ax.bar_label(container, fmt='%.1f', padding=3, fontsize=10)

        img_buffer = BytesIO()
        plt.savefig(img_buffer, format='png', bbox_inches='tight', dpi=150)
        plt.close()
        img_buffer.seek(0)

        timestamp = int(time.time())
        safe_name = f"{filename_prefix}_{timestamp}.png"
        public_url = upload_to_github_cdn(img_buffer, safe_name)
        if public_url:
            log(f" ✅ Chart Uploaded Successfully: {public_url}")
            return public_url
        else:
            log(" ❌ Chart Upload Failed (GitHub Error).")
            return None
    except Exception as e:
        log(f" ⚠️ Chart generation crashed: {e}")
        return None
