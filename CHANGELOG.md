# Changelog

All notable changes to Opal are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[semantic versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Exhaustive verification suite (`tests/test_every_feature.py`, 165 checks) that
  runs every catalogue action against real files and re-opens each output.
- A security suite (`tests/test_security.py`, 24 checks) that proves the
  guarantees the app makes: a hostile archive cannot write outside the folder
  it is unpacked into, the downloader refuses anything that is not a model,
  and the network layer only reaches allow-listed hosts.
- Cross-platform input watcher (`opal_studio/input_watch.py`) with Win32,
  CoreGraphics and X11 backends.

### Fixed
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
