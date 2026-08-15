# DDR Score Tracker

A personal hall of fame for DanceDanceRevolution — every Perfect Full Combo on
Expert and Challenge Single Play, generated straight from the score-tracking
spreadsheet.

Static site: plain HTML, CSS and JavaScript, no build step and no dependencies.

```
index.html      Dashboard — totals, level distribution, precision spread, top scores
records.html    My Records — the full archive, filterable and sortable
about.html      Four tabbed stories: about me / the cabinets / making this app / videos
assets/         css / js / jacket artwork
data/           generated records.json (+ records.js for file:// use)
tools/          the spreadsheet → JSON pipeline
```

## Running it

Any static server works:

```bash
python3 -m http.server 4325 --directory ~/Documents/CLAUDE/ddr-score-tracker
```

Then open <http://localhost:4325>. Opening `index.html` straight off disk works
too — the data is loaded from `data/records.js`, which needs no fetch.

## Updating the records

The spreadsheet is the source of truth. After editing it, rebuild:

```bash
python3 tools/build_data.py "/path/to/A.P.P's DDR Score Tracker (Aug 26 2023).xlsx"
```

That rewrites `data/records.json` and `data/records.js`. Useful flags:

| Flag | What it does |
| --- | --- |
| `--report` | Lists every song title that could not be matched to the song database |
| `--jackets` | Downloads any missing jacket artwork into `assets/img/jackets` |
| `--banners` | Fetches ZIv banners for songs that have no square jacket |
| `--refresh-songdb` | Re-pulls the song database (do this when a new DDR mix lands) |

The "last updated" date shown on the site is read from the **date in the
workbook's filename** (`... (Aug 26 2023).xlsx`), falling back to the file's
modification time. Keep naming the file that way and the date stays honest.

### Workbook format

One sheet, laid out as an A–Z grid. Every populated cell from row 5 down is one
cleared chart, written as three lines:

```
Song Name
ESP
30p
```

- Line 2 is `ESP` (Expert Single) or `CSP` (Challenge Single).
- Line 3 is the number of **Perfect** judgements in that full combo. `0p` would
  be a Marvelous Full Combo.
- `33p / 12p` records an improvement; the best (lowest) value becomes the current
  record and both are shown in the detail drawer.
- A cell with no `p` line is kept, with the score shown as unlogged.

## How the score is calculated

Modern DDR (X onwards) gives every scoring target `1,000,000 / N` points, and a
Perfect is worth exactly ten points less than a Marvelous. On a Perfect Full
Combo the Perfects are the only deduction, so the note count cancels out:

```
score = 1,000,000 − (10 × Perfects)
```

So `3p` is exactly 999,970 and `30p` is exactly 999,700. These are real scores,
not estimates — the workbook's Perfect count is all the information needed.

## Where the song metadata comes from

The workbook records the song, difficulty and Perfect count. Chart level, origin
mix, artist, BPM and jacket artwork are joined in from two community sources:

