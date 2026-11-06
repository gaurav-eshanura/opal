# Opal release notes

**Every file, in every light.**

---

## v2.2.0 — 2026-11-06

Every screen, asset and the wheel rebuilt on the Stitch "Opal Liquid Glass"
design system — the radial wheel now matches the Stitch overlay exactly
(R_out 246 · R_in 92, 184 px hub, rose→violet active wedge with 2 px white
stroke, "Release key to select" hub hint), the dashboard's features are
Stitch cards ("Core Instant Pipelines" with fire-spectrum ticks and mono
meta footers), the floating studio's field is the Stitch radial aurora
(violet 18 % top-left, rose 8 % bottom-right) under a navy veil, and the
canonical capture lives in `design/stitch/DESIGN.md`. Also fixed: every
label used to draw its own box (including a white band across the Floating
Studio home grid) — labels are borderless now. Wheel demo GIF regenerated
from the real widget.

- Tests: **390 passed / 15 skipped / 0 failed** (pytest, offscreen Qt, exit 0)
- Downloads: `Opal-v2.2.0-Windows-x64.zip` and
  `Opal-Full-v2.2.0-Windows-x64.zip` (AI engines bundled), sizes in the release
- Known gaps (roadmap, stated honestly on the site): MDP certification,
  LTV/DSS, preflight/PDF-X, JS actions; published zips are Windows-only
  (macOS/Linux build from source, CI green on all three); the exe is not
  code-signed yet.

---

## v2.1.0 — 2026-11-04

First release with **DSC USB token signing**: plug in an Indian CA's token
(live-proven with e-Mudhra HYP2003) or drop in the `.pfx`/`.p12` — the
signature is computed inside the token, the key never leaves it, the form's
own prepared signature field is used, a signed copy is written (original
untouched), and any signed PDF verifies fully offline (intact / trusted /
revoked; optional allow-listed `--tsa` timestamp, hash only).

Also in this release: the world-class UI redesign (liquid-glass field, type
ladder, segmented PDF studio, icon tiles, 500 px paged wheel with SVG icons,
scrollable rails, glass toasts — verified by a 36-screen capture rig and
pixel audit), wheel paging at 10 wedges (all 103 actions still reachable),
a viewer-search crash fix, and the rebuilt website (uses menu, DSC section,
honest vs-rivals scoreboard, EN+Hinglish, SEO, press kit, `MARKETING.md`).

- Tests: **390 passed / 15 skipped / 0 failed** (pytest, offscreen Qt, exit 0)
- Downloads: `Opal-v2.1.0-Windows-x64.zip` (103,554,634 B ≈ 99 MiB zipped) and
  `Opal-Full-v2.1.0-Windows-x64.zip` (233,087,187 B ≈ 222 MiB zipped, AI engines bundled)
- Known gaps (roadmap, stated honestly on the site): MDP certification,
  LTV/DSS, preflight/PDF-X, JS actions; published zips are Windows-only
  (macOS/Linux build from source, CI green on all three); the exe is not
  code-signed yet.

---

## Security audit — 2026-11-04

Deep static scan (Mimosa 0.1.0, `depth: deep`): **0 findings** (0 high / 0
medium / 0 low / 0 info), sealed artifacts under
`~/.mimosa/security-scans/project-c5d58624bebc2392dd718f46/`.

- Scan ID: `scan-2026-11-04T02-14-53.646Z-d7996a4f9c02`
- Seal: `sha256:1bc2645747d21dea50916053eacaa11371c21e5ced61ddaa3fa5401788ccbed3`
- Dependency check: 150 packages scanned; 3 matched 42 entries in the offline
  advisory DB (114 unknown); itemised names are not in the sealed artifacts.
- Caveat: static-only, partial call-graph coverage — run status
  **inconclusive**, not a claim of "fully secure".

---

## Unreleased

