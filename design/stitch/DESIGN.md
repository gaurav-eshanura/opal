# Opal — Liquid Glass Design System (Stitch canonical)

**Project:** `3961317633702086904` — *Opal — Liquid Glass File Studio*
**Design system asset:** `assets/3539134380188353237` ("Opal Liquid Glass v1")
**Captured:** 2026-11-06 · Screens captured: Dashboard, Image Lab, PDF Studio, Radial Wheel overlay.

Opal is a free, fully offline desktop "file studio" for Windows/macOS/Linux.
The one visual language: **liquid glass on a deep inky field**. Every screen is
a pane of frosted glass floating over a radial light-Field (soft top-left
violet glow, deep navy ground `#0B0E18`). Depth comes from glass, specular
top-edge highlights, and inner shadow — never from flat opaque panels.

## Color

| Token | Value |
|---|---|
| Ground | `#0B0E18` |
| Ground raised | `#141A2B` |
| Ground sunken | `#080B13` |
| Glass surface | white 7% |
| Glass hover | white 11% |
| Hairline border | white 10% |
| Emphasized border | white 18–20% |
| Accent (primary violet) | `#6C63FF` |
| Accent highlight | `#8A83FF` |
| Accent deep | `#4E45D6` |
| Accent soft | `rgba(108,99,255,0.20)` |
| Accent wash | `rgba(108,99,255,0.12)` |
| Text primary | `#EDF1FA` |
| Text dim | `#A8B2C8` |
| Text faint | `#8B96AD` |
| Inverse | `#0B0E18` |
| Success / leaf | `#37C98A` (+16% soft fill) |
| Danger | rose family only where destructive |

**Fire spectrum** (emphasis only — active wedges, gradients, graph ticks,
status dots; never body text):

| Token | Value |
|---|---|
| Teal | `#21C7D0` |
| Blue | `#3C7BF2` |
| Violet | `#8A5CF6` |
| Rose | `#EE4E8A` |
| Amber | `#FF9A3C` |
| Green | `#37C98A` |

**Primary button gradient:** violet `#6C63FF` → violet `#8A5CF6` → rose
`#EE4E8A` (the Stitch "Quick Action" treatment; the app's own primary CTA
runs violet → rose → amber `#FF9A3C`). Specular white top highlight line on
primary buttons.

**Light-Field gradient (background):**

```css
background:
  radial-gradient(circle 800px at 15% 10%, rgba(108,99,255,.18), transparent 60%),
  radial-gradient(circle 600px at 85% 85%, rgba(238,78,138,.08), transparent 55%),
  #0B0E18;
```

Qt equivalent already lives in `theme.py` as `FIELD`
(`qradialgradient cx:0.5,cy:-0.1,radius:1.6 … #161C30 → #0E1220 → #0B0E18`).

## Type (Qt ladder — authoritative)

| Ladder | px | weight |
|---|---|---|
| Title (hero/display) | 22 | 700 |
| Head | 15 | 600 |
| Body | 12 | 400 |
| Caption (labels, badges) | 11 | 600 |
| Hint | 10 | 400 |

- UI: **Inter** first choice (Stitch pair: Inter headlines + Public Sans
  labels), then Segoe UI / system-ui (real `UI_FAMILIES` unchanged).
- Monospace: Cascadia Mono / Consolas.
- Handwriting, signature pad only: Segoe Script / cursive.
- Material Symbols Outlined (`wght 300–350`) is the Stitch icon face; the
  app's local equivalent is `opal_studio/icons.py` (20px grid, 2px round-cap
  strokes, crisp at any size, no emoji-font dependency).

## Shape & space

| Token | Value |
|---|---|
| Radius small | 8 |
| Radius base | 12 |
| Radius large | 18 |
| Pills | fully round |
| Dialog rhythm | 24 px |
| Rail gutters | 12 px |
| Spacing scale | 8 pt |

## Glass recipes (the two canonical shadows)

```css
/* specular-edge (panels, drop zone, hub) */
box-shadow:
  inset 0 1px 0 0 rgba(255,255,255,.18),
  0 20px 40px -15px rgba(0,0,0,.6);

/* specular-subtle (tiles, cards, chips) */
box-shadow: inset 0 1px 0 0 rgba(255,255,255,.10);

/* disc-specular-edge (radial wheel disc) */
box-shadow:
  inset 0 1.5px 1px 0 rgba(255,255,255,.35),
  inset 0 -1.5px 1px 0 rgba(255,255,255,.08),
  0 30px 100px -20px rgba(0,0,0,.85),
  0 0 50px -5px rgba(108,99,255,.22);

/* hub-glass-depth (wheel center hub) */
box-shadow:
  inset 0 2px 4px 0 rgba(255,255,255,.25),
  inset 0 -4px 8px 0 rgba(0,0,0,.6),
  0 15px 35px -5px rgba(0,0,0,.7);
```

