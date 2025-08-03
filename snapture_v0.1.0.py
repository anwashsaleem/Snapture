"""
Snapture v0.1.0 – A simple OCR tool to convert images to text files 

What it does:
- Reads all images in the 'Screenshots' folder
- Extracts text using Tesseract OCR
- Saves text files in the 'TXTs' folder

Limitations:
- Only works locally
- Requires Tesseract installed (Windows path configured)
- No UI or tags yet
"""



import os
from PIL import Image
import pytesseract


# Tesseract path for Windows, update this if your path is different than this
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Supported image extensions
IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".bmp", ".webp"]


# Get current directory where the Python script (.py file) is located
base_dir = os.path.dirname(os.path.abspath(__file__))

# Input and output folder paths
input_folder = os.path.join(base_dir, "Screenshots")
output_folder = os.path.join(base_dir, "TXTs")

# Create output folder if it doesn't exist
os.makedirs(output_folder, exist_ok=True)


# Find images in Screenshots folder
image_files = []
for file in os.listdir(input_folder):
    if os.path.splitext(file)[1].lower() in IMAGE_EXTENSIONS:
        image_files.append(file)

if not image_files:
    print("No image files found in the 'Screenshots' folder.")

print(f"Found {len(image_files)} image(s) in: {input_folder}\n")


# Process images one by one
for img_file in image_files:
    image_path = os.path.join(input_folder, img_file)
    txt_filename = os.path.splitext(img_file)[0] + ".txt"
    txt_path = os.path.join(output_folder, txt_filename)

    try:
        image = Image.open(image_path)
        extracted_text = pytesseract.image_to_string(image)

        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(extracted_text.strip())

        print(f"Created: {txt_filename}")

    except Exception as e:
        print(f"Failed on {img_file}: {e}")

print("\nAll images processed.")