The work in this batch closed the gap between what Opal *says* it does and
what it *does*. Nothing here changes the look of the app; it changes whether
the app keeps its promises.

### Fixed

- **The Home grid did nothing.** The 38 tiles on the Home screen were wired to
  a signal whose arguments were in the wrong order, so every click fell
  through to a dead handler. All 38 now run their real action.
- **The radial wheel offered tools that had no handler.** Several entries in
  the Shift / Alt / Ctrl wheel pointed at menu ids that no route matched. Each
  one now points at an id that actually exists, so the wheel no longer opens a
  menu that does nothing when you pick from it.
- **Flattening a PDF only hid the form fields.** The page content was still
  there underneath. Flatten now draws the real page into a new document and
  drops the interactive layer entirely.
- **Auto-crop cut the wrong edges.** It cropped a fixed border instead of
  finding the actual content. It now detects the content box.
- **The palette tool crashed on a flat-colour image.** A one-colour image
  quantises to an empty palette, and the code assumed a palette was always
  there. The single colour is now used as the palette.
- **Media compression wrote MP3 bytes into a `.wav` file.** Audio is
  re-encoded to MP3, so the output is now named `.mp3` and opens as what it
  is.
- **"Burn Subtitles" was offered when there were no subtitles.** The entry now
  appears only when a matching `.srt` / `.vtt` really sits next to the video.
- **Office could take Opal down with it.** A misbehaving Word or Excel
  (an RPC abort, `0x800706be`) could abort the whole application. Word and
  Excel now run in a child process, so the worst they can do is fail their own
  conversion — the app stays up and falls back to the built-in converter.
- **The build scripts pointed at files that do not exist.** The Linux and
  macOS scripts built `Tangerine.spec` instead of `Opal.spec`, trimmed the
  wrong Qt libraries for their platform, and the Linux build never bundled
  FFmpeg at all.
- **The download button on the website pointed nowhere.** The build now
  produces the release archive *and* stages it where the site's link expects
  it, so the button has a real file behind it.

### The verification suite is real now

The old suite printed `[PASS]` and `[FAIL]` lines and ended with a summary —
but it never asserted anything. A failure could not fail a build, a skipped
check counted as a pass, and the "all features verified" report was a printer,
not a test.

It is now **pytest**, and it can fail:

- **Real sample files.** 28 samples are built on the test machine — photos,
  PDFs, scans, Office documents, an EPUB, a font, a certificate, video, audio,
  subtitles. Anything that cannot be built on that machine is recorded as
  missing *with the reason*, never faked.
- **Real artifacts.** Every output is re-opened with the matching reader and
  checked. A "successful" conversion that produced a file no reader can open
  counts as a failure.
- **Real assertions.** The menu contract is 298 cases (one per wheel entry per
  file type), the catalog contract covers all 38 catalog actions plus the
  guards around them, and the old print-only suites run as subprocesses where
  a failed check is a failed test.
- **Honest skips.** Slow AI upscaling and the desktop-only suites are reported
  as `SKIP` with the reason, never as passes.

The suite found four real product bugs on its first run — the palette crash,
the wrong audio extension, the subtitle entry with no subtitles, and the dead
Home grid. All four are fixed above.

### The numbers

| | File | Size |
|---|---|---|
| **Opal** | `Opal-v2.0.1-Windows-x64.zip` | 98 MB |
| **Opal Full** | `Opal-Full-v2.0.1-Windows-x64.zip` | 222 MB |

---

## 2.0.1

**Every file, in every light.**

A maintenance release with one security fix and a set of cross-platform fixes
that the new CI pipeline found. Everything else about Opal is unchanged.

---

## Download

| | File | Size |
|---|---|---|
| **Opal** | `Opal-v2.0.1-Windows-x64.zip` | 98 MB |
| **Opal Full** | `Opal-Full-v2.0.1-Windows-x64.zip` | 222 MB |

Unzip, run `Opal.exe`. No installer, no administrator rights.

