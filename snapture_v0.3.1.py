"""

Snapture v0.4.0 – GUI Support & Search functionality

How to use:
1. Place screenshots in the `Screenshots` folder.
2. Add your API key & endpoint in the script.
3. Run the script — it will create `.txt` files, organize screenshots into folders, and store metadata in the database.

Working:
- Uses AI to generate titles, descriptions & tags.
- Clusters screenshots based on similarity (adjustable threshold).
- Saves metadata in a database for better search & management.
- Minimal GUI added for viewing "All Screenshots" and "Albums".

"""



import os
import json
import base64
import shutil
import time
import threading
import requests
import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import os
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from tkinter import filedialog
from PIL import Image, ImageTk, ImageDraw, ImageFilter


from dotenv import load_dotenv
load_dotenv()

# Set your AI API key and URL here
AI_API_KEY = os.getenv("AI_API_KEY")
AI_BASE_URL = os.getenv("AI_BASE_URL")
AI_URL = f"{AI_BASE_URL}key={AI_API_KEY}"


# === Directories ===
base_directory = os.path.dirname(os.path.abspath(__file__))
screenshots_directory = os.path.join(base_directory, "Screenshots")
text_files_directory = os.path.join(base_directory, "TXTs")
albums_directory = os.path.join(base_directory, "Albums")

for folder in (text_files_directory, albums_directory):
    os.makedirs(folder, exist_ok=True)

