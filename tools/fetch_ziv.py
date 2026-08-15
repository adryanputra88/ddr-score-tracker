#!/usr/bin/env python3
"""
Supplementary song source: Zenius -I- vanisher's game database.

    python3 tools/fetch_ziv.py

DDRCardDraw only ships the mixes it can still draw cards for, so licensed songs
that were removed years ago have no level or origin there. ZIv keeps a full song
list per release, with the Expert/Challenge Single ratings and a
"First Appearance" annotation on every row -- exactly the two fields the
workbook is missing.

Only DDR X and later are scraped: the 1-20 rating scale arrived in X, and the
older pages still use the 1-10 foot scale, which would be misleading here.
Newest release wins, so a song keeps whatever its most recent rating was.

Writes tools/songdb_ziv.json, which build_data.py consults after DDRCardDraw.
"""

import html
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "songdb_ziv.json")
URL = "https://zenius-i-vanisher.com/v5.2/gamedb.php?gameid={}"

# Japanese arcade releases, newest first. All use the modern 1-20 scale.
# A20 and later are deliberately absent: ZIv has no song list for them, and
# DDRCardDraw already covers everything from that era.
GAMES = [
    (2979, "DDR A"),
    (1129, "DDR (2013)"),
    (347, "DDR X3 VS 2ndMIX"),
    (286, "DDR X2"),
    (148, "DDR X"),
]

# Pre-X releases, scraped for "First Appearance" only. Their ratings are on the
# retired 1-10 foot scale, which does not convert cleanly to 1-20, so a level
# from these pages would be worse than no level at all.
LEGACY_GAMES = [
    (89, "DDR SuperNOVA2"),
    (238, "DDR SuperNOVA"),
    (81, "DDR EXTREME"),
    (88, "DDRMAX2"),
    (147, "DDRMAX"),
    (146, "DDR 5thMIX"),
    (145, "DDR 4thMIX"),
    (142, "DDR 3rdMIX"),
    (134, "DDR 2ndMIX"),
    (131, "DDR 1stMIX"),
]

# Console and European releases. A lot of the licensed songs in the workbook
# never appeared on a Japanese arcade cabinet at all -- they came from the PS2 /
# Wii / Xbox ports or the European "Dancing Stage" line -- so without these the
# songs resolve to nothing. Ratings here are per-port and mostly on the old 1-10
# foot scale, so like LEGACY_GAMES these contribute origin, artist and BPM only.
CONSOLE_GAMES = [
    (402, "DDR X (CS)"), (407, "DDR X2 (CS)"),
    (394, "DDR SuperNOVA2 (CS)"), (374, "DDR SuperNOVA (CS)"),
    (408, "DDR HOTTEST PARTY 3"), (399, "DDR HOTTEST PARTY 2"),
    (378, "DDR HOTTEST PARTY"), (409, "DDR MUSIC FIT"),
    (355, "DDR EXTREME2"), (360, "DDR EXTREME (CS)"),
    (352, "DDR FESTIVAL"), (353, "DDR STR!KE"),
    (359, "DDR Party Collection"), (361, "DDRMAX2 (CS)"), (362, "DDRMAX (CS)"),
    (389, "DDR EXTRA MIX"), (390, "DDR 5thMIX (CS)"), (388, "DDR 4thMIX (CS)"),
    (387, "DDR 3rdMIX (CS)"), (386, "DDR 2ndMIX (CS)"), (385, "DDR KONAMIX"),
    (413, "DDR (CS)"), (395, "DDR Disney Channel Edition"),
    (351, "DDR ULTRAMIX4"), (363, "DDR ULTRAMIX3"),
    (364, "DDR ULTRAMIX2"), (365, "DDR ULTRAMIX"),
    (398, "Dancing Stage UNIVERSE2"), (382, "Dancing Stage UNIVERSE"),
    (366, "Dancing Stage Unleashed 3"), (367, "Dancing Stage Unleashed 2"),
    (368, "Dancing Stage Unleashed"),
    (379, "Dancing Stage SuperNOVA2"), (373, "Dancing Stage SuperNOVA"),
    (354, "Dancing Stage Max"), (384, "Dancing Stage MegaMix"),
    (393, "Dancing Stage Fusion"), (383, "Dancing Stage Fever"),
    (391, "Dancing Stage PARTY EDiTiON"), (371, "Dancing Stage EuroMIX"),
]

