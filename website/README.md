# Opal — website

The marketing site for **Opal**, the offline file studio for Windows,
macOS and Linux.

```
website/
├── index.html                     # the whole site (one page)
├── css/styles.css                 # design system + all styles
├── js/main.js                     # language switch, reveal, tour tabs, FAQ, copy
├── firebase.json                  # Firebase Hosting rules for this folder
├── .firebaserc                    # which Firebase project to publish to
├── downloads/                     # release zips (built, never committed)
└── assets/
    ├── brand/                     # logo, favicon, app icon sizes, OG image
    └── screenshots/               # real captures of the app (regenerate them!)
```

## Running it locally

Open `website/index.html` directly, or serve it:

```powershell
python -m http.server 8080 --directory website
# then visit http://127.0.0.1:8080
```

## Publishing it

Any static host works — there is no build step.

| Host | How |
|---|---|
| **Netlify / Cloudflare Pages** | drag the `website/` folder onto the dashboard, or connect the repo and set the publish directory to `website` |
| **GitHub Pages** | push `website/` to a `gh-pages` branch (or `/docs`) and enable Pages in the repo settings |
| **Firebase Hosting** | `firebase deploy --only hosting` from the `website/` folder (the config lives here: `website/firebase.json` and `website/.firebaserc`) |
| **Any web server** | copy the folder to the document root |

> **Use your own Firebase project.** The repository root's `firebase.json`
> belongs to a different site (`bajrangi-disposables`) — do not publish Opal
> through it. `website/.firebaserc` names a placeholder project
> (`opal-studio-site`); change it to the real project id before the first
> deploy, or run `firebase use --add` in the `website/` folder.

## The download button

The two buttons in `index.html` point at files inside this folder:

```
downloads/Opal-v2.0.1-Windows-x64.zip        core    (~98 MB)
downloads/Opal-Full-v2.0.1-Windows-x64.zip   full    (~222 MB)
```

Those archives are **built, not committed** — `website/downloads/` is in
`.gitignore`. The build produces them:

```powershell
python build_release.py            # full build  -> Opal-Full-v2.0.1-<platform>.zip
python build_release.py --core     # core build  -> Opal-v2.0.1-<platform>.zip
```

`build_release.py` writes each zip into `dist/` and copies it into
`website/downloads/`, so after a build the links on the site work as they
are. If you host the files somewhere else (a CDN, an S3 bucket), change the
two `href`s in `index.html` to those URLs and the buttons keep working.

To publish a release: build both variants, then deploy the folder with the
downloads still in it.

## Editing the copy

Every heading, paragraph and button carries two copies:

```html
<h2 data-en="Every file, in every light."
    data-hing="Har file, har roshni mein.">Every file, in every light.</h2>
```

The language switcher (top right) swaps between them and remembers the choice.
`#hinglish` in the URL forces Hinglish — handy for sharing a link with a
particular audience. Add a new language by adding `data-xx` attributes and one
line in `js/main.js`.

## Changing the brand

The brand is defined in three places, all easy to swap:

1. **Name & colours** — the tokens at the top of `css/styles.css`
   (`--fire-teal`, `--fire-violet`, `--glass`, `--ink-900`, …) and the
   wordmark in `index.html`.
2. **The mark** — `assets/brand/mark.svg` (and `logo.svg`, `favicon.svg`). The
   stone is drawn in code in `opal_studio/brand.py`, which also writes the
   Windows `.ico` and every PNG size; run `python generate_icon.py` after
   changing it. The site's SVG carries a slow drift so the fire moves, the way
   an opal does when the light does.
3. **The app's own theme** — `opal_studio/theme.py` holds the matching
   palette and the global stylesheet, and `opal_studio/glass.py` holds the
   painting code for a pane of glass (lit from above, bright where the light
   bends through the edge).

## Refreshing the screenshots

The product shots in `assets/screenshots/` are real captures of the app, so they
never go stale on purpose. After changing the app's look, re-take them:

```powershell
python tools/capture_screenshots.py
```

It renders the dashboard, image lab, PDF studio, tool wheel and document viewer
on the real widgets and overwrites the PNGs.

## A note on the name

Opal is an independent product with its own name, mark and codebase. It
is **not** affiliated with, endorsed by, or connected to any other converter —
including the separately-owned "Tangerine for Mac". The site says so in the FAQ
and the footer on purpose: if a visitor searches for the Mac app, they should
land here knowing this is a different thing.

## Checklist before launch

- [x] Download buttons point at real archives (`downloads/Opal-v2.0.1-*.zip`)
- [ ] Run `python build_release.py` and `python build_release.py --core`, then
      publish the folder with `website/downloads/` still in it
- [ ] Set the real Firebase project id in `website/.firebaserc`
- [ ] Swap the placeholder "Opal" copy for your final wording
- [ ] Add a privacy policy page and a contact/press-kit page
- [ ] Write the OG image (`assets/brand/icon-512.png` is the fallback now)
- [ ] Check the site on a phone — the layout is responsive but worth a look
- [x] Version number in the footer (keep it in step with
      `opal_studio/version.py`, which the app and the build both read)
