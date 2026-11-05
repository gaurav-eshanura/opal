# Opal — Press Kit (v2.1.0, November 2026)

Contact: [press email — fill in] · Site: (deployed Firebase Hosting for `website/`) · Repo: https://github.com/gaurav-eshanura/opal (MIT)

## Boilerplate — short (one sentence)
Opal is a free, fully offline desktop file studio for Windows (macOS/Linux from source) that converts, edits and signs files on your own machine — including PDF signing with a real DSC USB token, the job Adobe Acrobat Pro charges a subscription for.

## Boilerplate — long (one paragraph)
Opal ("every file, in every light") is an open-source (MIT) desktop app that takes the file you already have and returns it in the form the job needs — a WhatsApp PDF under 1 MB, a print-ready Aadhaar photo, a repaired scan, a signed contract — without ever uploading anything: 0 bytes leave the machine, by architecture, and the source is public so anyone can verify that. Its signature feature is real digital-signature signing: plug in an Indian CA's DSC USB token (PKCS#11) or drop in the `.pfx`/`.p12` they hand out, and Opal computes a standards-compliant signature inside the token — the private key never leaves the device — then verifies any signed PDF offline (intact / trusted / revoked). Around that sits a radial action wheel (hold Shift/Alt/Ctrl while dragging a file — 103 actions), a floating studio, image tools with offline AI (background removal, 2x/4x upscale), a full PDF editor, media tools with bundled FFmpeg, document/archive viewers, a watch folder, and a CLI. Built for CSC counters in India and for anyone who wants their documents to stay on their own disk.

## Facts sheet (re-measure before re-quoting — commands in README "Testing")
- 103 wheel actions (union over all modes incl. batch), 38 catalogue actions
- Test suite: 390 passed / 15 skipped / 0 failed (pytest, offscreen Qt)
- Release v2.1.0: `Opal-v2.1.0-Windows-x64.zip` (103,554,634 B ≈ 99 MiB zipped), `Opal-Full-v2.1.0-Windows-x64.zip` (233,087,187 B ≈ 222 MiB zipped)
- DSC signing live-proven with a real e-Mudhra HYP2003 token; `adbe.pkcs7.detached` output, verifies intact + trusted
- Works with the network unplugged (Full build bundles the AI cut-out model); only optional extras touch the network (one-time model download, opt-in `--tsa` — hash only)
- CI green on ubuntu / windows / macos (GitHub Actions)
- Honest gaps: no MDP certification / LTV-DSS / preflight-PDF-X / JS actions yet (roadmap); published zips are Windows-only; exe not yet code-signed

## Assets (in this folder / repo)
- `website/assets/press/wheel-demo.gif` — the radial wheel animating through its wedges (12 frames, rendered from the real widget)
- `website/assets/screenshots/01..05*.png` — real captures of the running app (dashboard, image lab, PDF studio, wheel, document viewer)
- `website/assets/brand/` — mark.svg, logo.svg, wordmark.png, icon-16..512.png, favicon.svg (do not recolor; keep clear space = icon height)
- `website/assets/counter-ratecard.pdf` — printable bilingual (EN/Hindi) counter rate card for CSC operators
- `website/compare.html` — "Opal vs Acrobat & the free PDF tools" scoreboard

## Brand rules
- Name: **Opal**. Mark: the opal-stone SVG (`mark.svg`). Never reuse the Mac "Tangerine" branding — Opal is an independent product, not affiliated with Adobe, iLovePDF, Smallpdf, Xodo, Foxit or Tangerine.
- Claims: only measured/proven facts (see above). Never "fully secure", never "every tool Acrobat has".
- Tone: plain, honest, a little warm. Bilingual EN/Hinglish is welcome for Indian audiences.

## What we're looking for (Nov 2026)
Coverage of: offline-first software, privacy-respecting PDF tools, DSC/e-signing in India's CSC economy, open-source Windows apps. Happy to do founder interviews, technical deep-dives (PKCS#11 driver discovery on Windows), or screen-share demos.
