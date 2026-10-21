# TazaKhabar — Design System

## Brief (Phase 0)

- **Subject:** TazaKhabar. A tech job-market intelligence instrument: HN Who Is Hiring scraped every
  2 hours, ghost-job flagging, keyword trend forecasting, ATS resume scoring, a personalised digest.
- **Audience:** serious tech job seekers who want signal, not career-coach fluff.
- **Job of the site:** let a user read the market (trends, mood, velocity), work the queue
  (radar listings with real contact info), and calibrate themselves (resume ATS readout).
- **Language:** English. **Existing assets:** brand red #FF2D00, dark shell, mono labels, live API.
- **Owner constraint (hard):** mechanical touch. Border radius must never exceed 1px. Enforced at
  0px globally.
- **Assumptions (placeholders, marked):** backend runs separately at `NEXT_PUBLIC_API_URL`; all
  live-data pages must degrade into designed empty/error states when the API is down. The user's
  real name/photo are not used; account shows the email only.

## Concept Card (Phase 1)

Three concepts were generated from different territories:

1. **CNC / measuring instrument** (chosen). TazaKhabar's whole promise is honest measurement: match
   percentages, ATS scores, hiring velocity, a mood index. The site is the instrument that takes
   those readings. Scores: originality 4, fit 5, feasibility 5, portability 2.
2. **Teletype wire service.** The digest as paper feeding off a wire. Rejected: typewriter cream-paper
   cliché, fights the dark instrument brand, says nothing about jobs or ATS. 3/3/4/3.
3. **Mainframe batch queue.** The old Report 1 / Report 2 swap as punch-card batch processing.
   Rejected: retro-kitsch, the card-flip gimmick ages in a week. 4/3/4/4.

Chosen because concept 1 is the only one every screen can carry: every number in this product is a
reading, so every panel is a faceplate.

```
Idea:        TazaKhabar is a machined measuring instrument for the tech job market.
Metaphor:    A CNC control panel / calibrated bench instrument: engraved faceplates, hairline
             scribe lines, tick scales, tabular readouts, square signal lamps, one needle gauge.
Signature:   The Market Mood gauge on /trends: a machined dial whose red needle swings up from
             rest and settles with mechanical damping when the panel enters view, then keeps a
             slow micro-drift while you do nothing. The same reading language returns as the ATS
             bar-gauge on /profile.
Emotion:     The quiet confidence of a calibrated tool. First 3 seconds: this thing measures.
Motion verb: DETENT. Things click into position: short travel, firm settle, no float. Big
             elements move slower than small ones; stagger 30 to 60 ms.
Screenshot:  /trends at desktop width: the dial with major/minor ticks, engraved 0 to 100
             numerals, red needle resting at the live mood score, plate label
             MARKET MOOD INDEX / READ 67 on the scribe line.
```

Genericness test: a generic model would ship a centered hero with a gradient, three equal cards and
rounded chips. This build answers with left-aligned faceplate compositions, engraved plate labels
sitting on full-bleed scribe lines, tick-scaled bars, square lamps, tabular mono readouts, and a
real gauge. Nothing here is a template default.

**Scale of theatre:** this is a working product UI with auth, filters and infinite scroll, not a
portfolio launch. So: a short power-on strip (loader) on first paint, a mechanical shutter
transition between routes, the gauge as the one big moment. No WebGL. No scroll-jacking; Lenis
smooths wheel input only and stays native on touch.

## Art Direction System (Phase 2)

### Palette

| Role | Hex | Use |
|---|---|---|
| ground | `#0D0E0D` | page well |
| panel | `#141614` | faceplate fill |
| ink | `#F0EDE6` | primary text (brand beige kept) |
| muted | `#8C8C8C` | secondary text |
| line | `#2A2D2B` | hairline scribe lines, borders |
| accent | `#FF2D00` | needle red: active states, primary CTA, faults |
| signal | `#00FF41` | OK lamp only (email/apply available, status complete) |

