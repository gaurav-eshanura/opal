# Opal — Marketing & Launch Plan

Goal: make people **know** Opal and **use** it. Everything here uses only claims we can
prove from source or measurement. Never say "every tool Acrobat has", never say
"fully audited/secure" (the last deep audit is recorded as static-only), never quote a
number without re-measuring it (see `opal-measured-numbers` memory / README testing section).

Current state (2026-11-06): public repo `github.com/gaurav-eshanura/opal` (0 stars),
release **v2.2.0** with Windows zips (Stitch Liquid Glass rebuild), website live on Firebase
Hosting from `website/`, suite 390 passed / 15 skipped / 0 failed, CI green on
ubuntu/windows/macos.

---

## 1. The one idea (positioning)

**"An opal has no colour of its own — the fire comes from light bending inside the stone.
Opal does the same for your files: one file, every form it can take, made on your own
machine in seconds."**

Three proof pillars, in this order:

1. **Offline & private** — 0 bytes uploaded, ever. No account, no subscription. Works on a
   USB stick. (Most competitors — iLovePDF, Smallpdf, Adobe online — upload your file to
   their servers. This is checkable by anyone with DevTools; it's our sharpest weapon.)
2. **DSC signing without Acrobat** — sign PDFs with a real USB token or `.pfx`/`.p12`,
   the thing Adobe Acrobat Pro charges a subscription for. Live-proven with an e-Mudhra
   HYP2003 token; verify signatures offline (intact / trusted / revoked).
3. **Counter-speed** — ~7 s for ten typical CSC counter jobs (measured), 103 wheel actions
   + 38 catalogue actions, ID photo / WhatsApp PDF / print sizes in one click.

Tagline options: *"Every file, in every light."* / *"The offline file studio."* /
*"Sign PDFs like Acrobat — without paying Acrobat."*

## 2. Audiences (in priority order)

| # | Audience | Where they live | What speaks to them |
|---|----------|-----------------|---------------------|
| 1 | CSC / cyber-café operators (India) | WhatsApp groups, CSC forums, Facebook groups, local markets | Aadhaar photo in 1 s, WhatsApp PDF <1 MB, DSC signing at the counter, rate-card one-pager |
| 2 | Privacy-conscious users anywhere | r/privacy, r/selfhosted, Hacker News | "0 bytes uploaded", works offline, no account, open source (MIT) |
| 3 | Legal / govt / CA-adjacent DSC users | LinkedIn, Bar Council circles, e-filing portals | Real PKCS#11 token signing, key never leaves the token, offline verification, RFC 3161 `--tsa` |
| 4 | Photo folks | r/photography, Instagram, YouTube Shorts | Offline background removal (8 matting models), upscale 2x/4x, face blur |
| 5 | Developers / power users | GitHub, HN, dev.to | CLI (`--convert/--tool/--sign/--verify-signature/--catalog/--json`), plugins folder, 391-test suite, watch folder |

## 3. Channels & concrete plays

### A. GitHub (day 1 — free, highest ROI)
- Enable **GitHub Discussions** (Announcements + Q&A categories) — it's the community hub.
- Add repo **topics**: `pdf-editor`, `offline`, `digital-signature`, `dsc`, `pkcs11`,
  `image-tools`, `ffmpeg`, `pyside6`, `privacy`, `windows`, `csc`.
- Submit to awesome lists: `awesome-pdf`, `awesome-offline-first`, `awesome-privacy`,
  `awesome-windows-apps`, `awesome-selfhosted` (PRs, follow each list's rules).
- Pin a "Start here" issue with the quickstart (download → unzip → run → drop a file).
- Keep the CI badge in README (already there). Tag releases properly (v2.1.0 done).

### B. Product Hunt launch (week 2)
- Maker account needed (free). Prepare assets **now**:
  - Gallery images: the 6 real screenshots in `website/assets/screenshots/` + a **GIF of the
    wheel appearing on drag** (we have `tools/capture_all_screens.py`; render 12–16 frames of
    the wheel and stitch into a GIF/looping video — the wheel is the signature move, show it).
  - Thumbnail: `website/assets/brand/icon-512.png` on the dark field.
  - Tagline: "Every file, in every light — the offline file studio".
  - First comment (maker): the 3 pillars + "0 bytes uploaded — verified by reading the
    source; it's MIT-licensed" + DSC-vs-Acrobat hook.
- Launch Tuesday–Thursday, 12:01 AM PT. Ask 10–15 people to upvote in the first hour
  (organic network only — never buy votes).
- Hunter: ask a well-known hunter if comfortable; otherwise self-hunt.

### C. Hacker News — "Show HN"
- Title: "Show HN: Opal — an offline file studio that signs PDFs with a DSC USB token, no Acrobat needed".
- Post Tuesday 9–11 AM ET. First comment: what it is, why offline matters, the PKCS#11 story
  (finding drivers, SysWOW64 trap, key never leaves token), and the wheel UX. Be ready to
  answer technical questions for 12 h.

### D. Reddit (rules: read each sub's self-promo rules; most allow one post in Showoff Saturday or with mod approval)
- r/privacy, r/selfhosted — "I made an offline PDF editor; 0 bytes uploaded, source is public" (lead with privacy).
- r/windows, r/software — wheel demo GIF.
- r/India, r/IndianTech — Hinglish copy (the site already has Hinglish mode — reuse that copy): "Acrobat bina diye PDF sign karo", "Aadhaar photo 1 second mein".
- r/photography — background removal quality post with before/after.
- Never astroturf. One post per sub, engage in comments honestly.

### E. YouTube / Shorts / Instagram Reels (the CSC goldmine)
60–90 s demos, phone-filmed or screen-recorded:
1. "Sign a government PDF with your DSC token — no Adobe Acrobat" (the killer video; show token plugged, PIN dialog, signed copy, verify output).
2. "Aadhaar photo ban gayi 1 second mein" (Hinglish; counter scenario).
3. "Background remove offline — network cable nikala, phir bhi kaam" (pull the cable on camera).
4. "Scan ko searchable PDF — offline OCR."
5. "WhatsApp pe PDF bhejna — 1 MB se kam."
Post natively on YouTube + Shorts + Instagram + X. Cross-post to WhatsApp Status via CSC operators.

### F. Directories & listings (week 1–3, mostly free)
- **AlternativeTo** — the #1 place people look for "iLovePDF alternative"; add Opal with
  "works offline" as the differentiator. This is where your "10x better" competitors are listed.
- **Slant.co**, **SourceForge**, **FossHub**, **MajorGeeks**, **Softpedia** — standard listings.
- **Capterra / G2** — PDF editor category (free listings; expect review solicitation later).
- **FileCR / FileEagle-style blogs** — guest post or review request.

### G. Indian tech press (week 3–6)
- YourStory, Inc42, TechCircle, Entrackr, ELEVATE (govt-tech). Pitch: "Made-in-India offline
  alternative to Adobe Acrobat for DSC signing at CSCs." Emphasize: Indian CA tokens work
  (e-Mudhra proven), CSC economy, Digital India angle. Send a one-page press note + screenshots + founder story.

### H. Blogs (SEO engine, ongoing)
- dev.to / Hashnode / Medium: technical posts — "Signing PDFs with a DSC USB token from Python (PKCS#11)",
  "Why we built a radial menu instead of a toolbar", "Zero-telemetry desktop apps in 2026",
  "Porting a PySide6 app to three OSes — what broke".
- **Comparison landing pages on the website** (big SEO win, honest): `/vs/ilovepdf`, `/vs/adobe-acrobat`,
  `/vs/smallpdf` — side-by-side table: offline? uploads? price? DSC? sign with token? Keep it factual.
- Target keywords: "free offline PDF editor", "sign PDF with DSC without Acrobat", "background remover offline",
  "Aadhaar photo maker online free", "ilovepdf alternative no upload", "convert HEIC to JPG offline Windows".

### I. CSC channel (highest LTV in India)
- One-page **printable rate card** (PDF): "Opal se kya kya hota hai" with per-job prices
  (ID photo ₹10, WhatsApp PDF ₹5, DSC sign ₹50…) — operators print and put it at the counter.
  Make it in the repo (`website/assets/counter-ratecard.pdf`) — bilingual Hindi/English.
- WhatsApp/Telegram groups of CSC operators; offer free onboarding call.
- Facebook/Instagram pages targeting "cyber cafe owner" interest.

### J. LinkedIn (B2B/legal angle)
- Posts about DSC compliance: "How to sign e-tender PDFs without an Acrobat Pro subscription",
  "PKCS#11 on Windows: the driver hunt" — tag CAs, government e-procurement folks.

### K. SEO/ASO technical
- Site: add `privacy-policy.html` and `terms.html` (required by most listings & ad platforms),
  JSON-LD `SoftwareApplication` schema (name, price 0, OS), `sitemap.xml`, `robots.txt`,
  OG images already exist. Add a lightweight privacy-friendly counter (**Plausible** or
  **Umami** self-hosted) — never Google Analytics on a privacy product; it undercuts the brand.
- If Android ever ships: ASO title "Opal — Offline PDF Editor & DSC Signer", keywords in
  short description; screenshots in Hindi + English.

## 4. Content calendar (first 8 weeks)

| Week | Action |
|------|--------|
| 1 | GitHub topics + Discussions + awesome-list PRs; AlternativeTo/Slant/SourceForge listings; directories; privacy-policy page; Plausible counter |
| 2 | Product Hunt launch (assets ready: wheel GIF + 6 screenshots); Show HN post |
| 2–3 | Reddit wave (privacy/selfhosted/windows/India); 3 YouTube demos |
| 3 | Press pitches (YourStory/Inc42/TechCircle); dev.to technical post #1 |
| 4 | CSC rate card PDF + WhatsApp/Telegram operator outreach; comparison pages `/vs/*` |
| 5 | Shorts/Reels series (5 videos); r/photography post |
| 6 | LinkedIn DSC-compliance series; guest post on a PDF-tools blog |
| 7 | "Opal vs Acrobat for DSC signing" comparison video; Capterra/G2 listing |
| 8 | Retrospective blog ("What we learned launching an offline-first app"); plan v2.1 from Discussions feedback |

## 5. Launch checklist (before the big push)

- [ ] Code-sign the Windows exe (SmartScreen) — the #1 day-one friction
- [ ] Fresh full deep security audit; record seal in RELEASE_NOTES.md (never claim "secure" without it)
- [ ] v2.0.1 zips in `website/downloads/` on the Firebase deploy AND attached to the GitHub release (done)
- [ ] Wheel GIF + PH gallery assets rendered from real captures
- [ ] Press kit folder: `assets/press/` with logo pack, screenshots, boilerplate, founder bio, contact email
- [ ] privacy-policy.html + terms.html live
- [ ] GitHub Discussions on; issue templates; CONTRIBUTING already exists
- [ ] Trademark "Opal" (IN class 9/42) — cheap insurance
- [ ] Plausible/Umami counter on site (privacy-friendly)
- [ ] Founder accounts ready on PH/HN/Reddit/X/LinkedIn/YouTube, consistent handle

## 6. Metrics (review weekly)

- GitHub: stars, forks, release download count (`gh api repos/gaurav-eshanura/opal/releases`)
- Site: unique visitors, download-button clicks, time on page (Plausible)
- Launch: PH upvotes/comments, HN points, Reddit karma, YouTube views + CTR
- Product: Discussions activity, issues (bug vs question ratio), zip downloads per day
- Leading indicator of the CSC niche: searches/questions about Aadhaar photo / DSC sign / WhatsApp PDF

## 7. Rules of the road (brand integrity)

1. Honest claims only — every number re-measured, every feature shown working. No "best", no
   "fully secure", no fake reviews, no astroturfing.
2. The privacy claim is the brand: never add analytics that phone home, never an account wall.
3. Bilingual (EN + Hinglish) everywhere for the India audience — the site already sets the pattern.
4. "Not affiliated with Tangerine/Adobe/iLovePDF" stays in the footer — clean separation.
5. Open-source goodwill: MIT license, public roadmap (GitHub Projects), fast issue triage —
   developers are your evangelists.

## 8. Optional paid (only after organic traction, month 3+)

- Google Ads India on long-tail, high-intent: "dsc pdf sign kaise kare", "aadhaar photo size",
  "pdf editor offline free", "ilovepdf alternative". Small daily budget; measure CAC against
  release downloads.
- Facebook/Instagram ads targeting "cyber cafe owner" + "CSC" interests in Hindi.
- Sponsor a couple of Indian tech YouTube channels doing honest reviews (disclose sponsorship).