1. **[DDRCardDraw](https://github.com/noahm/DDRCardDraw)** — merged across every
   DDR release file it ships, so songs removed from the current mix still
   resolve. This is also where the jacket art comes from.
2. **[Zenius -I- vanisher](https://zenius-i-vanisher.com/)** game database —
   scraped by `tools/fetch_ziv.py` for the licensed songs DDRCardDraw no longer
   carries. Releases before DDR X are used for *origin only*, never for level:
   they still use the retired 1–10 foot scale, which does not convert cleanly to
   the modern 1–20 one.

Console and European releases matter more than you would expect: a lot of the
licensed songs in the workbook never appeared on a Japanese arcade cabinet at all.
They came from the PS2 / Wii / Xbox ports or the European *Dancing Stage* line, so
`fetch_ziv.py` scrapes those catalogues too (origin, artist and BPM only — their
ratings are per-port and mostly on the retired 1–10 foot scale).

Current coverage of the 642 records: **614 matched**, **614 with an origin**,
**554 with a chart level**, **591 with artwork**.

Artwork comes in two forms. DDR only adopted square jackets around 2013; before
that every song had a wide **banner** instead, and ZIv still hosts those. So a
song with no jacket falls back to its real banner, shown whole on a generated
tile. ZIv serves a square per-release logo when a song has no art of its own —
those are rejected on aspect ratio rather than passed off as artwork. The 51
records with neither get the generated tile alone: a gradient whose hue is
derived from the song title, with the title's first character, so a given song
always looks the same.

To fix or fill in anything by hand, add it to `tools/overrides.json`, keyed by
the song title exactly as it appears in the workbook:

```json
{ "Gakuen tengoku 学園天国": { "level": 12, "origin": "DDR SuperNOVA2" } }
```

Then rebuild. Run with `--report` to see what is still unmatched.

## Proof photos

Each record's drawer ends with a **Proof** section holding the result-screen
photo, tap to enlarge. Until real photos are attached, every record shows a
shared sample marked `Placeholder`.

To attach a real one, drop the photo in `assets/img/proof` named
`<slug>-<esp|csp>.<jpg|png|webp>`, where the slug is the song title lowercased
with everything but letters and digits removed:

| Chart | Filename |
| --- | --- |
| PARANOiA — Expert | `paranoia-esp.jpg` |
| CANDY♡ — Expert | `candy-esp.jpg` |
| Dam Dariram — Challenge | `damdariram-csp.jpg` |

Then rebuild. The build matches it to the chart, the tag flips from
`Placeholder` to `Result screen`, and the caption changes with it. Files that
don't match that shape (like `sample-proof.jpg`) are ignored.

Photos straight off a phone are large; downscale them first, e.g.
`sips -Z 1400 -s format jpeg -s formatOptions 72 in.png --out out.jpg`.

## The home page's "latest PFC"

The workbook is sorted alphabetically and carries no dates, so the most recent
clear cannot be worked out from it. Name it by hand in `tools/site.json`:

```json
{ "latestRecord": "The Legend of MAX" }
```

Rebuild and it appears under the hero. Left empty, the line is simply omitted.

## Notes

- **Theme** — dark by default; the switch in the header remembers the choice in
  `localStorage` and it is applied before first paint, so there is no flash.
- **Music** — plays in the background from YouTube. Browsers only permit
  unattended playback when muted, so it starts muted and the bar shows an
  "Enable sound" button; the choice, mix and volume are then remembered.
- **The background follows the music.** Each mix in `MIXES` (top of
  `assets/js/app.js`) carries a `palette` key; picking a mix writes it to
  `data-mix` on `<html>` and the matching block in the "background palettes"
  section of `style.css` takes over. A palette is just three colours as raw
  `r g b` triples (`--c1/2/3`) plus a `--bg-dark` tint — the wash, the blobs and
  both themes all derive from those, so adding a release means adding one block.
  Gradients can't be transitioned, so the glow layer fades out, swaps and fades
  back in. The choice is stored and re-applied before first paint alongside the
  theme, so neither flashes on load.
- **Animated numbers** replay on every load and on back/forward navigation. They
  always land on the true value even if the tab is hidden while they run.
- **`about.html`** — four tabbed sections sharing one layout (prose left, photo
  grid right). The first panel's prose is marked `EDIT ME`; all of it is yours to
  rewrite. Photos live in `assets/img/play` (screens) and `assets/img/room`
  (cabinets), both sourced from `~/Documents/DDR/PHOTOS`. The "Making this app"
  grid uses labelled placeholder tiles — add real screenshots and swap
  `<figure class="is-placeholder">` for a normal `<figure><img …>`. The
  "DDR videos" tab is deliberately `disabled` with a Coming soon badge.
- **The detail drawer is shared** (`assets/js/drawer.js`). Both the archive cards
  and the home page's top-score cards open the same panel; the module also owns
  the jacket/banner/placeholder artwork helpers, so there is one implementation
  of each.
- Jacket artwork is cached locally in `assets/img/jackets` (~12 MB, 500 files).
- **Background motion** — three colour blobs sampled from the DDR (2014) attract
  screen (cyan `#11e2ed`, azure `#44c1fd`, violet `#8072f7`) orbit the centre
  (`rotate` on the outer span, an offset on the inner one) on 31s / 35s / 39s
  loops, one of them reversed, with a slower scale breath on an unrelated period
  so the arrangement never repeats. Same motion in both themes; only the alphas
  change. `prefers-reduced-motion` parks them.
- **Background structure** — the DDR (2014) screen is really a vertical wash
  (cyan top → azure → violet base), which roaming blobs alone can't reproduce,
  so a fixed gradient layer supplies it and the blobs orbit over the top.
  Composites run `#13959D` teal → `#2665A3` → `#6C52AE` violet.

  **This is deliberately brighter than WCAG AA allows.** The owner asked for the
  DDR (2014) mood explicitly, over a contrast-safe alternative. Text over the
  cyan band lands around 3.6:1 — fine for the large hero type, under AA for body
  copy. Three things keep it readable: every text token is near-white rather than
  grey, `body` carries a tight dark `text-shadow`, and the header, filter bar and
  player bar are light glass (`rgba(255,255,255,.10)`) so no chrome reads as a
  dark band across the wash. If you ever want the accessible version back, drop
  the `.glow::before` alphas to roughly a third and restore grey secondary text.
- **Type** — Inter everywhere except the page headline and the navbar wordmark,
  which use Jersey 10. Its cap height is 0.536em against Inter's 0.727, so it
  needs a much bigger size to read at the same optical scale; the headline
  measures 11.84em wide, which is what sets the `clamp(40px, 7vw, 96px)` — it
  clears the content box on one line from 830px up. Below 821px it wraps.
- **Home headline** — hover turns it into gold gradient text and shows a gold
  tooltip that tracks the pointer; clicking plays the announcer clip.
- **The level chart** sorts by level (default) or by PFC count.
- **Background music** — eight mixes in the player bar's picker, DDR 2013 by
  default; the choice is remembered. Edit the `MIXES` list at the top of
  `assets/js/app.js` to add more.
- The hero title plays the AAA announcer clip
  (`assets/sfx/aaa-dancing-master.mp3`) on click, with a tooltip on hover.
- CSS and JS are linked with a `?v=` timestamp so a browser never serves a stale
  stylesheet after an edit. Bump it whenever you change `assets/` by hand.
