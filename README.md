# Snapture v0.1.0

In this version, I use a simple OCR method to extract text from images.
The goal is to organize screenshots by creating albums based on the text inside the images.
The OCR reads images from the 'Screenshots' folder and saves text files in the 'TXTs' folder.

But, this has limitations like:
- If the screenshot image does not contain any text, the text file will be empty.
- Images with unclear text or blur images produce meaningless text.
- Tesseract OCR must be installed locally for this to work.
- There is no user interface or tagging system yet.

This version is the starting point for smarter screenshot organization tool, Snapture.