---

## Security

**Archive extraction could write outside the folder you chose.** A crafted
`.tar` with a member named `../../something` would have been written outside
the destination folder. Every member is now checked against the target folder
before anything is written, on every supported Python version.

This was found by the new test suite, and it is the reason 2.0.1 exists.

## Fixed

- **The AI upscaler was permanently broken.** Its download address pointed at a
  file that does not exist, so the server returned an error page which was
  saved as the model — and every later upscale failed with a cryptic message.
  The address is now correct, the download is checked against a pinned
  fingerprint, and a bad file is deleted rather than cached.
- **Burning subtitles no longer depends on ffmpeg having libass.** Plenty of
  ffmpeg builds do not have it, so the feature simply failed there. Opal now
  draws the subtitle text itself and asks ffmpeg only to lay it over the
  video. Subtitles in Hindi and other Indic scripts now come out right too.
- **Media compression used the wrong duration** when ffprobe was not
  installed, so the bitrate was calculated from a made-up ten seconds.
- **The command line printed a library notice before its JSON**, so `--info`
  could not be parsed by a script.
- **One unreadable page aborted the whole OCR job** instead of costing only
  that page.
- **The Settings dialog crashed on open.**
- **The global stylesheet was being discarded** because of one malformed
  gradient, so the app was running without its theme.
- **Opal can now start at login on macOS**, with a Launch Agent in your own
  folder, the same way Linux gets a `.desktop` entry and Windows gets a
  registry key.

## The cross-platform work

The CI now runs the whole suite on **Windows, macOS and Linux**, on Python 3.11
and 3.12, and builds the portable app to make sure it does not grow past its
size budget.

Building it that way found problems that only appear on the platforms they
appear on — a font that only exists on Windows, a filter that only exists in
one ffmpeg build, a system font that macOS will not let you copy. All of them
are fixed.

---

## Source

**https://github.com/gaurav-eshanura/opal**

```bash
git clone https://github.com/gaurav-eshanura/opal.git
cd opal
pip install -r requirements.txt
python -m opal_studio
```

MIT licensed.

---

## 2.0.0 — the first public release

The release that introduced Opal to the world. Everything above it is
maintenance on top of this.

### Two builds

| | Download | What you get |
|---|---|---|
| **Opal** | `Opal-v2.0.0-Windows-x64.zip` | Every tool except the heavy AI engines, which install by themselves the first time you use them. |
| **Opal Full** | `Opal-Full-v2.0.0-Windows-x64.zip` | Everything bundled, including the cut-out model, so background removal works offline from the very first click. |

Unzip, run `Opal.exe`. There is no installer, no admin rights and no service.
Copy the folder to a USB stick and it works on the next machine too.

**Portable mode:** create a file called `portable.txt` beside the executable and
Opal keeps its settings, history and models inside the folder instead of your
user profile — nothing is left behind on a shared or counter PC.

### What was in it

- **A PDF editor, not a PDF viewer.** Annotate, redact, sign, build and fill
  forms, OCR a scan, compare two versions, flatten, protect, and export to
  Word, PowerPoint or EPUB.
- **Real digital signatures.** Sign with the PKCS#12 certificate (`.pfx` /
  `.p12`) your authority issued. Opal shows the subject, issuer, serial and
  validity *before* you sign, and the private key never leaves the machine.
- **AI that runs at the counter.** Eight background-removal models, Real-ESRGAN
  upscaling and offline OCR — all on your own processor, with no upload and no
  queue.
- **The wheel.** Hold Shift, Alt or Ctrl while you drag a file and a wheel
  appears under the cursor with the exact actions for that file.
- **A floating studio.** One pane of glass over your other windows, with four
  workspaces: Image Lab, PDF Studio, Media Studio and Documents.
- **Nothing to press afterwards.** Every result is written next to the
  original, under a new name, without asking you a question.

