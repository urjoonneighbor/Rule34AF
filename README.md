[🇷🇺 Читать на русском](doc/README_ru.md)

---

# Rule34 Artist Finder 🎨🔍

A multi-threaded desktop application in Python (Tkinter) for smart search, analysis, and mass downloading of art from Booru platforms.

> [!IMPORTANT]
> Most booru tools (imgbrd-grabber, DanbooruDownloader, etc.) are built around one thing: download by tag. This one asks a different question — **which artists actually draw the most under a given tag** — and once you've found them, lets you queue them up and download their stuff in bulk. It's not trying to replace the big multi-site downloaders (they cover way more sites); this is specifically for artist discovery.

## 🌟 Key Features

* **Smart Artist Search**: Scans thousands of posts using your tags and finds the artists who draw most frequently in that specific genre.
* **Multiple API Support**: Works seamlessly with `Rule34.xxx`, `AllTheFallen.moe`, and `Rule34.paheal.net`.
* **Advanced Filters**:
  * Exclude AI-generated content (`ai_generated`).
  * Exclude `Questionable` rating.
  * Set limits for download counts and minimum required posts per artist.
* **Multi-threaded Downloading (Queue)**: Downloads original, full-resolution images using several background threads (configurable in the "Network & Performance" section — see below). You can continue browsing and adding new artists to the queue on the fly.
* **Rating System & Blacklists**: Rate artists (👍 Excellent / 👌 Average / 👎 Bad). "Bad" artists can be automatically skipped during mass downloads or permanently hidden from future searches.
* **AI Analytics**: Built-in support for local LLMs (via Ollama) and cloud models (Gemini / OpenAI) to analyze your search history and suggest relevant, fresh tags.
* **Encrypted credential storage**: Site API keys / User IDs are stored separately from the rest of the settings and, when the optional `keyring` and `cryptography` packages are installed, are genuinely *encrypted* using a per-machine key kept in your OS's secure credential store (Windows Credential Manager / macOS Keychain / Linux Secret Service). Without those packages installed, credentials fall back to plain base64 encoding (not real protection) and a warning is written to the log — see "Optional dependencies" below. Earlier versions described this as "secure storage" while only doing base64+zlib encoding, which is not actually secure; that has been corrected here both in code and in this description.
* **Automatic update check**: On startup, the app optionally checks GitHub Releases in the background (toggle in Settings) and, if a newer version exists, offers to open its release page. It never downloads or replaces the running executable itself.
* **Smoother zoom**: The image viewer zooms towards the mouse cursor (not just the canvas center) with an instant low-cost preview per scroll tick and a debounced high-quality resize computed off the UI thread, so large images no longer feel "jerky" while zooming.

## 📂 Project Structure

```text
rule34_project/
├── main.py                     # Application entry point
├── README.md                   # English documentation
├── doc/README_ru.md            # Russian documentation
├── CHANGELOG.md                 # Version history
├── doc/CHANGELOG_ru.md          # Version history (Russian)
├── requirements.txt             # Python dependencies
├── assets/
│   └── 1.png                   # Application icon
└── src/
    ├── __init__.py
    ├── app.py                  # Main business logic and thread management
    ├── core/
    │   ├── api.py               # Booru API interactions (GET/HEAD requests)
    │   ├── ai.py                 # LLM integration (Ollama, OpenAI, Gemini)
    │   ├── config.py             # Settings load/save (+ credential migration)
    │   ├── downloader.py         # Download queue / worker threads
    │   ├── search_engine.py      # Artist-search worker
    │   ├── secure_store.py       # Credential encryption (keyring + Fernet)
    │   ├── paths.py              # Cross-platform app-data directory resolution
    │   ├── applog.py             # File logging (app.log in the app-data dir)
    │   ├── media_types.py        # Shared list of allowed file extensions
    │   ├── updater.py            # Background GitHub Releases update check
    │   └── version.py            # App version / repo constants
    └── ui/
        ├── gui.py                 # Interface rendering (Tkinter UI)
        ├── gallery.py             # Local gallery + image/video viewer
        └── locales.py             # Localization (RU / EN)
```

## 🛠 Installation & Run (For Developers)

1. Ensure you have **Python 3.8+** installed.
2. Clone the repository and install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the application:
   ```bash
   python main.py
   ```

### Optional dependencies (encrypted credential storage)

`requirements.txt` includes `keyring` and `cryptography` as they are needed for real encryption of your API keys/User IDs (see "Encrypted credential storage" above). If, for some reason, you don't want them installed, the app still works — it just falls back to the old base64 encoding for credentials and logs a warning that this is not real protection.

## 📁 Where your data is stored

Settings, credentials, search history and logs are no longer written next to the executable / current working directory (which could fail silently when installed under `Program Files`, or leave data scattered depending on how the app was launched). They now live in a standard per-user app-data directory:

* Windows: `%APPDATA%\Rule34ArtistFinder`
* macOS: `~/Library/Application Support/Rule34ArtistFinder`
* Linux: `$XDG_DATA_HOME/Rule34ArtistFinder` (usually `~/.local/share/Rule34ArtistFinder`)

If you're upgrading from an older version, any existing `r34_settings.dat`/`found_artists.dat`/etc. found next to the app are moved there automatically on first run — nothing is lost.

## 📦 Building Standalone .exe (Windows)

The project is configured to be compiled into a single executable file using `PyInstaller`. All resources (like icons) will be embedded inside the application.

Run the following command in the root directory:
```bash
pyinstaller --noconsole --onefile --add-data "assets/1.png;assets" main.py
```
The compiled `main.exe` will appear in the `dist/` folder.

## 🍏 Running on macOS

### From source

If your Python came from **Homebrew**, Tkinter is a separate package and isn't installed by default (the official python.org installer already bundles it):
```bash
brew install python-tk@3.11
```
Then run the app as usual:
```bash
python3 main.py
```

### Running the pre-built app (from Releases)

The macOS build (`Rule34_Artist_Finder-macOS.zip` on the Releases page) isn't signed with an Apple Developer ID, so **Gatekeeper will block the first launch** with a message like "Apple could not verify that this app is free of malware" or "...is from an unidentified developer". This is expected for an unsigned app and is safe to bypass:

1. Unzip the archive to get `Rule34_Artist_Finder.app`.
2. **Right-click** (or Control-click) the app → **Open** → confirm **Open** in the dialog. (A normal double-click just repeats the warning with no way to proceed.)
3. If macOS instead says the app **"is damaged and can't be opened"** (a stricter Gatekeeper message on newer macOS versions), clear the quarantine flag in Terminal:
   ```bash
   xattr -cr /path/to/Rule34_Artist_Finder.app
   ```
   then try step 2 again.
4. You only need to do this once — after the first successful launch, macOS remembers your choice.

## ⚙️ API Keys Management
To bypass server rate limits, it is highly recommended to use API keys.
Go to the **"Connection & Auth"** tab to enter your `User ID` and `API Key` for the selected site. Settings are applied instantly and safely saved upon exit (see "Encrypted credential storage" above for how they're protected on disk).

## 🌐 Network & Performance settings

The "Network & Performance" section (below the download filters) lets you configure:

* how many parallel threads are used for downloading files, checking file sizes, and checking tags during artist search (previously hardcoded to 8/32/4);
* an optional HTTP(S) proxy for all Booru API requests (useful behind a corporate proxy). Note: this currently applies to Booru API traffic only, not to the AI-provider requests in the AI Analytics tab.