# === Utility Functions ===
def sanitize(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', '', name).strip() or "Uncategorized"

def call_AI(prompt: str, image_path: str):
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
                print("❌ AI API rate limit. Try again later.")
                return None
            else:
                print("❌ AI API error:", response.text)
                return None
        except requests.exceptions.RequestException as e:
            print(f"[Attempt {attempt + 1}] AI API call failed: {e}")
            if attempt < 2:
                print("Retrying in 3 seconds...")
                time.sleep(3)
    print("❌ AI API failed after 3 attempts.")
    return None

# === Data Model ===
class ScreenshotItem:
    def __init__(self, file_name, image_path, title="", description="", tags=None, txt_path=None, album=None):
        self.file_name = file_name
        self.image_path = image_path
        self.title = title
        self.description = description
        self.tags = tags or []
        self.txt_path = txt_path
        self.album = album

# === Core Processing Logic (runs in background thread) ===
class SnaptureProcessor(threading.Thread):
    def __init__(self, update_callback):
        super().__init__()
        self.update_callback = update_callback
        self.screenshot_items = []
        self.clusters = []
        self.cluster_names = []
        self.stop_requested = False

    def run(self):
        # Only process uncategorized screenshots (no TXT or not in any album)
        self.screenshot_items.clear()
        uncategorized_items = []
        for file_name in sorted(os.listdir(screenshots_directory)):
            if not file_name.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".webp")):
                continue

            image_path = os.path.join(screenshots_directory, file_name)
            txt_file_name = os.path.splitext(file_name)[0] + ".txt"
            txt_file_path = os.path.join(text_files_directory, txt_file_name)

            # If TXT already exists, load it
            if os.path.exists(txt_file_path):
                with open(txt_file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                title, description, tags = self.parse_txt(content)
                # Check if already in an album
                already_in_album = False
                for album_folder in os.listdir(albums_directory):
                    album_path = os.path.join(albums_directory, album_folder)
                    if os.path.isdir(album_path) and file_name in os.listdir(album_path):
                        already_in_album = True
                        break
                if title and description and tags and already_in_album:
                    continue  # Already categorized, skip
            else:
                title, description, tags = "", "", []

            uncategorized_items.append((file_name, image_path, txt_file_path, title, description, tags))

        if not uncategorized_items:
            self.update_callback("info", "All screenshots are already categorized.")
            self.update_callback("done", None)
            return

        # Step 1: Caption screenshots and generate TXT files for uncategorized
        for file_name, image_path, txt_file_path, title, description, tags in uncategorized_items:
            if not title or not description or not tags:
                # Caption with AI
                caption_prompt = (
                    "You are an AI that captions screenshots.\n"
                    "Respond EXACTLY as:\n"
                    "Title: <up to 10 words>\n"
                    "Description: <1–3 lines>\n"
                    "Tags: <3–5 comma-separated keywords>\n"
                )
                caption_response = call_AI(caption_prompt, image_path)
                if not caption_response or "Title:" not in caption_response or "Tags:" not in caption_response:
                    continue
                title, description, tags = self.parse_caption(caption_response)
                # Save TXT
                with open(txt_file_path, "w", encoding="utf-8") as txt_file:
                    txt_file.write(f"Title:\n{title}\n\n")
                    txt_file.write(f"Description:\n{description}\n\n")
                    txt_file.write(f"Tags:\n{', '.join(tags)}")

            item = ScreenshotItem(
                file_name=file_name,
                image_path=image_path,
                title=title,
                description=description,
                tags=tags,
                txt_path=txt_file_path
            )
            self.screenshot_items.append(item)
            self.update_callback("captioned", item)

        if not self.screenshot_items:
            self.update_callback("error", "No new screenshots to categorize.")
            self.update_callback("done", None)
            return

        # Step 2: Cluster similar captions using TF-IDF + cosine similarity
        corpus = [item.title + " " + item.description for item in self.screenshot_items]
        tfidf_matrix = TfidfVectorizer().fit_transform(corpus)
        similarity_matrix = cosine_similarity(tfidf_matrix)

        threshold = 0.4
        clusters = []
        for index, item in enumerate(self.screenshot_items):
            added = False
            for cluster in clusters:
                existing_index = cluster[0]
                if similarity_matrix[index][existing_index] >= threshold:
                    cluster.append(index)
                    added = True
                    break
            if not added:
                clusters.append([index])
        self.clusters = clusters

        # Step 3: Suggest folder name for each cluster
        cluster_names = []
        for cluster_indices in clusters:
            filenames = [self.screenshot_items[i].file_name for i in cluster_indices]
            all_tags = sum((self.screenshot_items[i].tags for i in cluster_indices), [])
            folder_prompt = (
                "You are a folder-organization expert.\n"
                "Given these filenames and tags, suggest ONE concise (1–2 word) folder name.\n"
                f"Files: {filenames}\nTags: {all_tags}\n"
                "Return just the name."
            )
            sample_image_path = self.screenshot_items[cluster_indices[0]].image_path
            folder_name_response = call_AI(folder_prompt, sample_image_path)
            if folder_name_response:
                folder_name = sanitize(folder_name_response.splitlines()[0].split(":", 1)[-1].strip())
            else:
                folder_name = "Uncategorized"
            cluster_names.append(folder_name)
            for idx in cluster_indices:
                self.screenshot_items[idx].album = folder_name
            self.update_callback("clustered", (folder_name, [self.screenshot_items[i] for i in cluster_indices]))
        self.cluster_names = cluster_names

        # Step 4: Save clustered files into folders
        for cluster, folder_name in zip(clusters, cluster_names):
            destination_path = os.path.join(albums_directory, folder_name)
            os.makedirs(destination_path, exist_ok=True)
            for item_index in cluster:
                item = self.screenshot_items[item_index]
                shutil.copy2(item.image_path, os.path.join(destination_path, item.file_name))
                shutil.copy2(item.txt_path, os.path.join(destination_path, os.path.basename(item.txt_path)))
                self.update_callback("moved", (item, folder_name))
            self.update_callback("notify_album", folder_name)

        self.update_callback("done", None)

    def parse_caption(self, caption_response):
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
        return title, description, tags

    @staticmethod
    def parse_txt(content):
        title, description, tags = "", "", []
        lines = content.splitlines()
        i = 0
        while i < len(lines):
            if lines[i].startswith("Title:"):
                i += 1
                if i < len(lines): title = lines[i].strip()
            elif lines[i].startswith("Description:"):
                i += 1
                if i < len(lines): description = lines[i].strip()
            elif lines[i].startswith("Tags:"):
                i += 1
                if i < len(lines): tags = [tag.strip() for tag in lines[i].split(",") if tag.strip()]
            i += 1
        return title, description, tags

# === GUI ===
class SnaptureGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Snapture 4.0 — Screenshot Organizer")
        self.root.geometry("1100x700")
        self.root.configure(bg="#f7f7fa")
        self.screenshot_items = []
        self.albums = {}
        self.album_order = []
        self.processing = False

        # Create rounded button styles
        self._create_rounded_button_styles()

        # --- UI Layout ---
        # Top bar frame for search and run button
        self.topbar_frame = tk.Frame(self.root, bg="#f7f7fa")
        self.topbar_frame.pack(side="top", fill="x", padx=0, pady=(10, 0))

        # --- Homepage Icon (top left) ---
        self.home_button = tk.Button(self.topbar_frame, text="🏠", font=("Segoe UI", 14), command=self.go_home, bd=0, relief="flat", bg="#f7f7fa", fg="#666666", activebackground="#e0e7ef", activeforeground="#222222", cursor="hand2", highlightthickness=0, padx=8, pady=4)
        self.home_button.place(x=20, y=5)

        # --- Breadcrumbs (below search bar) ---
        self.breadcrumbs_frame = tk.Frame(self.root, bg="#f7f7fa")
        self.breadcrumbs_frame.pack(side="top", fill="x", padx=20, pady=(5, 0))
        self.current_path = ["Homepage"]
        self.update_breadcrumbs()

        # --- Search Bar (centered, rounded, long, shadow) ---
        self.search_var = tk.StringVar()
        self.search_type_var = tk.StringVar(value="All")
        self.search_suggestions = []
        self.search_results = []
        self._suggestion_index = -1

        # Custom rounded search bar with shadow
        self.search_canvas = tk.Canvas(self.topbar_frame, bg="#f7f7fa", highlightthickness=0, bd=0, height=54)
        self.search_canvas.pack(side="top", pady=0, expand=True)
        self.search_canvas.update_idletasks()
        self._draw_searchbar_bg()

        # Place search entry and combobox on top of the canvas
        self.search_entry = tk.Entry(self.topbar_frame, textvariable=self.search_var, font=("Segoe UI", 13), bd=0, relief="flat", bg="#ffffff", fg="#222222", highlightthickness=0, insertbackground="#222222")
        self.search_entry.place(x=0, y=0)  # Will be positioned in _position_searchbar_widgets
        self.search_entry.bind("<KeyRelease>", self._on_search_typing)
        self.search_entry.bind("<Return>", self._on_search_enter)
        self.search_entry.bind("<FocusIn>", self._on_search_typing)
        self.search_entry.bind("<Down>", self._on_suggestion_down)
        self.search_entry.bind("<Up>", self._on_suggestion_up)
        # Add binding to lose focus when clicking outside
        self.search_entry.bind("<FocusOut>", self._on_search_focus_out)

        # Load search icons
        self.search_icon_img = ImageTk.PhotoImage(Image.open(os.path.join(base_directory, "search_icon.png")).resize((36, 36)))
        self.search_icon_active_img = ImageTk.PhotoImage(Image.open(os.path.join(base_directory, "search_icon_active.png")).resize((36, 36)))

        # Create search icon button with image
        self.search_icon_button = tk.Button(
            self.topbar_frame,
            image=self.search_icon_img,
            command=self._on_search_enter,
            bd=0, relief="flat", bg="#ffffff", activebackground="#e0e7ef",
            cursor="hand2", highlightthickness=0
        )
        self.search_icon_button.place(x=0, y=-2)  # Will be positioned in _position_searchbar_widgets

        # 1. Create the suggestion box early
        self.suggestion_box = tk.Listbox(
            self.root, font=("Segoe UI", 11), height=5, bg="#ffffff",
            activestyle="dotbox", bd=1, relief="solid", highlightthickness=0,
            selectbackground="#4a90e2", selectforeground="white"
        )
        self.suggestion_box.bind("<ButtonRelease-1>", self._on_suggestion_click)
        self.suggestion_box.bind("<Return>", self._on_suggestion_enter)
        self.suggestion_box.bind("<Escape>", lambda e: self.suggestion_box.place_forget())

        # 2. Load the run button image
        self.run_snapture_img = ImageTk.PhotoImage(Image.open(os.path.join(base_directory, "run_snapture.png")))

        # 3. Create a label to display the image as a clickable icon
        self.play_button_label = tk.Label(
            self.topbar_frame,
            image=self.run_snapture_img,
            bg="#f7f7fa",
            cursor="hand2"
        )
        self.play_button_label.image = self.run_snapture_img  # Prevent garbage collection
        self.play_button_label.place(relx=1.0, rely=0.0, anchor="ne", x=-20, y=5)
        self.play_button_label.bind("<Button-1>", lambda e: self.start_processing())

        # Position all search bar widgets after play button is created
        self._position_searchbar_widgets()

        # --- Main Canvas (center) ---
        self.main_canvas = tk.Canvas(self.root, bg="#f7f7fa", highlightthickness=0)
        self.main_scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=self.main_canvas.yview)
        self.main_canvas.configure(yscrollcommand=self.main_scrollbar.set)
        self.main_canvas.pack(side="left", fill="both", expand=True, padx=10, pady=(0, 10))
        self.main_scrollbar.pack(side="right", fill="y")
        self.main_inner = tk.Frame(self.main_canvas, bg="#f7f7fa")
        self.main_canvas.create_window((0, 0), window=self.main_inner, anchor="nw")
        self.main_inner.bind("<Configure>", lambda e: self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all")))

        # Enable mousewheel scrolling (Windows, Mac, Linux)
        self.main_canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.main_canvas.bind_all("<Button-4>", self._on_mousewheel)  # Linux scroll up
        self.main_canvas.bind_all("<Button-5>", self._on_mousewheel)  # Linux scroll down

        # --- Notification (bottom left) ---
        self.notification_label = None

        # Status Bar (hidden, replaced by notification)
        self.status_var = tk.StringVar(value="Ready.")

        # For image caching
        self.thumb_cache = {}

        # For album view
        self.album_windows = {}

        # Load all screenshots and albums on startup
        self.load_all_data()

        # Responsive grid: update on resize
        self.root.bind("<Configure>", self._on_root_resize)
        self._last_width = self.root.winfo_width()
        
        # Bind root to hide suggestions when clicking outside
        self.root.bind("<Button-1>", self._on_root_click)

    def _create_rounded_button_styles(self):
        # Create rounded button styles
        ttk.Style().configure("Rounded.TButton", padding=6, relief="flat", borderwidth=0)
        ttk.Style().configure("Rounded.TCombobox", padding=6, relief="flat", borderwidth=0)
        ttk.Style().configure("Rounded.TEntry", padding=6, relief="flat", borderwidth=0)

    def _draw_searchbar_bg(self):
        # Draw a rounded rectangle for the search bar background (no shadow)
        self.search_canvas.delete("all")
        width = self.root.winfo_width() if self.root.winfo_width() > 1 else 1100
        # Add margins: 20px from left and right
        margin = 20
        # Make search bar and Run button same height
        bar_w = min(500, width - 200 - 2*margin)  # Account for margins
        bar_h = 44
        # Center the search bar
        bar_x = (width - bar_w) // 2  # Center the search bar
        bar_y = 5
        radius = 22
        self.search_canvas.config(width=width, height=bar_h + 2*bar_y)
        # Main bar (no shadow)
        self.search_canvas.create_oval(bar_x, bar_y, bar_x+radius*2, bar_y+bar_h, fill="#ffffff", outline="#e0e7ef", width=1.5)
        self.search_canvas.create_oval(bar_x+bar_w-radius*2, bar_y, bar_x+bar_w, bar_y+bar_h, fill="#ffffff", outline="#e0e7ef", width=1.5)
        self.search_canvas.create_rectangle(bar_x+radius, bar_y, bar_x+bar_w-radius, bar_y+bar_h, fill="#ffffff", outline="#e0e7ef", width=1.5)
        self._searchbar_geom = (bar_x, bar_y, bar_w, bar_h, radius)

    def _position_searchbar_widgets(self):
        # Place the search entry, combobox, and button on top of the search bar canvas
        self.root.update_idletasks()
        width = self.root.winfo_width() if self.root.winfo_width() > 1 else 1100
        bar_x, bar_y, bar_w, bar_h, radius = getattr(self, "_searchbar_geom", (250, 5, 500, 44, 22))  # Updated for centered position
        entry_pad = 12
        icon_w = 36  # Width for search icon button (make it circular)
        entry_w = bar_w - icon_w - 16  # Leave space for icon button
        entry_x = bar_x + entry_pad
        entry_y = bar_y + 4
        
        # Position search entry and icon button inside the search bar
        self.search_entry.place(x=entry_x, y=entry_y, width=entry_w, height=bar_h-8)
        # Position search icon at the right edge of search bar
        self.search_icon_button.place(x=bar_x+bar_w-icon_w, y=entry_y, width=icon_w, height=bar_h-4)
        
        # Remove play_button_label.place(...) from here to prevent disappearing
        # Remove the problematic lift() call for canvas
        self.search_entry.lift()
        self.search_icon_button.lift()
        self.play_button_label.lift()
        
        # Update search icon button state based on search text
        self._update_search_button_state()
        
        # Create filter chips below search bar
        self._create_filter_chips()

    def _update_search_button_state(self):
        """Update search button appearance based on search text"""
        if hasattr(self, 'search_icon_button'):
            text = self.search_var.get().strip()
            if text:
                # Enable state - blue color
                self.search_icon_button.config(image=self.search_icon_active_img)
            else:
                # Disabled state - dark gray
                self.search_icon_button.config(image=self.search_icon_img)

    def _create_filter_chips(self):
        """Create filter chips below the search bar"""
        # Remove existing filter chips if any
        if hasattr(self, 'filter_chips_frame'):
            self.filter_chips_frame.destroy()
        
        # Create frame for filter chips
        self.filter_chips_frame = tk.Frame(self.topbar_frame, bg="#f7f7fa")
        self.filter_chips_frame.pack(side="top", pady=(5, 0))
        
        # Filter options
        filter_options = ["All", "Screenshots", "Albums"]
        
        for i, option in enumerate(filter_options):
            chip = tk.Button(
                self.filter_chips_frame,
                text=option,
                font=("Segoe UI", 10),
                bd=0,
                relief="flat",
                bg="#e0e7ef" if option == "All" else "#f0f0f0",
                fg="#222222" if option == "All" else "#666666",
                activebackground="#4a90e2" if option == "All" else "#e0e7ef",
                activeforeground="white" if option == "All" else "#222222",
                cursor="hand2",
                highlightthickness=0,
                padx=12,
                pady=4,
                command=lambda opt=option: self._on_filter_chip_click(opt)
            )
            chip.pack(side="left", padx=(0, 8))
            
            # Store reference to update styling
            setattr(self, f'filter_chip_{option.lower()}', chip)

    def _on_filter_chip_click(self, option):
        """Handle filter chip clicks"""
        # Update search type
        self.search_type_var.set(option)
        
        # Update chip styling
        for opt in ["All", "Screenshots", "Albums"]:
            chip = getattr(self, f'filter_chip_{opt.lower()}', None)
            if chip:
                if opt == option:
                    # Selected chip
                    chip.config(bg="#e0e7ef", fg="#222222", activebackground="#4a90e2", activeforeground="white")
                else:
                    # Unselected chip
                    chip.config(bg="#f0f0f0", fg="#666666", activebackground="#e0e7ef", activeforeground="#222222")
        
        # Update the main page content based on filter
        self.update_main_page()
        
        # Trigger search if there's text
        if self.search_var.get().strip():
            self._on_search_enter()

    def _on_root_resize(self, event):
        # Only update if width changed (avoid infinite loops)
        if event.widget == self.root:
            width = self.root.winfo_width()
            if width != getattr(self, "_last_width", None):
                self._last_width = width
                self._draw_searchbar_bg()
                self._position_searchbar_widgets()
                self.update_main_page()

    def _on_mousewheel(self, event):
        # Windows/Mac
        if hasattr(event, "num") and event.num == 4 or (hasattr(event, "delta") and event.delta > 0):
            self.main_canvas.yview_scroll(-1, "units")
        elif hasattr(event, "num") and event.num == 5 or (hasattr(event, "delta") and event.delta < 0):
            self.main_canvas.yview_scroll(1, "units")

    def _on_search_typing(self, event):
        query = self.search_var.get().strip().lower()
        search_type = self.search_type_var.get()
        
        # Update search button state
        self._update_search_button_state()
        
        suggestions = []
        if not query:
            self.suggestion_box.place_forget()
            return
        # Gather all possible search targets, no duplicates
        screenshot_targets = []
        seen_screenshots = set()
        for item in self.all_screenshots:
            unique_id = item.file_name
            fields = [
                item.title.lower() if item.title else "",
                item.description.lower() if item.description else "",
                " ".join(item.tags).lower() if item.tags else "",
                item.album.lower() if item.album else "",
                os.path.splitext(item.file_name)[0].lower()
            ]
            if any(query in f for f in fields):
                if unique_id not in seen_screenshots:
                    screenshot_targets.append(item)
                    seen_screenshots.add(unique_id)
        album_targets = []
        seen_albums = set()
        for album_name in self.album_order:
            if query in album_name.lower() and album_name not in seen_albums:
                album_targets.append(album_name)
                seen_albums.add(album_name)
        # Build suggestions based on current filter
        if search_type in ("All", "Screenshots"):
            for item in screenshot_targets:
                suggestions.append(f"Screenshot: {item.title or os.path.splitext(item.file_name)[0]}")
        if search_type in ("All", "Albums"):
            for album_name in album_targets:
                suggestions.append(f"Album: {album_name}")
        self.search_suggestions = suggestions[:10]
        # Show suggestions below the search bar
        if self.search_suggestions:
            self.root.update_idletasks()
            x = self.search_entry.winfo_rootx() - self.root.winfo_rootx()
            y = self.search_entry.winfo_rooty() - self.root.winfo_rooty() + self.search_entry.winfo_height()
            self.suggestion_box.delete(0, tk.END)
            for s in self.search_suggestions:
                self.suggestion_box.insert(tk.END, s)
            self.suggestion_box.place(x=x, y=y, width=self.search_entry.winfo_width())
            self.suggestion_box.lift()
            self._suggestion_index = -1
        else:
            self.suggestion_box.place_forget()

    def _on_suggestion_down(self, event):
        if not self.search_suggestions:
            return
        self._suggestion_index = (self._suggestion_index + 1) % len(self.search_suggestions)
        self.suggestion_box.select_clear(0, tk.END)
        self.suggestion_box.select_set(self._suggestion_index)
        self.suggestion_box.activate(self._suggestion_index)
        self.suggestion_box.see(self._suggestion_index)

    def _on_suggestion_up(self, event):
        if not self.search_suggestions:
            return
        self._suggestion_index = (self._suggestion_index - 1) % len(self.search_suggestions)
        self.suggestion_box.select_clear(0, tk.END)
        self.suggestion_box.select_set(self._suggestion_index)
        self.suggestion_box.activate(self._suggestion_index)
        self.suggestion_box.see(self._suggestion_index)

    def _on_suggestion_click(self, event):
        selection = self.suggestion_box.curselection()
        if selection:
            value = self.suggestion_box.get(selection[0])
            self.search_var.set(value.split(":", 1)[-1].strip())
            self.suggestion_box.place_forget()
            self._on_search_enter(None)

    def _on_suggestion_enter(self, event):
        selection = self.suggestion_box.curselection()
        if selection:
            value = self.suggestion_box.get(selection[0])
            self.search_var.set(value.split(":", 1)[-1].strip())
            self.suggestion_box.place_forget()
            self._on_search_enter(None)

    def _on_search_enter(self, event=None):
        # Hide suggestions when Enter is pressed
        self.suggestion_box.place_forget()
        
        query = self.search_var.get().strip().lower()
        search_type = self.search_type_var.get()
        screenshot_results = []
        album_results = []
        seen_screenshots = set()
        seen_albums = set()
        if not query:
            self.search_results = []
            self.update_main_page()
            return
        # Search screenshots (no duplicates)
        if search_type in ("All", "Screenshots"):
            for item in self.all_screenshots:
                unique_id = item.file_name
                fields = [
                    item.title.lower() if item.title else "",
                    item.description.lower() if item.description else "",
                    " ".join(item.tags).lower() if item.tags else "",
                    item.album.lower() if item.album else "",
                    os.path.splitext(item.file_name)[0].lower()
                ]
                if any(query in f for f in fields):
                    if unique_id not in seen_screenshots:
                        screenshot_results.append(item)
                        seen_screenshots.add(unique_id)
        # Search albums (no duplicates)
        if search_type in ("All", "Albums"):
            for album_name in self.album_order:
                if query in album_name.lower() and album_name not in seen_albums:
                    album_results.append(album_name)
                    seen_albums.add(album_name)
        self.search_results = (screenshot_results, album_results)
        self.update_main_page(search_mode=True)

    def load_all_data(self):
        # Load albums and their screenshots if already categorized
        self.albums = {}
        self.album_order = []
        for album_folder in sorted(os.listdir(albums_directory)):
            album_path = os.path.join(albums_directory, album_folder)
            if not os.path.isdir(album_path):
                continue
            items = []
            for file_name in sorted(os.listdir(album_path)):
                if not file_name.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".webp")):
                    continue
                image_path = os.path.join(album_path, file_name)
                txt_file_name = os.path.splitext(file_name)[0] + ".txt"
                txt_file_path = os.path.join(album_path, txt_file_name)
                title, description, tags = "", "", []
                if os.path.exists(txt_file_path):
                    with open(txt_file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    title, description, tags = SnaptureProcessor.parse_txt(content)
                item = ScreenshotItem(file_name, image_path, title, description, tags, txt_file_path, album=album_folder)
                items.append(item)
            if items:
                self.albums[album_folder] = items
                self.album_order.append(album_folder)

        # Load all screenshots (including those in albums and uncategorized)
        self.all_screenshots = []
        # Add uncategorized screenshots (not in any album)
        album_file_names = set()
        for album_items in self.albums.values():
            for item in album_items:
                album_file_names.add(item.file_name)
        for file_name in sorted(os.listdir(screenshots_directory)):
            if not file_name.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".webp")):
                continue
            image_path = os.path.join(screenshots_directory, file_name)
            txt_file_name = os.path.splitext(file_name)[0] + ".txt"
            txt_file_path = os.path.join(text_files_directory, txt_file_name)
            title, description, tags = "", "", []
            if os.path.exists(txt_file_path):
                with open(txt_file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                title, description, tags = SnaptureProcessor.parse_txt(content)
            # If this file is also in an album, skip adding here (will show in album section)
            if file_name in album_file_names:
                continue
            item = ScreenshotItem(file_name, image_path, title, description, tags, txt_file_path)
            self.all_screenshots.append(item)
        # Add all album screenshots (flattened)
        for album_name in self.album_order:
            for item in self.albums[album_name]:
                # For the "all" section, we want to show all screenshots, so add them too
                self.all_screenshots.append(item)
        self.update_main_page()

    def start_processing(self):
        if self.processing:
            return
        self.processing = True
        self.show_slide_notification("Processing uncategorized screenshots...")
        self.play_button_label.config(state="disabled")
        self.processor = SnaptureProcessor(self.process_update)
        threading.Thread(target=self.processor.run, daemon=True).start()

    def process_update(self, event, data):
        # Called from background thread, so use after() for UI updates
        def _update():
            if event == "captioned":
                self.show_slide_notification(f"Captioned: {data.file_name}")
                self.load_all_data()
            elif event == "clustered":
                album_name, items = data
                self.show_slide_notification(f"Clustered: {album_name}")
                self.albums[album_name] = items
                if album_name not in self.album_order:
                    self.album_order.append(album_name)
                self.load_all_data()
            elif event == "moved":
                item, album_name = data
                self.show_slide_notification(f"Moved: {item.file_name} → {album_name}")
            elif event == "notify_album":
                self.show_slide_notification(f"Created new album: {data}")
            elif event == "info":
                self.show_slide_notification(str(data))
            elif event == "done":
                self.show_slide_notification("Done! Check Albums section below.")
                self.processing = False
                self.play_button_label.config(state="normal")
                self.load_all_data()
            elif event == "error":
                self.show_slide_notification(str(data))
                self.processing = False
                self.play_button_label.config(state="normal")
        self.root.after(0, _update)

    def show_slide_notification(self, message, duration=3500):
        # Remove previous notification if exists
        if self.notification_label and self.notification_label.winfo_exists():
            self.notification_label.destroy()
        # Notification at bottom right
        self.notification_label = tk.Label(self.root, text=message, bg="#323232", fg="white",
                                           font=("Segoe UI", 11, "bold"), bd=2, relief="ridge", padx=18, pady=8)
        self.notification_label.place(relx=1.0, rely=1.0, anchor="se", x=-20, y=-20)
        self.notification_label.after(duration, self.notification_label.destroy)

    def update_main_page(self, search_mode=False):
        # Clear everything
        for widget in self.main_inner.winfo_children():
            widget.destroy()

        # Get current filter selection
        current_filter = self.search_type_var.get()

        # --- All Screenshots Section ---
        # Set a left margin for all content (including headings and grids)
        LEFT_MARGIN = 20
        RIGHT_MARGIN = 20

        # Determine what to show based on filter
        if current_filter == "Screenshots":
            # Show both categorized and uncategorized screenshots in separate sections
            categorized_screenshots = [item for item in self.all_screenshots if item.album]
            uncategorized_screenshots = [item for item in self.all_screenshots if not item.album]
            total_screenshots = len(self.all_screenshots)
            categorized_count = len(categorized_screenshots)
            uncategorized_count = len(uncategorized_screenshots)
            heading_text = f"Screenshots ({total_screenshots} total)"
            show_albums_section = False
        elif current_filter == "Albums":
            # Show album names as large squares with album covers (no individual screenshots)
            heading_text = f"Albums ({len(self.album_order)} total)"
            show_albums_section = False
            show_album_grid = True
            screenshots = []  # Don't show individual screenshots in Albums filter
        else:  # "All"
            # Show all screenshots and albums in separate sections
            screenshots = self.all_screenshots
            heading_text = "All Screenshots"
            show_albums_section = True
            show_album_grid = True  # Show album grid in All filter
            show_individual_screenshots = True  # Show individual screenshots too

        # If in search mode, show only search results (no duplicates)
        if search_mode and hasattr(self, "search_results") and self.search_results:
            search_screenshots, album_names = self.search_results
            # Apply filter to search results
            if current_filter == "Screenshots":
                # For search in Screenshots filter, show both categorized and uncategorized
                search_categorized = [item for item in search_screenshots if item.album]
                search_uncategorized = [item for item in search_screenshots if not item.album]
                screenshots_to_show = search_categorized + search_uncategorized
            elif current_filter == "Albums":
                screenshots_to_show = [item for item in search_screenshots if item.album]
            else:
                screenshots_to_show = search_screenshots
            album_names_to_show = album_names if current_filter != "Screenshots" else []
        else:
            album_names_to_show = self.album_order if show_albums_section else []

        heading1 = tk.Label(self.main_inner, text=heading_text, font=("Segoe UI", 18, "bold"), bg="#f7f7fa")
        heading1.grid(row=0, column=0, sticky="w", padx=LEFT_MARGIN, pady=(20, 10), columnspan=100)

        # For Screenshots filter, show categorized and uncategorized sections
        if current_filter == "Screenshots":
            # Show categorized screenshots section
            if categorized_screenshots:
                categorized_heading = tk.Label(self.main_inner, text=f"Categorized Screenshots ({categorized_count})", font=("Segoe UI", 15, "bold"), bg="#f7f7fa", fg="#4a90e2")
                categorized_heading.grid(row=1, column=0, sticky="w", padx=LEFT_MARGIN+10, pady=(20, 10), columnspan=100)
                screenshots_to_show = categorized_screenshots
                start_row = 2
            else:
                start_row = 1
                screenshots_to_show = []
            
            # Show uncategorized section only if there are uncategorized screenshots
            if uncategorized_screenshots:
                show_uncategorized_section = True
            else:
                show_uncategorized_section = False
                # Show message if all screenshots are categorized
                if categorized_screenshots:
                    all_categorized_msg = tk.Label(self.main_inner, text="All screenshots are categorized! 🎉", font=("Segoe UI", 12, "bold"), bg="#f7f7fa", fg="#4a90e2")
                    all_categorized_msg.grid(row=start_row, column=0, sticky="w", padx=LEFT_MARGIN+10, pady=20, columnspan=100)
        else:
            # For other filters, show all screenshots normally
            screenshots_to_show = screenshots
            start_row = 1
            show_uncategorized_section = False

        # --- Responsive grid layout for screenshots ---
        thumb_size = (120, 120)
        thumb_padx = 24  # Clean spacing between screenshots
        thumb_pady = 32  # Vertical spacing for clean layout
        title_font = ("Segoe UI Semibold", 10)  # semibold, not bold
        title_wraplength = thumb_size[0]  # wrap title to width of image
        title_justify = "left"

        # Calculate the max title height in each row for vertical alignment
        def get_title_height(title, font, wraplength):
            # Create a hidden label to measure height
            temp = tk.Label(self.main_inner, text=title, font=font, wraplength=wraplength, justify=title_justify)
            temp.update_idletasks()
            h = temp.winfo_reqheight()
            temp.destroy()
            return h

        # Determine number of columns based on window width
        def get_max_cols():
            try:
                # Get the width of the canvas (visible area)
                width = self.main_canvas.winfo_width()
                if width <= 1:
                    width = self.root.winfo_width()
                usable_width = max(width - LEFT_MARGIN - RIGHT_MARGIN, 300)
                # Each thumb + padding
                per_thumb = thumb_size[0] + thumb_padx
                max_cols = max(1, usable_width // per_thumb)
                return max_cols
            except Exception:
                return 6  # fallback

        max_cols = get_max_cols()

        # Prepare grid: for each row, find max title height
        grid = []
        idx = 0
        while idx < len(screenshots_to_show):
            row_items = screenshots_to_show[idx:idx+max_cols]
            row_titles = [
                (item.title if item.title else os.path.splitext(item.file_name)[0])
                for item in row_items
            ]
            row_title_heights = [
                get_title_height(title, title_font, title_wraplength)
                for title in row_titles
            ]
            max_title_height = max(row_title_heights) if row_title_heights else 0
            grid.append((row_items, max_title_height))
            idx += max_cols

        row = start_row
        for row_items, max_title_height in grid:
            for col, item in enumerate(row_items):
                # Responsive: calculate left/right margin for first/last column
                if col == 0:
                    padx = (LEFT_MARGIN, thumb_padx//2)
                elif col == len(row_items) - 1:
                    padx = (thumb_padx//2, RIGHT_MARGIN)
                else:
                    padx = (thumb_padx//2, thumb_padx//2)
                # Frame with rounded corners and soft shadow
                frame = tk.Frame(self.main_inner, bg="#f7f7fa", bd=0, width=thumb_size[0], height=thumb_size[1]+max_title_height)
                frame.grid(row=row, column=col, padx=padx, pady=thumb_pady//2, sticky="nw")
                frame.grid_propagate(False)
                # Shadow (soft, not harsh)
                shadow_canvas = tk.Canvas(frame, width=thumb_size[0], height=thumb_size[1], bg="#f7f7fa", highlightthickness=0, bd=0)
                shadow_canvas.place(x=0, y=0)
                shadow_canvas.create_oval(4, 4, thumb_size[0]-4, thumb_size[1]-4, fill="#e3e6ee", outline="", width=0)
                # Thumbnail with rounded corners
                thumb = self.get_thumbnail(item.image_path, size=thumb_size)
                thumb_label = tk.Label(frame, image=thumb, bg="#f7f7fa", bd=0, relief="flat", cursor="hand2")
                thumb_label.image = thumb
                thumb_label.place(x=0, y=0, width=thumb_size[0], height=thumb_size[1])
                title = item.title if item.title else os.path.splitext(item.file_name)[0]
                title_label = tk.Label(
                    frame,
                    text=title,
                    font=title_font,
                    bg="#f7f7fa",
                    anchor="w",
                    justify=title_justify,
                    wraplength=title_wraplength
                )
                # Place title directly below image, left-aligned, width of image, height=max_title_height
                title_label.place(x=0, y=thumb_size[1], width=thumb_size[0], height=max_title_height)
                thumb_label.bind("<Button-1>", lambda e, i=item: self.open_screenshot_detail(i))
            row += 1

        # If no screenshots, show a message
        if not screenshots_to_show:
            empty_label = tk.Label(self.main_inner, text="No screenshots found.", font=("Segoe UI", 12), bg="#f7f7fa")
            empty_label.grid(row=row, column=0, sticky="w", padx=LEFT_MARGIN, pady=10)
            row += 1
        else:
            row += 1

        # For Screenshots filter, add uncategorized section after categorized
        if current_filter == "Screenshots" and show_uncategorized_section and uncategorized_screenshots:
            # Add uncategorized screenshots section
            uncategorized_heading = tk.Label(self.main_inner, text=f"Uncategorized Screenshots ({uncategorized_count})", font=("Segoe UI", 15, "bold"), bg="#f7f7fa", fg="#666666")
            uncategorized_heading.grid(row=row, column=0, sticky="w", padx=LEFT_MARGIN+10, pady=(40, 10), columnspan=100)
            row += 1
            
            # Grid for uncategorized screenshots
            uncategorized_grid = []
            idx = 0
            while idx < len(uncategorized_screenshots):
                row_items = uncategorized_screenshots[idx:idx+max_cols]
                row_titles = [
                    (item.title if item.title else os.path.splitext(item.file_name)[0])
                    for item in row_items
                ]
                row_title_heights = [
                    get_title_height(title, title_font, title_wraplength)
                    for title in row_titles
                ]
                max_title_height = max(row_title_heights) if row_title_heights else 0
                uncategorized_grid.append((row_items, max_title_height))
                idx += max_cols

            for row_items, max_title_height in uncategorized_grid:
                for col, item in enumerate(row_items):
                    # Responsive: calculate left/right margin for first/last column
                    if col == 0:
                        padx = (LEFT_MARGIN+10, thumb_padx//2)
                    elif col == len(row_items) - 1:
                        padx = (thumb_padx//2, RIGHT_MARGIN)
                    else:
                        padx = (thumb_padx//2, thumb_padx//2)
                    # Frame with rounded corners and soft shadow
                    frame = tk.Frame(self.main_inner, bg="#f7f7fa", bd=0, width=thumb_size[0], height=thumb_size[1]+max_title_height)
                    frame.grid(row=row, column=col, padx=padx, pady=thumb_pady//2, sticky="nw")
                    frame.grid_propagate(False)
                    # Shadow (soft, not harsh)
                    shadow_canvas = tk.Canvas(frame, width=thumb_size[0], height=thumb_size[1], bg="#f7f7fa", highlightthickness=0, bd=0)
                    shadow_canvas.place(x=0, y=0)
                    shadow_canvas.create_oval(4, 4, thumb_size[0]-4, thumb_size[1]-4, fill="#e3e6ee", outline="", width=0)
                    # Thumbnail with rounded corners
                    thumb = self.get_thumbnail(item.image_path, size=thumb_size)
                    thumb_label = tk.Label(frame, image=thumb, bg="#f7f7fa", bd=0, relief="flat", cursor="hand2")
                    thumb_label.image = thumb
                    thumb_label.place(x=0, y=0, width=thumb_size[0], height=thumb_size[1])
                    title = item.title if item.title else os.path.splitext(item.file_name)[0]
                    title_label = tk.Label(
                        frame,
                        text=title,
                        font=title_font,
                        bg="#f7f7fa",
                        anchor="w",
                        justify=title_justify,
                        wraplength=title_wraplength
                    )
                    # Place title directly below image, left-aligned, width of image, height=max_title_height
                    title_label.place(x=0, y=thumb_size[1], width=thumb_size[0], height=max_title_height)
                    thumb_label.bind("<Button-1>", lambda e, i=item: self.open_screenshot_detail(i))
                row += 1

        # For Albums filter, show album grid
        if (current_filter == "Albums" or current_filter == "All") and show_album_grid:
            # Add albums section heading for All filter
            if current_filter == "All":
                albums_heading = tk.Label(self.main_inner, text=f"Albums ({len(self.album_order)} total)", font=("Segoe UI", 18, "bold"), bg="#f7f7fa")
                albums_heading.grid(row=row, column=0, sticky="w", padx=LEFT_MARGIN, pady=(40, 16), columnspan=100)
                row += 1
            
            # Album grid layout
            album_thumb_size = (240, 240)  # 2x screenshot size
            album_thumb_padx = 32
            album_thumb_pady = 40
            album_title_font = ("Segoe UI Semibold", 12)
            album_title_wraplength = album_thumb_size[0]
            
            # Calculate max columns for album grid
            def get_album_max_cols():
                try:
                    width = self.main_canvas.winfo_width()
                    if width <= 1:
                        width = self.root.winfo_width()
                    usable_width = max(width - LEFT_MARGIN - RIGHT_MARGIN, 300)
                    per_album = album_thumb_size[0] + album_thumb_padx
                    max_cols = max(1, usable_width // per_album)
                    return max_cols
                except Exception:
                    return 3  # fallback
            
            album_max_cols = get_album_max_cols()
            
            # Create album grid
            album_grid = []
            idx = 0
            while idx < len(self.album_order):
                row_albums = self.album_order[idx:idx+album_max_cols]
                album_grid.append(row_albums)
                idx += album_max_cols
            
            for row_albums in album_grid:
                for col, album_name in enumerate(row_albums):
                    # Responsive: calculate left/right margin for first/last column
                    if col == 0:
                        padx = (LEFT_MARGIN, album_thumb_padx//2)
                    elif col == len(row_albums) - 1:
                        padx = (album_thumb_padx//2, RIGHT_MARGIN)
                    else:
                        padx = (album_thumb_padx//2, album_thumb_padx//2)
                    
                    # Album frame
                    album_frame = tk.Frame(self.main_inner, bg="#f7f7fa", bd=0, width=album_thumb_size[0], height=album_thumb_size[1]+50)
                    album_frame.grid(row=row, column=col, padx=padx, pady=album_thumb_pady//2, sticky="nw")
                    album_frame.grid_propagate(False)
                    
                    # Shadow for album
                    shadow_canvas = tk.Canvas(album_frame, width=album_thumb_size[0], height=album_thumb_size[1], bg="#f7f7fa", highlightthickness=0, bd=0)
                    shadow_canvas.place(x=0, y=0)
                    shadow_canvas.create_oval(8, 8, album_thumb_size[0]-8, album_thumb_size[1]-8, fill="#e3e6ee", outline="", width=0)
                    
                    # Get first screenshot from album as cover
                    album_items = self.albums.get(album_name, [])
                    if album_items:
                        cover_item = album_items[0]
                        cover_thumb = self.get_thumbnail(cover_item.image_path, size=album_thumb_size)
                        cover_label = tk.Label(album_frame, image=cover_thumb, bg="#f7f7fa", bd=0, relief="flat", cursor="hand2")
                        cover_label.image = cover_thumb
                        cover_label.place(x=0, y=0, width=album_thumb_size[0], height=album_thumb_size[1])
                        cover_label.bind("<Button-1>", lambda e, album=album_name: self.open_album_from_grid(album))
                    else:
                        # Empty album placeholder
                        placeholder_label = tk.Label(album_frame, text="📁", font=("Segoe UI", 48), bg="#f7f7fa", fg="#cccccc", bd=0, relief="flat", cursor="hand2")
                        placeholder_label.place(x=0, y=0, width=album_thumb_size[0], height=album_thumb_size[1])
                        placeholder_label.bind("<Button-1>", lambda e, album=album_name: self.open_album_from_grid(album))
                    
                    # Album name below
                    album_name_label = tk.Label(
                        album_frame,
                        text=album_name,
                        font=album_title_font,
                        bg="#f7f7fa",
                        anchor="w",
                        justify="left",
                        wraplength=album_title_wraplength
                    )
                    album_name_label.place(x=0, y=album_thumb_size[1]+5, width=album_thumb_size[0], height=40)
                row += 1

    def get_thumbnail(self, image_path, size=(120, 120)):
        key = (image_path, size)
        if key in self.thumb_cache:
            return self.thumb_cache[key]
        try:
            img = Image.open(image_path)
            img = img.convert("RGB")
            # Make square crop
            min_side = min(img.size)
            left = (img.width - min_side) // 2
            top = (img.height - min_side) // 2
            img = img.crop((left, top, left + min_side, top + min_side))
            img = img.resize(size, Image.LANCZOS)
            # Rounded corners
            radius = 22
            mask = Image.new("L", size, 0)
            draw = ImageDraw.Draw(mask)
            draw.rounded_rectangle([0, 0, size[0], size[1]], radius=radius, fill=255)
            img.putalpha(mask)
            # Soft shadow (optional, already handled in grid, so just return image)
            tkimg = ImageTk.PhotoImage(img)
        except Exception:
            tkimg = None
        self.thumb_cache[key] = tkimg
        return tkimg

    def open_screenshot_detail(self, item: ScreenshotItem):
        detail = tk.Toplevel(self.root)
        detail.title(item.title or item.file_name)
        detail.geometry("600x700")
        detail.configure(bg="#f7f7fa")
        # Full image (centered)
        try:
            img = Image.open(item.image_path)
            img.thumbnail((550, 400), Image.LANCZOS)
            # Rounded corners for detail view
            radius = 32
            size = img.size
            mask = Image.new("L", size, 0)
            draw = ImageDraw.Draw(mask)
            draw.rounded_rectangle([0, 0, size[0], size[1]], radius=radius, fill=255)
            img.putalpha(mask)
            tkimg = ImageTk.PhotoImage(img)
            img_label = tk.Label(detail, image=tkimg, bg="#f7f7fa")
            img_label.image = tkimg
            img_label.pack(pady=10)
        except Exception:
            img_label = tk.Label(detail, text="(Image not available)", bg="#f7f7fa")
            img_label.pack(pady=10)
        # Info section (left-aligned, no "Title:", "Description:", "Tags:" prefixes)
        info_frame = tk.Frame(detail, bg="#f7f7fa")
        info_frame.pack(fill="x", padx=30, pady=10, anchor="w")
        # Title (bold, left-aligned)
        title = item.title if item.title else os.path.splitext(item.file_name)[0]
        title_label = tk.Label(info_frame, text=title, font=("Segoe UI", 14, "bold"), bg="#f7f7fa", anchor="w", justify="left")
        title_label.pack(fill="x", anchor="w", pady=(0, 4))
        # Description (regular, left-aligned)
        desc_label = tk.Label(info_frame, text=item.description, font=("Segoe UI", 12), bg="#f7f7fa", anchor="w", justify="left", wraplength=520)
        desc_label.pack(fill="x", anchor="w", pady=(0, 4))
        # Tags (medium size, left-aligned, comma separated)
        tags_text = ", ".join(item.tags)
        tags_label = tk.Label(info_frame, text=tags_text, font=("Segoe UI Semibold", 11), bg="#f7f7fa", anchor="w", justify="left", wraplength=520)
        tags_label.pack(fill="x", anchor="w", pady=(0, 4))
        # Album (left-aligned, separated from above)
        album_label = tk.Label(info_frame, text=(item.album or "Uncategorized"), font=("Segoe UI", 11, "italic"), bg="#f7f7fa", anchor="w", justify="left")
        album_label.pack(fill="x", anchor="w", pady=(8, 0))

    def open_album_from_grid(self, album_name):
        # Update breadcrumbs
        self.current_path = ["Homepage", "Albums", album_name]
        self.update_breadcrumbs()
        # Open album window
        self.open_album_window(album_name)

    def open_album_window(self, album_name):
        if album_name in self.album_windows:
            try:
                self.album_windows[album_name].lift()
                return
            except Exception:
                pass
        win = tk.Toplevel(self.root)
        win.title(f"Album: {album_name}")
        win.geometry("900x600")
        win.configure(bg="#f7f7fa")
        
        # Add breadcrumbs to album window
        album_breadcrumbs = tk.Frame(win, bg="#f7f7fa")
        album_breadcrumbs.pack(side="top", fill="x", padx=20, pady=(10, 0))
        
        # Homepage link
        home_link = tk.Label(album_breadcrumbs, text="Homepage", font=("Segoe UI", 12, "bold"), fg="#4a90e2", cursor="hand2")
        home_link.pack(side="left")
        home_link.bind("<Button-1>", lambda e: self.go_home())
        
        # Separator
        separator1 = tk.Label(album_breadcrumbs, text=" / ", font=("Segoe UI", 12), fg="#666666")
        separator1.pack(side="left")
        
        # Albums link
        albums_link = tk.Label(album_breadcrumbs, text="Albums", font=("Segoe UI", 12, "bold"), fg="#4a90e2", cursor="hand2")
        albums_link.pack(side="left")
        albums_link.bind("<Button-1>", lambda e: self.go_to_albums())
        
        # Separator
        separator2 = tk.Label(album_breadcrumbs, text=" / ", font=("Segoe UI", 12), fg="#666666")
        separator2.pack(side="left")
        
        # Current album
        current_album = tk.Label(album_breadcrumbs, text=album_name, font=("Segoe UI", 12), fg="#666666")
        current_album.pack(side="left")
        
        canvas = tk.Canvas(win, bg="#f7f7fa", highlightthickness=0)
        scrollbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        inner = tk.Frame(canvas, bg="#f7f7fa")
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        # Enable mousewheel scrolling for album window
        canvas.bind_all("<MouseWheel>", lambda event: canvas.yview_scroll(-1 if event.delta > 0 else 1, "units"))
        canvas.bind_all("<Button-4>", lambda event: canvas.yview_scroll(-1, "units"))
        canvas.bind_all("<Button-5>", lambda event: canvas.yview_scroll(1, "units"))

        items = self.albums.get(album_name, [])

        # Responsive grid layout for album window
        thumb_size = (120, 120)
        thumb_padx = 24
        thumb_pady = 32
        title_font = ("Segoe UI Semibold", 10)
        title_wraplength = thumb_size[0]
        title_justify = "left"
        LEFT_MARGIN = 20
        RIGHT_MARGIN = 20

        def get_title_height(title, font, wraplength):
            temp = tk.Label(inner, text=title, font=font, wraplength=wraplength, justify=title_justify)
            temp.update_idletasks()
            h = temp.winfo_reqheight()
            temp.destroy()
            return h

        def get_max_cols():
            try:
                width = canvas.winfo_width()
                if width <= 1:
                    width = win.winfo_width()
                usable_width = max(width - LEFT_MARGIN - RIGHT_MARGIN, 300)
                per_thumb = thumb_size[0] + thumb_padx
                max_cols = max(1, usable_width // per_thumb)
                return max_cols
            except Exception:
                return 6

        max_cols = get_max_cols()
        idx = 0
        grid = []
        while idx < len(items):
            row_items = items[idx:idx+max_cols]
            row_titles = [
                (item.title if item.title else os.path.splitext(item.file_name)[0])
                for item in row_items
            ]
            row_title_heights = [
                get_title_height(title, title_font, title_wraplength)
                for title in row_titles
            ]
            max_title_height = max(row_title_heights) if row_title_heights else 0
            grid.append((row_items, max_title_height))
            idx += max_cols

        row = 0
        for row_items, max_title_height in grid:
            for col, item in enumerate(row_items):
                if col == 0:
                    padx = (LEFT_MARGIN+10, thumb_padx//2)
                elif col == len(row_items) - 1:
                    padx = (thumb_padx//2, RIGHT_MARGIN)
                else:
                    padx = (thumb_padx//2, thumb_padx//2)
                frame = tk.Frame(inner, bg="#f7f7fa", bd=0, width=thumb_size[0], height=thumb_size[1]+max_title_height)
                frame.grid(row=row, column=col, padx=padx, pady=thumb_pady//2, sticky="nw")
                frame.grid_propagate(False)
                # Shadow (soft, not harsh)
                shadow_canvas = tk.Canvas(frame, width=thumb_size[0], height=thumb_size[1], bg="#f7f7fa", highlightthickness=0, bd=0)
                shadow_canvas.place(x=0, y=0)
                shadow_canvas.create_oval(4, 4, thumb_size[0]-4, thumb_size[1]-4, fill="#e3e6ee", outline="", width=0)
                thumb = self.get_thumbnail(item.image_path, size=thumb_size)
                thumb_label = tk.Label(frame, image=thumb, bg="#f7f7fa", bd=0, relief="flat", cursor="hand2")
                thumb_label.image = thumb
                thumb_label.place(x=0, y=0, width=thumb_size[0], height=thumb_size[1])
                title = item.title if item.title else os.path.splitext(item.file_name)[0]
                title_label = tk.Label(
                    frame,
                    text=title,
                    font=title_font,
                    bg="#f7f7fa",
                    anchor="w",
                    justify=title_justify,
                    wraplength=title_wraplength
                )
                title_label.place(x=0, y=thumb_size[1], width=thumb_size[0], height=max_title_height)
                thumb_label.bind("<Button-1>", lambda e, i=item: self.open_screenshot_detail(i))
            row += 1
        self.album_windows[album_name] = win

    def go_to_albums(self):
        """Navigate to Albums filter"""
        self.search_type_var.set("Albums")
        self.current_path = ["Homepage", "Albums"]
        self.update_breadcrumbs()
        self.update_main_page()

    def _on_search_focus_out(self, event):
        """Hide suggestions when search entry loses focus."""
        self.suggestion_box.place_forget()

    def _on_root_click(self, event):
        """Hide suggestions when clicking outside the search bar."""
        # Check if click is outside the search area
        search_x = self.search_entry.winfo_rootx()
        search_y = self.search_entry.winfo_rooty()
        search_w = self.search_entry.winfo_width()
        search_h = self.search_entry.winfo_height()
        
        # Check if click is outside search entry and suggestion box
        if (event.x_root < search_x or event.x_root > search_x + search_w or 
            event.y_root < search_y or event.y_root > search_y + search_h + 150):  # 150px for suggestion box
            self.suggestion_box.place_forget()

    def go_home(self):
        self.current_path = ["Homepage"]
        self.update_breadcrumbs()
        self.update_main_page()

    def update_breadcrumbs(self):
        self.breadcrumbs_frame.destroy() # Clear previous breadcrumbs
        self.breadcrumbs_frame = tk.Frame(self.root, bg="#f7f7fa")
        self.breadcrumbs_frame.pack(side="top", fill="x", padx=20, pady=(5, 0))
        for i, folder in enumerate(self.current_path):
            if i == 0:
                # Homepage is always the first breadcrumb
                label = tk.Label(self.breadcrumbs_frame, text=folder, font=("Segoe UI", 12, "bold"), fg="#4a90e2", cursor="hand2")
                label.bind("<Button-1>", lambda e: self.go_home())
            else:
                label = tk.Label(self.breadcrumbs_frame, text=f"/ {folder}", font=("Segoe UI", 12), fg="#666666")
            label.pack(side="left", padx=(5, 5))

# === Main ===
def main():
    root = tk.Tk()
    style = ttk.Style(root)
    style.theme_use("clam")
    app = SnaptureGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
