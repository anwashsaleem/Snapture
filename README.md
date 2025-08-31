# Snapture v0.4.0


This version introduces the `first functional UI (GUI)` for **Snapture** along with `search support` and a `Run button` to process screenshots without manually running code. It builds on the previous logic of [Clustering-based Screenshot Organization](https://github.com/anwashsaleem/Snapture/releases/tag/v0.3.1) but now makes the workflow more interactive and user-friendly. <br><br>


## Improvements:

- Simple Python-based `GUI` added to view screenshots and albums.
- Starts the captioning process directly from the UI by `Run button`.
- The UI refreshes automatically to show progress in `real-time`.
- Screenshots appear under `All Screenshots`, while clustered ones are shown under `Albums` (including any previously created albums).
- Now, you can `search` screenshots and albums by text in titles, descriptions, or album names. 
<br>

## Limitations:

- Currently GUI is very basic and coded in **Python**. Works only on `desktop` (not mobile or app-based yet).
- **Categorization** is still `file-based`. Metadata is saved in `.txt` files alongside screenshots (no database yet).
- Captions depend entirely on the `AI API` response. The better the AI response, the better the `categorization` will be.

<br>



## How to use it:

1. Place your screenshots in the `Screenshots` folder.
2. Add your own `API key` & `endpoint` in the script.
3. `Run` the script. The GUI will open automatically and display:
   -  All screenshots in the `Screenshots` section.
   -  Existing albums (if already created) in the `Albums` section.
4. Press the Run button to start captioning. The UI will:
   -  Generate `.txt files` with titles, descriptions, and tags for each screenshot.
   -  Update them in real time as screenshots are processed.
   -  Group related screenshots into `albums` based on text similarity using clusting method.
5. Adjust the *`threshold`* to control whether you want broader categories or more precise albums. <br><br><br>



> [!TIP]
> **Threshold Value**

> The threshold value defines how similar two captions need to be in order to be grouped into the same folder. A lower threshold (e.g., 0.1–0.2) makes clustering more relaxed, so even loosely related screenshots may end up in the same group, resulting in broader categories. A higher threshold (e.g., 0.5–0.7) makes clustering stricter, so only very similar screenshots are grouped, leading to smaller and more precise folders. Adjusting this value lets you control whether you want broader grouping or tighter categorization.`

<br><br><br> This version marks the first step toward a `usable interface`. Screenshots can now be browsed, searched, and organized in real time. The next milestone will be expanding **Snapture** into an `AI-powered mobile app` tool to make it truly accessible everywhere and taking it closer to the full vision of “Snapture”.
