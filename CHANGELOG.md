[🇷🇺 Читать на русском](doc/CHANGELOG_ru.md)

# Changelog

## 1.2

### AI analytics

- Added a **built-in local AI model** (Qwen2.5 0.5B Instruct) as a new
  provider in the AI analysis tab. Unlike Ollama/LM Studio it needs no
  separate program running, and unlike the cloud APIs it needs no API key
  - it runs entirely offline, inside the app itself. The model file
  (~490 MB) downloads automatically the first time you use it and is then
  reused for every later analysis in that (and future) sessions.
- The built-in model asks two separate, single-purpose questions (style
  description, then similar artists) instead of one combined prompt with
  both parts at once. A model this small tends to get stuck elaborating on
  the first part of a multi-part instruction and never reach the second -
  splitting it in two makes it noticeably more likely to actually answer
  both. Only the built-in model works this way; the larger cloud/Ollama/LM
  Studio providers handle the combined prompt fine.
- Distributed builds (the .exe/.app/binary from GitHub Releases) include
  everything needed for the built-in model out of the box. Running from
  source requires the optional `local-ai` extra
  (`pip install ".[local-ai]" --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu`)
  - see the README.
- Fixed: the analysis used the wrong artist list. It read an internal,
  session-only set that's only filled while actually downloading something
  in that same run and is never saved between launches - so even with
  dozens of artists rated "good" in the History tab from earlier sessions,
  clicking "Run" without downloading anything first saw an empty list and
  did nothing, with no explanation. It now correctly uses your "good"-rated
  artists from the History tab, like the tab's own hint always said it
  would.
- Fixed: clicking "Run" with a genuinely empty "good" history, or with a
  cloud provider selected but no API key entered, silently did nothing - no
  error, no feedback, as if the button wasn't working. Both cases now show
  a clear message in the results box instead.
- Fixed: the analysis worker thread read the model-name field directly
  from a background thread, which isn't safe with Tkinter and could
  occasionally kill that thread with no visible error (especially in the
  windowed .exe build, which has no console to show it) - leaving the
  "Sending request..." message on screen forever. It's now read on the
  main thread before the background work starts, matching how the rest of
  the app already handles this.
- Fixed: the chosen AI provider, its model and its API key were never
  saved - every restart silently reset the tab back to "Ollama (Локально)"
  regardless of what you'd picked last time, which could make "Run" try to
  reach Ollama (and fail with a connection error) even after switching to
  a different provider, including the built-in model, in an earlier
  session. All three are now remembered between launches, the same way the
  rest of the app's settings already are (the API key goes into the same
  encrypted credentials file as your Booru site keys, not the plain
  settings file).
- **"Similar artists" is no longer guessed by the AI model - it's found by
  actually searching the site.** No LLM, however large, has live internet
  access from this offline app, so asking it "who draws like this obscure
  booru username" was an unanswerable question: it either invented
  specific-sounding facts about artists it has no real knowledge of, or
  simply echoed back the same names it was given as "similar". Now the app
  builds a "taste profile" from the real, actual content tags of your
  "good"-rated artists (themes, species, kinks - not usernames), searches
  the site for other artists who draw under those same tags using the same
  mechanism as a normal search, and ranks them by post count - a
  deterministic list of real artists you don't already know, not
  invented, and not a repeat of your input. The AI model's only remaining
  job is to describe, in a few sentences, the shared style or theme those
  real tags suggest - it's explicitly told not to name any specific
  artists, for every provider (built-in, Ollama, LM Studio, Gemini,
  OpenAI, Qwen).

### Local gallery

- Fixed: the gallery only remembered which *page* you'd stopped on for each
  artist (an internal, per-artist mapping) - but never which artist was
  actually open. After restarting the app, the artist list came up with
  nothing selected, so there was nothing to apply that saved page to - from
  the outside this looked exactly like "my page isn't being remembered" at
  all. The app now also remembers which artist was open and re-selects it
  automatically on startup, landing you right back on the same page without
  having to click the artist again.
