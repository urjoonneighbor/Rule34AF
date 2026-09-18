[🇷🇺 Читать на русском](doc/CHANGELOG_ru.md)

# Changelog

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
- Support for multiple APIs: `Rule34.xxx`, `AllTheFallen.moe`,
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
