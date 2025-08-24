# Snapture v0.3.1

This version is closest one to the **Snapture** concept, It has the main logic of automatically captioning & organizing screenshots. In this version, I added `clustering` logic that automatically groups screenshots into albums (folders) based on the similarity of their AI-generated titles and descriptions. Instead of relying only on *predefined keywords*, this version uses **text similarity** to detect related screenshots and place them together. <br><br>


## Improvements:

- **AI-powered** captioning generates titles, descriptions, and tags for each screenshot.
- Creates `.txt files` with metadata for every screenshot.
- Uses `clustering` to automatically group related screenshots.
- Introduces a `threshold value` to control clustering strictness:
  - **Lower threshold:** broader grouping, `fewer albums`.
  - **Higher threshold:** stricter grouping, `more albums`.

<br>

## Limitations:

- Captions depend entirely on the `AI API` response. The better the AI response, the better the `categorization` will be.
- No UI or tagging search yet. Categorization is still `file-based` (no database yet).

<br>

## How to use it:

1. Place screenshots in the `Screenshots` folder.
2. Add your own `API key` & endpoint in the script.
3. **Run** the script, it will generate `.txt files` and organize screenshots into `albums`.
4. Adjust the *`threshold`* to control whether you want broader categories or more precise albums. <br><br><br>

> [!TIP]
> **Threshold Value**

> The threshold value defines how similar two captions need to be in order to be grouped into the same folder. A lower threshold (e.g., 0.1–0.2) makes clustering more relaxed, so even loosely related screenshots may end up in the same group, resulting in broader categories. A higher threshold (e.g., 0.5–0.7) makes clustering stricter, so only very similar screenshots are grouped, leading to smaller and more precise folders. Adjusting this value lets you control whether you want broader grouping or tighter categorization.`

<br><br><br> This version brings **Snapture** very close to the original idea: the screenshots are no longer just stored, but intelligently captioned and grouped. The logic for an `AI-powered` screenshot organizer is now in place, waiting to be expanded with a real interface and storage system to make it fully “Snapture”.

