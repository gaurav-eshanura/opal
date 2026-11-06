# Changelog

All notable changes to Opal are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[semantic versioning](https://semver.org/spec/v2.0.0.html).

## [2.2.0] — 2026-11-06

### Added
- **The Stitch Liquid Glass rebuild**: every screen, asset and the wheel
  rebuilt on the Stitch "Opal Liquid Glass" design system (project
  `3961317633702086904`, captured in `design/stitch/DESIGN.md`). Tokens,
  glass recipes and geometry are now canonical: the radial wheel matches the
  Stitch overlay exactly (R_out 246 · R_in 92, 184 px hub, rose→violet active
  wedge with 2 px white stroke, "Release key to select" hub hint), the
  dashboard's features became Stitch cards ("Core Instant Pipelines" with
  fire-spectrum ticks and mono meta footers), and the floating studio's field
  is the Stitch radial aurora (violet 18 % top-left, rose 8 % bottom-right)
  under a navy veil. Wheel demo GIF regenerated from the real widget.

### Fixed
- **Every label drew its own box.** Qt's default `QLabel` carries a border
  once the app stylesheet is applied, so helper labels rendered inside a
  border — including a giant white band across the Floating Studio home
  grid. The global rule is now `background: transparent; border: none` on
  `QLabel`, and the home scroll viewport is transparent with its horizontal
  scrollbar removed.

### Verified
- 390 passed / 15 skipped offscreen; 36-screen capture rig green;
  wheel, dashboard and FloatStudio home re-rendered and checked.

## [2.1.0] — 2026-11-04