# ZIv "First Appearance" strings -> the mix names build_data.py uses.
ORIGIN_MAP = [
    (r"^Dance ?Dance ?Revolution WORLD", "DDR WORLD"),
    (r"^Dance ?Dance ?Revolution A3", "DDR A3"),
    (r"^Dance ?Dance ?Revolution A20 PLUS", "DDR A20 PLUS"),
    (r"^Dance ?Dance ?Revolution A20", "DDR A20"),
    (r"^Dance ?Dance ?Revolution A\b", "DDR A"),
    (r"^Dance ?Dance ?Revolution \(2014\)|2014", "DDR (2014)"),
    (r"^Dance ?Dance ?Revolution \(2013\)|\(New\)|2013", "DDR (2013)"),
    (r"X3", "DDR X3 VS 2ndMIX"),
    (r"X2", "DDR X2"),
    (r"Dance ?Dance ?Revolution X\b", "DDR X"),
    (r"SuperNOVA ?2", "DDR SuperNOVA2"),
    (r"SuperNOVA", "DDR SuperNOVA"),
    (r"EXTREME", "DDR EXTREME"),
    (r"DDRMAX2|7thMIX", "DDRMAX2"),
    (r"DDRMAX|6thMIX", "DDRMAX"),
    (r"5thMIX", "DDR 5thMIX"),
    (r"4thMIX", "DDR 4thMIX"),
    (r"3rdMIX", "DDR 3rdMIX"),
    (r"2ndMIX", "DDR 2ndMIX"),
    (r"^Dance ?Dance ?Revolution( Internet Ranking Version)?$", "DDR 1stMIX"),
]

TAG_RE = re.compile(r"<[^>]+>")
ROW_RE = re.compile(r"<tr(?P<attrs>[^>]*)>(?P<body>.*?)</tr>", re.S)
CELL_RE = re.compile(r"<t([dh])(?P<attrs>[^>]*)>(?P<body>.*?)</t\1>", re.S)


def text(fragment):
    return html.unescape(TAG_RE.sub("", fragment)).strip()


def fetch(gameid):
    out = subprocess.run(
        ["curl", "-sfL", "-A", "Mozilla/5.0", "--max-time", "60",
         URL.format(gameid)],
        capture_output=True)
    if out.returncode != 0:
        return None
    return out.stdout.decode("utf-8", "replace")


def map_origin(raw):
    """
    Normalise a DDR release name; anything else (a crossover from IIDX, pop'n,
    jubeat, a console-only DDR, ...) is kept verbatim so the record still says
    where the song actually came from.
    """
    for pattern, name in ORIGIN_MAP:
        if re.search(pattern, raw, re.I):
            return name
    return raw.strip() or None


def parse(page):
    """Yield {name, artist, bpm, esp, csp, origin} for every song row."""
    start = page.find("Song List")
    if start < 0:
        return
    body = page[start:]
    cols = {}
    for m in ROW_RE.finditer(body):
        cells = CELL_RE.findall(m.group("body"))
        labels = [text(c[2]) for c in cells]

        # A header row re-declares the column order; remember where ESP/CSP sit.
        if all(c[0] == "h" for c in cells) and "Song Name" in labels:
            cols = {name: i for i, name in enumerate(labels)}
            continue
        if not cols or len(cells) < 5 or cells[0][0] == "h":
            continue

        # The artist cell carries colspan=2 when a song has no genre, which
        # shifts every later column left by one. Rebuild by counting spans.
        flat = []
        for kind, attrs, frag in cells:
            span = int((re.search(r'colspan="(\d+)"', attrs) or [0, 1])[1])
            flat.append(text(frag))
            flat.extend([""] * (span - 1))

        def col(key):
            i = cols.get(key)
            return flat[i] if i is not None and i < len(flat) else ""

        name = col("Song Name")
        if not name:
            continue

        def lvl(key):
            v = col(key)
            return int(v) if v.isdigit() and int(v) > 0 else None

        origin_raw = re.search(r'title="First Appearance:\s*([^"]*)"',
                               m.group("attrs"))
        songid = re.search(r'songdb\.php\?songid=(\d+)', m.group("body"))
        yield {
            "name": name,
            "artist": col("Artist"),
            "bpm": col("BPM"),
            "esp": lvl("ESP"),
            "csp": lvl("CSP"),
            "songid": songid.group(1) if songid else None,
            "origin": map_origin(html.unescape(origin_raw.group(1)))
                      if origin_raw else None,
        }


def main():
    merged, seen = [], set()
    for games, keep_levels in ((GAMES, True), (LEGACY_GAMES, False),
                               (CONSOLE_GAMES, False)):
        for gameid, label in games:
            print(f"  {label} (gameid={gameid}) ...", end=" ", flush=True)
            page = fetch(gameid)
            if not page:
                print("unavailable")
                continue
            added = 0
            for song in parse(page):
                key = song["name"].casefold()
                if key in seen:
                    continue
                seen.add(key)
                if not song["origin"]:
                    song["origin"] = label
                if not keep_levels:
                    song["esp"] = song["csp"] = None
                merged.append(song)
                added += 1
            print(f"{added} new (total {len(merged)})")

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False)
    print(f"wrote {len(merged)} songs -> {os.path.relpath(OUT, os.path.dirname(HERE))}")


if __name__ == "__main__":
    sys.exit(main())