- Fixed: that saved position only actually reached disk when the app was
  closed normally through its own close button - a hard shutdown, a crash,
  or the PC just losing power meant `on_closing()` never ran, so the last
  save on disk could be from several page turns (or artists) ago. The
  gallery now saves its position as soon as it changes (page turn, artist
  switch), not only on a clean exit.
- The photo you last opened in the viewer is now highlighted in the grid:
  its thumbnail gets a border in the current theme's accent color and a
  "👁 Last viewed" label. It's remembered separately for each artist and
  survives restarts, so when you come back to an artist (or reopen the
  app) you can see at a glance where you stopped - and if that photo is on
  the restored page, the grid scrolls to it automatically. The mark is
  saved about a second after you flip to another photo in the viewer and
  immediately when you close the viewer, so it isn't lost even if the PC
  shuts down mid-browsing.

### History

- Fixed: rating an artist (good/neutral/bad) rebuilt the whole history tree
  from scratch, which dropped the current selection, re-collapsed any
  folder you'd manually expanded, and reset the scroll position - so
  rating an artist felt like it threw you back to the top of the list
  every time. The tree now keeps your selection, your folders' open/closed
  state, and your scroll position across a rating change (and across
  filtering, moving artists between folders, etc).
- Rating an artist now takes them out of the search folder they were
  found in (the "🔍 ..." folders): rated artists are listed in the rating
  groups at the top, and a search folder keeps only the artists that
  still need a rating. A search folder whose artists are all rated hides
  itself, and clearing a rating puts the artist back into its search
  folder. Folders you created yourself are not affected - they keep
  showing everyone you moved there.
- Deleting a search folder now deletes only the artists it shows (the
  unrated ones). Rated artists from it stay in the history.
- Fixed: running the same search again replaced its folder with just the
  newly found artists, so everyone found by the earlier run disappeared
  from the History tab - rated artists vanished from the rating groups
  too. New artists are now added to the existing folder.

### Interface

- The app icon now shows up in every app window, including the gallery
  viewer, which used to show the default Tk icon. On Windows the app also
  registers its own taskbar identity, so the taskbar button uses the app
  icon instead of Python's when running from source. The icon is cropped
  to a square and pre-scaled, so it no longer looks squashed at small
  sizes.

### Diagnostics

- The internal `app.log` file now rotates by day instead of by size. It
  used to cap out at 1 MB with 2 backups (3 MB total) and simply overwrite
  the oldest one once full - so a single busy day could silently wipe out
  an earlier day's log you actually wanted to look back at. Now each day
  gets its own file (`app.log.YYYY-MM-DD`), and the last 14 days are kept;
  older ones are deleted automatically.

## 1.1

### Search

- Fixed: if filters like "exclude AI" or "exclude questionable" (or any
  saved tags) were already active from a previous session, the "final
  query" preview box stayed empty right after startup until you touched a
  filter yourself. It's now filled in correctly as soon as the window
  opens.

### Downloading