### Added
- **Sign PDFs with a plugged-in DSC USB token** (PKCS#11): Opal finds the
  token's driver itself, shows certificate subject/issuer/serial/validity
  before signing, computes the signature inside the token (the private key
  never leaves the device), signs into the form's own prepared signature
  field, writes a signed copy only, and verifies any signed PDF offline —
  intact / trusted / revoked. `.pfx`/`.p12` files work too, plus an optional
  allow-listed RFC 3161 timestamp (`--tsa`, hash only). Live-proven with a
  real e-Mudhra HYP2003 token.
- **World-class redesign**: radial liquid-glass field, type ladder, segmented
  PDF studio (File/Organize/Annotate/Convert), icon-tile cards, a 500 px
  radial wheel with paging and arc-fitted labels, SVG icons everywhere,
  scrollable image-lab rail, glass toasts, 24 px dialog rhythm. Verified with
  a 36-screen capture rig and a pixel/margin audit.
- **Website**: full uses menu, DSC-signing section marketed against paid
  Acrobat, honest vs-rivals scoreboard (`compare.html`), EN + Hinglish,
  JSON-LD/sitemap/robots SEO, printable bilingual CSC rate card, press kit,
  `MARKETING.md` launch plan.

### Changed
- The wheel pages at 10 wedges with a More/First wedge — all 103 action ids
  stay reachable; labels elide to their wedge's arc width.

### Fixed
- Document viewer search crashed on a no-match (`QTextDocument.find` cursor
  misuse); regression-tested.

## [Unreleased]

### Added
- **A real test suite.** The verification suite is now pytest, and it can fail.
  `tests/conftest.py` provides the Qt application fixture the old scripts
  never had, `tests/opal_fixtures.py` builds 28 real sample files on the test
  machine (anything that cannot be built is recorded as missing *with the
  reason*, never faked), and `tests/opal_artifacts.py` re-opens every produced
  file with the matching reader — so a "successful" conversion that produced a
  file nothing can open counts as a failure.
- **Contracts for the two surfaces that matter most.**
  `tests/test_menu_contract.py` runs every wheel entry against the file
  types it applies to (298 cases), and `tests/test_catalog_contract.py`
  covers all 38 catalog actions plus the guards around them.
- **The watch folder is tested end to end.** `tests/test_watch_folder.py`
  drops a file into a watched folder and waits for the conversion, the
  `Output/` file and the `Originals/` move.
- **Office runs in a child process.** `opal_studio/office_worker.py` keeps
  Word and Excel out of Opal's own process, so a misbehaving Office can fail
  its own conversion instead of taking the application down with it.
- `opal_studio/version.py` — one place for the version number. The About box,
  the release archive name and the website footer all read it from here.
- The build now produces the release archive people download and stages it
  into `website/downloads/`, so the download button on the site has a real
  file behind it.
- `website/firebase.json` and `website/.firebaserc` — hosting config for the
  site, separate from the other project that shares this repository.
- **The command line takes a whole folder.** `--convert scans/ --to pdf` runs
  every supported file in the directory (`--recursive` includes subfolders,
  files already in the target format and files inside `--out` are skipped so a
  run cannot feed on its own results), and `--json` prints one machine-readable
  summary for scripts. Covered by `tests/test_cli_batch.py`.
- **The eight OS-level wheel actions are tested for real.**
  `tests/test_os_actions.py` covers copy-to-Downloads, copy path, duplicate,
  show in folder, terminal, open-with, float and recycle bin. Where an action
  would launch Explorer or a terminal on the test machine, the platform layer
  is replaced with a recorder and the test proves the engine called it with the
  right path; the real launches stay in the `OPAL_RUN_DESKTOP` group.
- **Batch jobs run through a visible queue.** One conversion batch runs at a
  time and the rest wait in FIFO order; the dashboard header pill shows
  "Working · N queued" while jobs wait, and every queued job reports its result
  when it finishes. `tests/test_action_queue.py` covers the ordering, the
  failure path and the pill.
- **Plugin API.** Drop a `.py` file into the plugins folder (next to the app in
  portable mode, otherwise the Opal data folder; `OPAL_PLUGINS_DIR` overrides)
  and its tool joins the wheel's tools mode as `plugin:<id>`. A plugin that
  fails to import, lacks metadata, or raises while running is skipped with a
  reason and never crashes the app. `tests/test_plugins.py`.
- **Sign with a plugged-in DSC USB token, not just a .pfx file.** PDF Studio's
  "Sign with DSC" now offers *USB token* alongside the certificate file: Opal
  finds the token's PKCS#11 driver automatically (or via `OPAL_PKCS11_LIB`),
  lists the tokens and the certificates on them, shows the certificate details
  for confirmation, and computes the signature **inside the token** — the
  private key never leaves the device, exactly like Adobe Acrobat. The PIN is
  asked for in a dialog and held in memory only; it is never saved, logged, or
  put on a command line. Verified live against a Hypersecu HYP2003 token with
  an e-Mudhra Class 3 certificate: the signature lands in the form's prepared
  empty signature field and validates as intact **and** trusted.
  `opal_studio/dsc_token.py` + `python-pkcs11`.
- **The command line can sign too.** `Opal --sign contract.pdf --token` signs
  with the plugged-in token (PIN from `OPAL_DSC_PIN` or an interactive prompt),
  `Opal --sign contract.pdf --pfx cert.pfx` with a certificate file; `--out`,
  `--page`, `--reason`, `--rect`, `--json` are supported and the result is
  verified after signing. Covered by `tests/test_dsc_token.py`.
- **Signing fills a prepared signature field when the form has one** — forms
  like INC-33 ship an empty signature field and Acrobat signs into it; Opal now
  does the same (`pdf_tools.find_empty_sig_field`), instead of adding a second
  field. `tests/test_parity.py`.
- **Verify Signatures** — a new wheel action, `Opal --verify-signature file.pdf`
  and the result dialog after signing all run pyHanko's cryptographic validation
  and report per signature: intact (bytes unmodified and covered), signer
  certificate, chain trust, revocation. Fully offline (no AIA/CRL/OCSP
  fetching). `tests/test_parity.py`.
- **Search & Redact** — `pdf_search_redact` with `--options '{"query": "..."}'`
  blacks out every occurrence of the text on every page, like Acrobat's
  "Search and Redact". `tests/test_parity.py`.
- **Optional RFC 3161 timestamp** — `--tsa https://freetsa.org/tsr` (or the
  engine option `tsa_url`) embeds a timestamp token in the signature, so it
  still validates after the certificate expires. Off by default (signing stays
  100% offline); only allow-listed TSA hosts are contacted and a TSA receives
  just the signature hash, never the document. `tests/test_parity.py`.

### Fixed
- **The Home grid did nothing.** The 38 tiles were wired to a signal whose
  arguments were in the wrong order, so every click fell through to a dead
  handler.
- **The radial wheel offered actions with no handler.** Several entries
  pointed at menu ids that no route matched; each now points at an id that
  exists.
- **Flattening a PDF only hid the form fields.** The page content was still
  underneath. Flatten now draws the real page and drops the interactive layer.
- **Auto-crop cut a fixed border** instead of finding the content box.
- **The palette tool crashed on a flat-colour image**, whose palette is
  empty.
- **Media compression wrote MP3 bytes into a `.wav` file.** The output is now
  named `.mp3`.
- **"Burn Subtitles" was offered when there were no subtitles.** The entry now
  appears only when a matching `.srt` / `.vtt` really sits next to the video.
- **The Linux and macOS build scripts pointed at `Tangerine.spec`**, trimmed
  the wrong Qt libraries for their platform, and the Linux build never
  bundled FFmpeg.
- The old print-only suites could not fail a build: a failed check was only
  a printed line, and a skipped check counted as a pass. They now run under
  pytest, where a failed check is a failed test and a skip is reported as a
  skip.
- **Burning subtitles no longer depends on ffmpeg having libass.** Plenty of
  ffmpeg builds (the one Homebrew ships, for one) do not, so the feature
  simply failed there. The subtitle text is now drawn by Opal itself and
  ffmpeg is only asked to lay the pictures over the video. As a bonus,
  subtitles in Hindi and other Indic scripts now come out right.
- **Archive extraction could write outside the target folder.** A crafted tar
  with a member named `../../something` would have been written outside the
  folder the user chose. Every member is now checked before anything is
  written, on every supported Python version.
- The AI upscaler downloaded a 404 error page and cached it as the model, so
  every later upscale failed. The URL now points at a real model, the
  download is fingerprinted with a pinned SHA-256, and a corrupt cache
  removes itself.
- Media compression computed its bitrate from a hard-coded ten-second
  duration when FFprobe was not present.
- The command line printed a library deprecation notice before its JSON, so
  `--info` could not be parsed by a script.
- One unreadable page no longer aborts the whole OCR job.
- The Settings dialog crashed on open.
- The global stylesheet was being discarded because of one malformed
  gradient declaration.
- The customer-journey test no longer inherits the output folder from
  whatever the person running it has configured.
- **The watch folder converted files that were still being written.** It now
  waits for the size to settle first, retries a failed conversion on later
  scans, and after three attempts moves the file into `Failed/` and shows a
  failure toast instead of retrying forever or dropping it silently.
- **Starting a second action while one was running silently replaced it.**
  The first batch kept running invisibly, its result was never shown, and two
  batches at once fight over memory (the AI models are the heavy part).
  Actions now run one at a time from a FIFO queue and every result is
  reported. Covered by `tests/test_action_queue.py`.

### Changed
- The website and the README now quote the real numbers: 103 wheel actions,
  38 catalogue actions, 391 passing tests, 98 MB
  and 222 MB for the two zipped builds.
- A separate security suite (`tests/test_security.py`, 24 checks) proves the
  guarantees the app makes: a hostile archive cannot write outside the folder
  it is unpacked into, the downloader refuses anything that is not a model,
  and the network layer only reaches allow-listed hosts.
- Cross-platform input watcher (`opal_studio/input_watch.py`) with Win32,
  CoreGraphics and X11 backends.

## [2.0.0] — 2026-10-21

### Added
- The Opal mark, the liquid-glass design system and the whole brand.
- Floating Studio with four workspaces: Image Lab, PDF Studio, Media Studio
  and Documents.
- The modifier wheel: hold Shift, Alt or Ctrl while dragging a file.
- Full PDF editing, including real DSC signing with PKCS#12 certificates.
- On-device AI: eight background-removal models, Real-ESRGAN upscaling and
  offline OCR.
- DSC certificate inspection before signing, and a self-contained signature
  pad (draw, type, upload or use initials).
- Portable mode, driven by a `portable.txt` marker.
- Auto-save: results are written next to the original without a prompt.
- A marketing site with a full English and Hinglish edition.

### Changed
- The application is now built on a deep, inky field with panes of glass
  rather than a flat light theme.
- The data folder is now `%APPDATA%/Opal` (or the equivalent on macOS and
  Linux), with a one-time migration from the previous name.

## [1.0.0]

- First public release.