Scrollbars: 6px, thumb white 12% → hover 22%, track `#0B0E18` 60%.

## Signature patterns

### Radial wheel (tightened spec from Stitch screen "Opal Radial Wheel Overlay")
- 500 px glass disc (SVG, 36° × 10 wedges; R_out 246 · R_in 96 in viewBox
  units), disc shadow `disc-specular-edge`, perimeter hairlines (white 15%
  outer · 5% inner), separators white 12%.
- Active wedge: rose `#EE4E8A` → violet `#8A5CF6` → violet `#6C63FF`
  gradient, bloom glow (`gaussianBlur stdDev 8`, drop-shadow rose), **2 px
  white stroke**, icon + label in white 700 uppercase, key-hint chip below.
- Inactive wedges: radial glass fill (transparent → white 6%), white 12%
  stroke, ≤11px labels, 9px mono key hints.
- Center hub (184 px): `#080B13` 90%, white 20% border, `hub-glass-depth`,
  mode pill (`⇧ Convert` etc.), file name + size/pages, "Release key to
  select" hint under a hairline divider.
- Desc banner pill beneath the disc (hovered tool desc + meta chips + Options).
- Bottom-right file-type filmstrip chips (PDF active / Image / Video / Audio /
  Doc / Archive). *(Not adopted — the wheel stays self-contained; the
  desktop app's keyboard-modes already do this job.)*
- Bottom status bar: `● 100% Offline | Zero Network Calls | Radial Engine
  v1.4 | RAM: 38MB`. *(The desktop status strip in the app shows the same;
  engine name/RAM are desktop-measured values, not Stitch placeholders.)*

### Icon tiles & feature cards
- Catalog tile: frosted glass, icon box 32 px radius 8, label 12/500 white,
  sublabel 10px white 40%; hover: fire-spectrum tint per tile family, border
  `#6C63FF`/50%, scale .95 active.
- Feature card: top fire-spectrum tick 32×2 px gradient, 36 px icon chip,
  14px serif? — no: 14px semibold head, 11px dim description, footer hairline
  + mono meta.
- Section header: 6px fire dot + 11px uppercase 600 white tracking-wide.

### Dashboard layout
- Slim glass nav rail (w-16/20, rounded-r, white/5, blur): Opal mark
  (40px glass chip, 20px gem, gradient violet→rose→amber rotate-45) + nav
  (48px buttons, active: white 10% + 20% ring + left 4×20px violet→rose fire
  bar + violet glow) + footer help/shield (green).
- Top chrome: frameless, white/5, hairline bottom: traffic dots
  (rose/amber/green glossy), brand, Convert/Tools/Actions nav (active:
  white + 2px white-40 underline), center ⌘K search pill, right: offline
  status pill (green pulse dot) + gradient Quick Action + window glyphs.
- Hero: kicker pill (2px gradient dot + "OFFLINE CORE ENGINE ACTIVE" 11px
  uppercase white 60% + faint "· Memory Encrypted"), 22–30px title with
  white→#A8B2C8 gradient sheen, 12–14px dim subtitle; right mini "Sandbox
  Cache" glass pill.
- Drop zone: dashed violet 40% border, white 4% fill, blur-xl, 16–18px
  radius, glow backing (violet 30% → rose 20% → amber 20%, blur-xl, 40% →
  75% hover), 64px upload chip, 18–20px head, quick buttons (primary
  gradient + ghost), kbd legend with tactile badges (⇧ Shift Convert · ⌥ Alt
  Tools · ⌃ Ctrl Actions).
- Status strip (bottom, white/8 bg, 10–11px): `Offline-first · No account
  required · MIT Open Core` left; `RAM: 42MB · Engine: Local PySide6 / Rust
  Core · Zero Network Calls` center (mono, green 90% on the last); right CPU
  + "Clear Scratch".

### Tool rails (Image Lab pattern)
- Right vertical scrollable rail, 12px gutters, sections: Transform /
  Color & Filters / Offline Pipelines / Export quality (92% slider).
- Bottom docked bar: mode segmented control (Pad/Trim/AI), offline badge,
  Undo (⌘Z), primary gradient "Save beside original".

### PDF Studio pattern
- Segmented control (File/Organize/Annotate/Convert) + icon toolbar.
- Center: warm off-white page on sunken canvas; dashed violet signature field.
- Right inspector: monospace cert rows, DSC token row, primary "Sign with
  token", verify chips (intact ✓ / trusted ✓ / revoked ✕).

### Dialogs
- 24px padding, 18px radius, specular top highlight, hairline borders; PIN
  stays in memory (shield note); toast = floating pill with left fire bar +
  Open/Show actions.

## Brand voice

Clean, calm, a little warm. Bilingual-ready (EN/Hinglish labels allowed).
Never "fully secure" — the audit is static-only and recorded as inconclusive.