- **An interrupted download is no longer lost.** The queue is saved to
  disk (`download_queue.dat` in the app's data folder), and on the next
  launch the app offers to continue where it left off. This includes the
  task that was actively downloading at the moment the app closed, not
  just what was still waiting in the queue.
- Closing the app while a download is in progress now shows a warning
  with the number of remaining files - previously the window just closed
  and anything not yet downloaded was silently lost.
- Fixed: when a saved download queue was resumed on startup, the UI
  controls (inputs, buttons, checkboxes) stayed editable the whole time
  instead of being locked like during a normal download.
- Files already downloaded are skipped on the next run (and when
  re-downloading the same artist). If the site reports an MD5, the file
  on disk is also checked against it and re-downloaded if it doesn't
  match.
- Files are downloaded to a temporary `.part` file and only renamed once
  the download is complete. Previously, an interrupted download left a
  truncated file under its final name, and it was forever considered
  "already downloaded".
- Manually stopping a download still works as before: the queue is
  discarded, there's nothing left to resume.

### Local gallery

- Added a **"Solo works only"** filter: hides files that, besides the
  current artist, are tagged with another known artist (collaborations).
  Known artists are determined entirely locally - from gallery folders,
  search history, and artist ratings - without a single request to the
  site. Files whose tags haven't been fetched yet are left untouched by
  the filter. The toggle's state is remembered between launches.
- The "Solo works only" checkbox is only enabled when the gallery search
  box contains a tag matching a known artist - without that there's
  nothing to filter collaborations against, so the toggle stays disabled
  (and switches itself off if it was on).
- Fixed: with an artist tag typed into the search box, "Solo works only"
  used to hide every matching file, since a match by definition has that
  other artist's tag. It now only filters out a *third* artist beyond the
  one(s) you searched for - so searching for one artist plus "solo only"
  shows exact pairs with the current artist, and searching for several
  artist tags at once shows exactly that group, with no extra
  collaborator.
- Fixed: adding or changing a filter tag in the gallery search box no
  longer jumps you back to page 1 - you stay on the current page, just
  with the filter applied (clamped to the new, possibly smaller, page
  count).

### Viewer

- The image-copied confirmation is now shown as an overlay on top of the
  image itself, instead of in the window title bar - the title bar isn't
  visible in fullscreen, so copying looked like "nothing happened".
- If the clipboard is briefly held by another app (clipboard managers,
  Windows clipboard history), copying no longer fails silently: it
  retries a few times, and the reason for a failure is written to the
  log. It also now checks the actual result of `SetClipboardData`
  (previously success was reported even when the system rejected it) and
  frees the allocated memory on failure.
- After switching to fullscreen, the window now forcibly reclaims
  keyboard focus - without this, arrow keys, Escape and Ctrl+C stopped
  working.
- Ctrl+C on a video no longer does nothing silently - it now tells you
  there's nothing to copy.
- On multi-monitor systems, F11 now expands the viewer on whichever
  monitor the window currently sits on, instead of always the primary
  one.

## 1.0

First public release.

### Features

- Smart artist search: scans posts under given tags and finds the
  artists who draw in that genre most often.
- Support for multiple APIs: `Rule34.xxx`, `allthefallen.moe`,
  `Rule34.paheal.net`.
- Search filters: exclude AI-generated content, exclude "questionable"
  rating, limits on download count and an artist's minimum post count.
- Multi-threaded background downloading of original images with a queue
  - you can keep using the app and adding new artists while a download is
  running.
- The site an artist was found on is remembered for each result -
  downloading and fetching tags from history automatically use that
  saved site, regardless of what's currently selected in the interface.
  Filtering out "already known" artists during search also takes the
  site into account: the same tag on different sites isn't treated as a
  repeat find.
- An artist rating system (👍/👌/👎) and blacklists - "bad" artists can be
  automatically skipped during downloads or permanently hidden from
  future searches.
- History has a "Site" column with a show/hide toggle on the toolbar and
  a context-menu option to manually set the site on older entries.
- AI analytics: local models via Ollama and cloud ones (Gemini/OpenAI)
  for analyzing search history and suggesting new tags.
- Credentials (API keys, User ID) are encrypted and stored in the OS's
  secure credential store (Windows Credential Manager / macOS Keychain /
  Secret Service on Linux).
- A local gallery with a fullscreen viewer: zoom with the mouse wheel
  "from the cursor", smooth background resizing, panning, copying an
  image to the clipboard, and switching the viewer to true fullscreen
  with **F11** (Escape exits fullscreen first, then closes the viewer on
  a second press).
- Automatic update checks via GitHub Releases - it never downloads
  anything on its own, it just offers to open the release page.
- Configurable thread counts and an HTTP(S) proxy for Booru API requests
  (the "Network and performance" section).
