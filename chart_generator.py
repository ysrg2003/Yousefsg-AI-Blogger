# FILE: chart_generator.py
# ROLE: The Data Artist (Auto-Visualization)
# DESCRIPTION: Parses numerical data from the research, creates professional charts 
#              using Matplotlib/Seaborn, uploads them to GitHub, and returns the image URL.

import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import os
import time
from io import BytesIO
from config import log
from image_processor import upload_to_github_cdn 

# Ensure output directory exists for temporary file generation
os.makedirs("output", exist_ok=True)

def create_chart_from_data(data_points, title, filename_prefix="chart"):
    """
    Generates a bar chart from a dictionary of data points.
    
    Args:
        data_points (dict): e.g., {"Gemini 1.5": 90, "GPT-4": 85}
        title (str): Chart title.
        filename_prefix (str): Prefix for the saved file.
        
    Returns:
        str: Public URL of the uploaded image, or None if failed.
    """
    # 1. Validation: We need at least 2 points to make a comparison
    if not data_points or not isinstance(data_points, dict) or len(data_points) < 2:
        log("      ⚠️ Chart Generator: Insufficient data points for visualization.")
        return None
    
    log(f"   📊 [Chart Generator] Creating original visualization for: '{title}'...")
    
    try:
        # 2. Setup Style (Professional & Clean)
        sns.set_theme(style="whitegrid")
        plt.figure(figsize=(10, 6)) # Standard 16:9ish aspect ratio
        
        # 3. Convert Data to DataFrame for Seaborn
        # Sorting data ensures the chart looks organized (Highest to Lowest)
        df = pd.DataFrame(list(data_points.items()), columns=['Entity', 'Value'])
        df = df.sort_values('Value', ascending=False)
        
        # 4. Create the Bar Plot
        # Using 'viridis' palette for a tech-modern look
        ax = sns.barplot(x='Entity', y='Value', data=df, palette='viridis')
        
        # 5. Styling Details
        plt.title(title, fontsize=16, fontweight='bold', pad=20, color='#333333')
        plt.xlabel("", fontsize=12) # Hide X label as entity names are enough
        plt.ylabel("Score / Value", fontsize=12)
        plt.xticks(fontsize=11, fontweight='medium')
        plt.yticks(fontsize=10)
        
        # Remove top and right spines for a cleaner look
        sns.despine(left=True, bottom=True)
        
        # 6. Add Data Labels on top of bars
        for container in ax.containers:
            ax.bar_label(container, fmt='%.1f', padding=3, fontsize=11, fontweight='bold')

        # 7. Save to Buffer (In-Memory)
        # We save to a BytesIO object to upload directly without needing persistent local storage
        img_buffer = BytesIO()
        plt.savefig(img_buffer, format='png', bbox_inches='tight', dpi=150)
        plt.close() # Close plot to free memory
        img_buffer.seek(0) # Rewind buffer
        
        # 8. Upload to GitHub CDN
        # We reuse the logic from image_processor to keep things DRY
        # Generate a unique filename
        timestamp = int(time.time())
        safe_name = f"{filename_prefix}_{timestamp}.png"
        
        public_url = upload_to_github_cdn(img_buffer, safe_name)
        
        if public_url:
            log(f"      ✅ Chart Uploaded Successfully: {public_url}")
            return public_url
        else:
            log("      ❌ Chart Upload Failed (GitHub Error).")
            return None

    except Exception as e:
        log(f"      ⚠️ Chart generation crashed: {e}")
        # traceback.print_exc() # Uncomment for deep debugging
        return None
