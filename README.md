# Snapture v0.3.0

In this version, I added the ability to automatically create **albums** (folders) for your screenshots based on `predefined keywords`. Screenshots are assigned to albums using **AI**-generated titles and descriptions, and a visual similarity check ensures similar screenshots are grouped together.



Improvements:

- First version that automatically creates albums (folders).
- Screenshots are assigned to albums based on `predefined keywords`.
- Uses **AI-powered** captioning to generate titles & descriptions for screenshots.
- Adds visual similarity check for organizing screenshots.



But this one also has limitations like:

- Accuracy is limited — keyword-based matching may misclassify screenshots.
- Screenshots without clear matches go into Uncategorized.
- No UI or tagging features yet.



How to use it:

1. Place screenshots in the `Screenshots` folder.
2. Add your `API key` & endpoint in the script.
3. Define your *album categories* & *keywords* in `keyword_categories`.
4. Run the script — it will create `.txt` files and organize screenshots into folders.


This version is the one step close to an **AI-powered** screenshot organizer, but there’s still more to make it fully “Snapture”.