### Type

Two families, both already sourced via next/font/google:

- **Space Grotesk** (300/400/500/600/700): display and UI sans. Machined, slightly squared terminals.
- **IBM Plex Mono** (300/400/500/600/700): every label, readout, chip, button and data figure,
  with `font-variant-numeric: tabular-nums`.

Dropped: Playfair Display (the editorial-italic AI default, fights the mechanical voice), Work Sans
and JetBrains Mono (redundant). Fluid scale: display `clamp(2.25rem, 1.2rem + 4.5vw, 4rem)` with
`-0.03em` tracking; section titles `clamp(1.5rem, 1.1rem + 1.6vw, 2.25rem)`; body 16 to 17px at
1.5; mono labels 10 to 12px at `0.14em` tracking, uppercase, always carrying real information.

### Grid and rhythm

12 columns, 24px gutter, content max 1440px, side padding `clamp(20px, 4vw, 48px)`. Every section
is separated by a full-bleed 1px scribe line with an engraved plate label optically seated on it
(label has ground-coloured padding so the line reads as passing behind it). Section rhythm varies:
dense instrument clusters, then 8 to 12vh of empty well.

### Shape

One rule: `border-radius: 0` on everything, enforced by a global reset and the Tailwind
`borderRadius` scale. The live indicator lamp is a square. The cursor stays native.

### Motion language

- Eases: `expo.out` for entrances and the needle settle, `expo.inOut` for the shutter, `power3.out`
  for small UI. One family, no per-component curves.
- Durations: UI feedback 160 to 240ms; entrances 700 to 1100ms; needle swing 900ms with a
  single overshoot-free settle.
- Idle: the needle micro-drifts +/-0.8 degrees over 6s; signal lamps breathe opacity. One GSAP
  ticker clock; lamp pulse via CSS keyframes. Paused off screen and disabled under reduced motion.
- Reveals: `data-reveal="up"` for panels, `data-split` only on server-rendered static headings.

### Composition plan (one layout family per section)

```
LANDING            AUTH              SETUP WIZARD       JOBS (radar)
+--------------+   +----------+      +---------------+  +--------+------------------+
| plate label  |   | BACK     |      | tick progress |  | FACE-  |  header readout  |
| display line |   | h1       |      | h1            |  | PLATE  |  [tab] [tab]     |
| left, huge   |   | fields   |      | choice grid   |  | filters|  card card       |
| right: status|   | [switch] |      | [BACK][CONT]  |  | ticks  |  card card       |
| column read- |   +----------+      +---------------+  | lamp   |  sentinel        |
| outs         |                                       +--------+------------------+
+--------------+
DIGEST            TRENDS (signature) PROFILE           Q&A CONSOLE
+----------------+ +---------------+ +----------+----+ +----------------+----------+
| h1             | | GAUGE (dial)  | | plate 01|plate| | terminal chat  | matches  |
| featured plate | | tick scale    | | 02 roles|03  | | > prompt       | why this |
| category tabs  | | stat rail     | | ATS bar |    | | history        | role     |
| ledger rows    | | bar ledger    | | gauge   |    | +----------------+----------+
+----------------+ +---------------+ +----------+----+
```

### Explainer figure

Not needed. The gauge is the one figure, and it is hand-built SVG inside the concept (see
`src/components/MoodGauge.tsx`). No anatomy skill section planned.

## Build conventions

- Engine ported from the awwwards skill (`src/engine/*`), Next adapter, GSAP ticker as the only
  clock. Lenis on wheel only; native touch scroll preserved.
- Content and copy stay in page components (this app has no CMS); all copy follows the content
  rules: no em/en dashes in visible text, no filler verbs, sentence case for prose, uppercase only
  for mono instrument labels.
- Radius audit: every `rounded-*` class removed; `rounded-full` lamps and spinners become squares
  or square tick loaders.

## QA record

(filled during Phase 4)
