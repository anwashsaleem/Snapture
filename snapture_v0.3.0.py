'''
Snapture 0.3.0 - First Album/Folder Creation with AI Captions.

How to use:
1. Place screenshots in the `Screenshots` folder.
2. Add your API key & endpoint in the script.
3. Define your album categories & keywords in `keyword_categories`.
4. Run the script — it will create `.txt` files and organize screenshots into folders.
'''

import os
import requests
import base64
import json
import shutil
import cv2
import numpy as np


# === Directories (input & output paths) ===
base_dir = os.path.dirname(os.path.abspath(__file__))
input_folder = os.path.join(base_dir, "Screenshots")
txt_folder = os.path.join(base_dir, "TXTs")
album_folder = os.path.join(base_dir, "Albums")
os.makedirs(txt_folder, exist_ok=True)
os.makedirs(album_folder, exist_ok=True)



# === Albums/Folder names & keywords. You can change or add your own ===
keyword_categories = {
    "chat": ["chat", "conversation", "whatsapp", "messenger"],
    "map": ["map", "location", "navigation", "gps"],
    "invoice": ["invoice", "bill", "receipt", "payment"],
    "social": ["instagram", "facebook", "post", "comment", "youtube", "tiktok", "twitter", "x", "snapchat","linkedin"],
    "Design": ["design", "ui", "ux", "mockup", "prototype"],   
}


# === AI Captioning Function ===
def get_ai_caption(image_path):
    API_KEY = "YOUR_API_KEY_HERE"   # <-- Replace with your actual API key
    API_URL = "YOUR_API_ENDPOINT_HERE"  # <-- Replace with your actual API endpoint

    with open(image_path, "rb") as f:
        image_data = f.read()
        encoded_image = base64.b64encode(image_data).decode("utf-8")

    headers = {
        "Content-Type": "application/json"
    }

    prompt = (
        "You're an AI content writer and image visualizer\n\n"
        "Task:\n"
        "1. Generate a short **title** for this image — max 8-10 words.\n"
        "2. Identify the application or context of the image (e.g., a chat screenshot, map screenshot, Instagram reel, etc.). "
        "Write a concise description (1–4 lines).\n\n"
        "Avoid:\n- Storytelling\n- Generic replies\n- Repetition\n\n"
        "3. Add some relevant tags related to the screenshot.\n"
        "4. Suggest the best matching category/album name."
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": encoded_image
                        }
                    }
                ]
            }
        ]
    }

    response = requests.post(API_URL, headers=headers, data=json.dumps(payload))

    if response.status_code == 200:
        try:
            content = response.json()["candidates"][0]["content"]["parts"][0]["text"]
            parts = content.split("\n", 1)
            title = parts[0].strip() if len(parts) > 0 else "No title"
            description = parts[1].strip() if len(parts) > 1 else "No description"
            return title, description
        except:
            return "Parse Error", "Parse Error"
    else:
        print("❌ API error:", response.text)
        return "API Failed", "API Failed"
    

# === Visual Hashing (for similarity detection) ===
def get_image_hash(image_path):
    image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    image = cv2.resize(image, (64, 64))
    avg = image.mean()
    hash_bits = (image > avg).astype(np.uint8)
    return hash_bits.flatten()

def is_similar(img_hash1, img_hash2, threshold=50):
    return np.sum(img_hash1 != img_hash2) < threshold

# === Main Logic ===
existing_hashes = {}

for file in os.listdir(input_folder):
    if file.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".webp")):
        image_path = os.path.join(input_folder, file)
        txt_file = os.path.splitext(file)[0] + ".txt"
        txt_path = os.path.join(txt_folder, txt_file)

        # Step 1: Get title & description
        title, desc = get_ai_caption(image_path)

        # Save TXT file
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(f"Title:\n{title}\n\n")
            f.write(f"Description:\n{desc}")

        print(f"✅ TXT saved: {txt_file}")

        # Step 2: Category detection
        keywords = (title + " " + desc).lower()
        assigned = False

        for category, terms in keyword_categories.items():
            if any(term in keywords for term in terms):
                category_path = os.path.join(album_folder, category)
                os.makedirs(category_path, exist_ok=True)
                shutil.copy2(image_path, os.path.join(category_path, file))
                shutil.copy2(txt_path, os.path.join(category_path, txt_file))
                print(f"📁 Added to album: {category}")
                assigned = True
                break

        # Step 3: Visual similarity check if not matched
        if not assigned:
            current_hash = get_image_hash(image_path)

            for category, hash_list in existing_hashes.items():
                for old_hash in hash_list:
                    if is_similar(current_hash, old_hash):
                        category_path = os.path.join(album_folder, category)
                        shutil.copy2(image_path, os.path.join(category_path, file))
                        shutil.copy2(txt_path, os.path.join(category_path, txt_file))
                        print(f"👀 Visually matched → Added to: {category}")
                        assigned = True
                        break
                if assigned:
                    break

            # Step 4: New folder if still unmatched
            if not assigned:
                unknown_path = os.path.join(album_folder, "Uncategorized")
                os.makedirs(unknown_path, exist_ok=True)
                shutil.copy2(image_path, os.path.join(unknown_path, file))
                shutil.copy2(txt_path, os.path.join(unknown_path, txt_file))
                print(f"🗂️ Moved to: Uncategorized")

            # Save hash for future similarity checks
            if assigned:
                category_name = category if 'category' in locals() else "Uncategorized"
                if category_name not in existing_hashes:
                    existing_hashes[category_name] = []
                existing_hashes[category_name].append(current_hash)
