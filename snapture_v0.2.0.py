'''
Snapture 0.2.0 - AI-powered text extraction using the OpenRouter API.

Improvements:
- Improvement on handling blurry or blank screenshots.
- Generates concise titles and descriptions automatically.
- Requires an OpenRouter API key (sign up at https://openrouter.ai).

Limitations:
- API limits may affect usage due to limitation on OpenRouter.
- No categorization of screenshots.
- No UI or tags yet.

How to use:
1. Place your screenshots in the `Screenshots` folder.
2. Add your OpenRouter API key in the code.
3. Run the script to generate text files with captions.
'''



import os
import requests
import base64
import json

# === OpenRouter API Config ===
OPENROUTER_API_KEY = "YOUR API KEY"  # Replace this with your OpenRouter API key
MODEL_ID = "YOUR MODEL ID"  # Replace with your model ID e.g., "meta-llama, gemini-1.5 or similar
API_URL = "YOUR API URL"  # Replace with the OpenRouter API URL

# === Folders ===
base_dir = os.path.dirname(os.path.abspath(__file__))
input_folder = os.path.join(base_dir, "Screenshots")
output_folder = os.path.join(base_dir, "TXTs")

# Create output folder if it doesn't exist
os.makedirs(output_folder, exist_ok=True)


# === Function to get caption using OpenRouter ===
def get_openrouter_caption(image_path):
    # Upload image to a public server or convert to base64 Data URL
    with open(image_path, "rb") as f:
        image_data = f.read()
        encoded_image = base64.b64encode(image_data).decode("utf-8")
        data_url = f"data:image/jpeg;base64,{encoded_image}"

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "X-Title": "Snapture AI",
    }
               

    payload = {
        "model": MODEL_ID,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": 
                     "You're an AI content writer.\n\n"
                    "Task:\n"
                    "1. Generate a **short title** for this image — maximum 8 words or 2 lines.\n"
                    "2. Write a **concise description** in 1–2 lines only (no storytelling).\n\n"
                    "Avoid:\n"
                    "- Detailed explanations\n"
                    "- Repetitive or generic wording\n"
                    "- Exceeding length limits\n\n"
                    "If the image is unclear or contains only UI, still respond professionally."
                    },
                    {"type": "image_url", "image_url": {"url": data_url}}
                ]
            }
        ]
    }

    response = requests.post(API_URL, headers=headers, data=json.dumps(payload))

    if response.status_code == 200:
        result = response.json()
        try:
            content = result["choices"][0]["message"]["content"]
            parts = content.split("\n", 1)
            title = parts[0].strip() if len(parts) > 0 else "No title"
            description = parts[1].strip() if len(parts) > 1 else "No description"
            return title, description
        except Exception as e:
            print(f" Failed to parse response: {e}")
            return "Parse error", "Parse error"
    else:
        print(f" API Error ({response.status_code}): {response.text}")
        return "Failed to get title", "Failed to get description"

# === Process each image ===
for file in os.listdir(input_folder):
    if file.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".webp")):
        image_path = os.path.join(input_folder, file)
        txt_file = os.path.splitext(file)[0] + ".txt"
        txt_path = os.path.join(output_folder, txt_file)

        title, description = get_openrouter_caption(image_path)

        # Append model given info to .txt
        try:
            with open(txt_path, "a", encoding="utf-8") as f:
                f.write(f"Title:\n {title}\n\n\n\n\n")
                f.write(f"Description:\n {description}\n")
            print(f" TXT file created for: {txt_file}")
        except Exception as e:
            print(f" Couldn't write to {txt_file}: {e}")
