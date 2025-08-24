"""
Snapture v0.3.1 – Clustering-based Screenshot Organization

How to use:
1. Place screenshots in the `Screenshots` folder.
2. Add your API key & endpoint in the script.
3. Run the script — it will create `.txt` files and organize screenshots into folders.

Working:
- Uses AI to generate titles, descriptions & tags.
- Clusters screenshots based on similarity (threshold = 0.2).
- Automatically creates albums (folders) and names them with AI.
"""


import os
import json
import base64
import shutil
import time
import requests
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# Set your AI API key
AI_API_KEY = "***"
AI_URL = f"*******key={AI_API_KEY}"


# Set up directories
base_directory = os.path.dirname(os.path.abspath(__file__))
screenshots_directory = os.path.join(base_directory, "Screenshots")
text_files_directory = os.path.join(base_directory, "TXTs")
albums_directory = os.path.join(base_directory, "Albums")

for folder in (text_files_directory, albums_directory):
    os.makedirs(folder, exist_ok=True)


# Clean folder/file names by removing invalid characters
def sanitize(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', '', name).strip() or "Uncategorized"


# Send image and prompt to AI API, return text response
def call_ai(prompt: str, image_path: str) -> str | None:
    with open(image_path, "rb") as image_file:
        image_encoded = base64.b64encode(image_file.read()).decode()

    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": "image/jpeg", "data": image_encoded}}
            ]
        }]
    }

    for attempt in range(3):
        try:
            response = requests.post(
                AI_URL,
                headers={"Content-Type": "application/json"},
                data=json.dumps(payload)
            )
            response.raise_for_status()
            if response.status_code == 200:
                return response.json()["candidates"][0]["content"]["parts"][0]["text"]
            elif response.status_code == 429:
                print("❌ API rate limit. Try again later.")
                return None
            else:
                print("❌ API error:", response.text)
                return None
        except requests.exceptions.RequestException as e:
            print(f"[Attempt {attempt + 1}] API call failed: {e}")
            if attempt < 2:
                print("Retrying in 3 seconds...")
                time.sleep(3)
    print("❌ API failed after 3 attempts.")
    return None


print("\n💫 Snapture 0.3.1 Starting…\n")


# Caption screenshots and generate TXT files
screenshot_items = []
for file_name in sorted(os.listdir(screenshots_directory)):
    if not file_name.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".webp")):
        continue

    image_path = os.path.join(screenshots_directory, file_name)
    print(f"🟡 Captioning {file_name}…", end=" ")

    caption_prompt = (
        "You are an AI that captions screenshots.\n"
        "Respond EXACTLY as:\n"
        "Title: <up to 10 words>\n"
        "Description: <1–3 lines>\n"
        "Tags: <3–5 comma-separated keywords>\n"
    )

    caption_response = call_ai(caption_prompt, image_path)
    if not caption_response or "Title:" not in caption_response or "Tags:" not in caption_response:
        print("⛔ skip")
        continue

    lines = caption_response.splitlines()

    title = ""
    description = ""
    tags = []

    for line in lines:
        if line.startswith("Title:"):
            title = line.split(":", 1)[1].strip()
        elif line.startswith("Description:"):
            description = line.split(":", 1)[1].strip()
        elif line.startswith("Tags:"):
            tags = [tag.strip() for tag in line.split(":", 1)[1].split(",") if tag.strip()]

    
    # Save TXT file
    txt_file_name = os.path.splitext(file_name)[0] + ".txt"
    txt_file_path = os.path.join(text_files_directory, txt_file_name)

    with open(txt_file_path, "w", encoding="utf-8") as txt_file:
        txt_file.write(f"Title:\n{title}\n\n")
        txt_file.write(f"Description:\n{description}\n\n")
        txt_file.write(f"Tags:\n{', '.join(tags)}")

    print("✅ TXT")

    screenshot_items.append({
        "file_name": file_name,
        "image_path": image_path,
        "title": title,
        "description": description,
        "tags": tags,
        "txt_path": txt_file_path
    })

if not screenshot_items:
    print("❌ No captions produced. Exiting.")
    exit()


# Cluster similar captions using TF-IDF + cosine similarity
corpus = [item["title"] + " " + item["description"] for item in screenshot_items]
tfidf_matrix = TfidfVectorizer().fit_transform(corpus)
similarity_matrix = cosine_similarity(tfidf_matrix)



#Create clusters if similarity > threshold
""" 
The threshold value controls how similar two captions must be to be grouped into the same folder.

Lower threshold (e.g., 0.1–0.2):
More relaxed similarity & Larger clusters
Screenshots with only slight overlap in meaning may get grouped together

Higher threshold (e.g., 0.5–0.7):
Stricter similarity, Smaller & more precise clusters
Screenshots must be very closely related to be grouped
"""

threshold = 0.2 
clusters = []
for index, item in enumerate(screenshot_items):
    added = False
    for cluster in clusters:
        existing_index = cluster[0]
        if similarity_matrix[index][existing_index] >= threshold:
            cluster.append(index)
            added = True
            break
    if not added:
        clusters.append([index])


# Suggest folder name for each cluster
cluster_names = []
for cluster_indices in clusters:
    filenames = [screenshot_items[i]["file_name"] for i in cluster_indices]
    all_tags = sum((screenshot_items[i]["tags"] for i in cluster_indices), [])

    folder_prompt = (
        "You are a folder-organization expert.\n"
        "Given these filenames and tags, suggest ONE concise (1–2 word) folder name.\n"
        f"Files: {filenames}\nTags: {all_tags}\n"
        "Return just the name."
    )

    sample_image_path = screenshot_items[cluster_indices[0]]["image_path"]
    print(f"\n🟢 Naming cluster ({filenames})…", end=" ")
    folder_name_response = call_ai(folder_prompt, sample_image_path)

    if folder_name_response:
        folder_name = sanitize(folder_name_response.splitlines()[0].split(":", 1)[-1].strip())
    else:
        folder_name = "Uncategorized"

    print(folder_name)
    cluster_names.append(folder_name)


# Save clustered files into folders
print()
for cluster, folder_name in zip(clusters, cluster_names):
    destination_path = os.path.join(albums_directory, folder_name)
    os.makedirs(destination_path, exist_ok=True)

    for item_index in cluster:
        item = screenshot_items[item_index]
        shutil.copy2(item["image_path"], os.path.join(destination_path, item["file_name"]))
        shutil.copy2(item["txt_path"], os.path.join(destination_path, os.path.basename(item["txt_path"])))
        print(f"📁 {item['file_name']} → {folder_name}")

print("\n🚀 Done — check ‘Albums’!")
