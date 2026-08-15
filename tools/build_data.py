#!/usr/bin/env python3
"""
Build data/records.json for the DDR Score Tracker web app.

    python3 tools/build_data.py "<path to the .xlsx>"          # rebuild records
    python3 tools/build_data.py --refresh-songdb               # re-pull song db
    python3 tools/build_data.py "<xlsx>" --jackets             # + fetch artwork
    python3 tools/build_data.py "<xlsx>" --report              # list non-matches

SOURCE WORKBOOK
    A single sheet laid out as an A-Z grid. Every populated cell from row 5 down
    is one PFC'd chart, written as three lines:

        Song Name
        ESP | CSP
        30p

    `30p` is the number of Perfect judgements in that full combo. `0p` would be
    an MFC. A cell like `33p / 12p` is an improvement history; the best (lowest)
    value is treated as the current record.

SCORING
    Modern DDR (X onwards) awards 1,000,000 / N per scoring target, and a Perfect
    is worth exactly 10 points less than a Marvelous. On a Perfect Full Combo the
    Perfects are the only deduction, so the note count cancels out entirely:

        score = 1,000,000 - 10 x perfects

    So `30p` is exactly 999,700 and `1p` is exactly 999,990. No estimation.

SONG METADATA
    Level and origin mix are not in the workbook. They are joined in from the
    DDRCardDraw community datasets (github.com/noahm/DDRCardDraw), merged across
    every DDR release file so that songs long since removed from the arcade are
    still resolvable. Anything that still cannot be matched is kept with a null
    level and can be corrected by hand in tools/overrides.json.
"""

import argparse
import json
import os
import re
import struct
import subprocess
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SONGDB_PATH = os.path.join(HERE, "songdb.json")
OVERRIDES_PATH = os.path.join(HERE, "overrides.json")
SITE_PATH = os.path.join(HERE, "site.json")
OUT_PATH = os.path.join(ROOT, "data", "records.json")
JACKET_DIR = os.path.join(ROOT, "assets", "img", "jackets")
PROOF_DIR = os.path.join(ROOT, "assets", "img", "proof")
BANNER_DIR = os.path.join(ROOT, "assets", "img", "banners")
BANNER_INDEX = os.path.join(HERE, "banners.json")
PROOF_EXTS = (".jpg", ".jpeg", ".png", ".webp")

GH_RAW = "https://raw.githubusercontent.com/noahm/DDRCardDraw/main"
ZIV = "https://zenius-i-vanisher.com"
# Newest first: the first file that mentions a song wins, so a song still in the
# current mix keeps its current levels.
SONG_FILES = [
    "ddr_world", "a3", "a20plus", "ddr_grand_prix",
    "ddr_x3", "ddr_x", "ddr_sn", "extreme",
]

DIFFS = {"ESP": "expert", "CSP": "challenge"}

# DDRCardDraw folder strings -> (canonical mix name, chronological order).
# Order doubles as the sort key for the "origin" filter in the UI.
MIXES = [
    ("DDR 1stMIX", 1, ["DanceDanceRevolution 1st Mix", "DDR 1st"]),
    ("DDR 2ndMIX", 2, ["DanceDanceRevolution 2nd Mix", "DDR 2ndMIX", "DDR 2ndMix",
                       "DDR Club Ver.", "DDR club version"]),
    ("DDR 3rdMIX", 3, ["DanceDanceRevolution 3rd Mix", "DDR 3rdMIX", "DDR 3rdMix",
                       "DDR Solo", "DDR solo"]),
    ("DDR 4thMIX", 4, ["DanceDanceRevolution 4th Mix", "DDR 4thMIX", "DDR 4thMix"]),
    ("DDR 5thMIX", 5, ["DanceDanceRevolution 5th Mix", "DDR 5thMIX", "DDR 5thMix"]),
    ("DDRMAX", 6, ["DDRMAX -DanceDanceRevolution 6thMIX-", "DDRMAX"]),
    ("DDRMAX2", 7, ["DDRMAX2 -DanceDanceRevolution 7thMIX-", "DDRMAX2"]),
    ("DDR EXTREME", 8, ["DanceDanceRevolution EXTREME", "DDR EXTREME"]),
    ("DDR SuperNOVA", 9, ["DanceDanceRevolution SuperNOVA", "DDR SuperNOVA"]),
    ("DDR SuperNOVA2", 10, ["DanceDanceRevolution SuperNOVA2"]),
    ("DDR X", 11, ["DanceDanceRevolution X"]),
    ("DDR X2", 12, ["DanceDanceRevolution X2"]),
    ("DDR X3 VS 2ndMIX", 13, ["DanceDanceRevolution X3 vs 2nd MIX"]),
    ("DDR (2013)", 14, ["DanceDanceRevolution (2013)"]),
    ("DDR (2014)", 15, ["DanceDanceRevolution (2014)"]),
    ("DDR A", 16, ["DanceDanceRevolution A"]),
    ("DDR A20", 17, ["DanceDanceRevolution A20"]),
    ("DDR A20 PLUS", 18, ["DanceDanceRevolution A20 PLUS"]),
    ("DDR A3", 19, ["DanceDanceRevolution A3"]),
    ("DDR WORLD", 20, ["DanceDanceRevolution World"]),
    ("DDR GRAND PRIX", 21, ["DDR GRAND PRIX"]),
    ("Console / Other", 90, ["CS DDR", "DDR home"]),
]
FOLDER_TO_MIX = {}
for _name, _order, _folders in MIXES:
    for _f in _folders:
        FOLDER_TO_MIX[_f] = (_name, _order)
# Anything from a sibling BEMANI series (crossover songs) collapses to one bucket.
CROSSOVER = ("Other BEMANI", 91)


# --------------------------------------------------------------------------- #
# Song database
# --------------------------------------------------------------------------- #

def http_get(url, timeout=60):
    """Fetch bytes, falling back to curl where urllib's TLS stack is unhappy."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.read()
    except Exception:
        out = subprocess.run(
            ["curl", "-sfL", "--max-time", str(timeout), url],
            capture_output=True)
        if out.returncode != 0:
            raise IOError(f"GET failed: {url}")
        return out.stdout


def refresh_songdb():
    """Merge every DDR dataset in DDRCardDraw into one lean local song db."""
    merged, seen = [], set()
    for stem in SONG_FILES:
        url = f"{GH_RAW}/src/songs/{stem}.json"
        print(f"  fetching {stem}.json ...", end=" ", flush=True)
        try:
            data = json.loads(http_get(url).decode("utf-8"))
        except IOError:
            print("skipped (unavailable)")
            continue
        added = 0
        for s in data.get("songs", []):
            key = (norm(s["name"]), norm(s.get("artist", "")))
            if key in seen:
                continue
            seen.add(key)
            charts = {}
            for c in s.get("charts", []):
                if c.get("style") != "single":
                    continue
                for tag, cls in DIFFS.items():
                    if c.get("diffClass") == cls and c.get("lvl"):
                        charts[tag] = {"lvl": c["lvl"], "maxScore": c.get("maxScore")}
            merged.append({
                "name": s["name"],
                "translation": s.get("name_translation"),
                "hint": s.get("search_hint"),
                "artist": s.get("artist"),
                "bpm": s.get("bpm"),
                "folder": s.get("folder"),
                "jacket": s.get("jacket"),
                "remy": s.get("remyLink"),
                "charts": charts,
            })
            added += 1
        print(f"{added} new (total {len(merged)})")
    with open(SONGDB_PATH, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False)
    print(f"wrote {len(merged)} songs -> {os.path.relpath(SONGDB_PATH, ROOT)}")
    return merged


def load_songdb():
    if not os.path.exists(SONGDB_PATH):
        return refresh_songdb()
    with open(SONGDB_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_ziv():
    """Optional supplementary source produced by tools/fetch_ziv.py."""
    path = os.path.join(HERE, "songdb_ziv.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    out = []
    for s in raw:
        charts = {}
        if s.get("esp"):
            charts["ESP"] = {"lvl": s["esp"]}
        if s.get("csp"):
            charts["CSP"] = {"lvl": s["csp"]}
        out.append({
            "name": s["name"],
            "translation": None,
            "hint": None,
            "artist": s.get("artist") or None,
            "bpm": s.get("bpm") or None,
            "folder": None,
            "origin": s.get("origin"),
            "jacket": None,
            "songid": s.get("songid"),
            "remy": None,
            "charts": charts,
        })
    return out


def load_site():
    """Values the workbook cannot supply; see tools/site.json."""
    if not os.path.exists(SITE_PATH):
        return {}
    with open(SITE_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def load_overrides():
    if not os.path.exists(OVERRIDES_PATH):
        return {}
    with open(OVERRIDES_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    # Keys starting with "_" are notes for the reader, not song titles.
    return {norm(k): v for k, v in raw.items()
            if not k.startswith("_") and isinstance(v, dict)}


# --------------------------------------------------------------------------- #
# Name normalisation / matching
# --------------------------------------------------------------------------- #

PUNCT = str.maketrans({
    "’": "'", "‘": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", "～": "~", "〜": "~",
    "・": " ", "☆": " ", "★": " ", "♥": " ", "♡": " ",
    "♪": " ", "〇": "0",
})
CJK_RE = re.compile(r"[぀-ヿ㐀-鿿ｦ-ﾟ]")
KEEP_RE = re.compile(r"[^0-9a-z぀-ヿ㐀-鿿]+")


def norm(s):
    """Fold case, width, punctuation and spacing away for fuzzy equality."""
    s = unicodedata.normalize("NFKC", s or "").translate(PUNCT).lower()
    return KEEP_RE.sub("", s)


def strip_suffix(s):
    """Drop a trailing "(...)" / "[...]" / "~...~" qualifier."""
    return re.sub(r"\s*[\(\[~].*$", "", s).strip()


def split_romaji(title):
    """
    The workbook writes Japanese songs as "Romaji Reading 日本語タイトル"
    (and occasionally the reverse). Return (japanese_part, latin_part).
    """
    m = CJK_RE.search(title)
    if not m:
        return None, title
    latin = title[:m.start()].strip()
    jp = title[m.start():].strip()
    if not latin:
        # Japanese first: "恋 Koi (Gen Hoshino)" -> jp "恋", latin "Koi (Gen Hoshino)"
        tail = CJK_RE.search(title[::-1])
        cut = len(title) - tail.start()
        return title[:cut].strip(), title[cut:].strip() or None
    return jp, latin


def build_index(songs):
    index = {}

    def add(key, song):
        k = norm(key)
        if k and k not in index:
            index[k] = song

    for s in songs:
        add(s["name"], s)
        for extra in (s.get("translation"), s.get("hint")):
            if extra:
                add(extra, s)
        add(strip_suffix(s["name"]), s)
    return index


def candidates(title):
    jp, latin = split_romaji(title)
    out = [title]
    if jp:
        out.append(jp)
    if latin:
        out.append(latin)
    out += [strip_suffix(c) for c in list(out)]
    # "Song Name (subtitle)" where the workbook keeps romaji before the paren.
    if jp and latin:
        out.append(f"{jp} {strip_suffix(latin)}".strip())
    seen, uniq = set(), []
    for c in out:
        k = norm(c)
        if k and k not in seen:
            seen.add(k)
            uniq.append(c)
    return uniq


def lookup(index, title, difficulty=None):
    """
    Resolve a workbook title against the song index.

    Several aliases can hit different sources -- ZIv may match a full title
    exactly while DDRCardDraw only matches it with its suffix stripped. Prefer
    whichever hit actually carries a level for the chart we are looking up, and
    fall back to the closest alias otherwise.
    """
    hits = []
    for c in candidates(title):
        hit = index.get(norm(c))
        if hit is not None and hit not in hits:
            hits.append(hit)
    if not hits:
        return None

    # Order the winner first, but keep the rest: the sources are complementary
    # (ZIv has levels for removed songs, DDRCardDraw has the artwork) and
    # `merge_hits` pulls each field from whichever hit actually has it.
    if difficulty:
        for i, h in enumerate(hits):
            if (h.get("charts") or {}).get(difficulty, {}).get("lvl"):
                return [h] + hits[:i] + hits[i + 1:]
    return hits


def merge_hits(hits, difficulty):
    """Collapse candidate matches into one record, field by field, best-first."""
    def first(key):
        for h in hits:
            if h.get(key):
                return h[key]
        return None

    level = None
    for h in hits:
        lvl = (h.get("charts") or {}).get(difficulty, {}).get("lvl")
        if lvl:
            level = lvl
            break

    folder = first("folder")
    origin, origin_order = (mix_of(folder) if folder else (None, None))
    if not origin:
        origin = first("origin")
        if origin:
            origin_order = next(
                (o for n, o, _ in MIXES if n == origin), CROSSOVER[1])

    return {
        "name": hits[0]["name"],
        "translation": first("translation"),
        "artist": first("artist"),
        "bpm": first("bpm"),
        "jacket": first("jacket"),
        "remy": first("remy"),
        "level": level,
        "origin": origin,
        "originOrder": origin_order,
    }


# --------------------------------------------------------------------------- #
# Workbook reading
# --------------------------------------------------------------------------- #

def read_cells(xlsx_path):
    with zipfile.ZipFile(xlsx_path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall(f"{NS}si"):
                shared.append("".join(t.text or "" for t in si.iter(f"{NS}t")))
        sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))

    cells = {}
    for row in sheet.iter(f"{NS}row"):
        rn = int(row.get("r"))
        for c in row.findall(f"{NS}c"):
            col = re.match(r"[A-Z]+", c.get("r")).group()
            v = c.find(f"{NS}v")
            if c.get("t") == "s" and v is not None:
                val = shared[int(v.text)]
            elif c.get("t") == "inlineStr":
                val = "".join(t.text or "" for t in c.iter(f"{NS}t"))
            else:
                val = v.text if v is not None else ""
            if val and val.strip():
                cells[(col, rn)] = val
    return cells


def parse_entries(cells, first_row=5):
    out = []
    for (col, rn), val in cells.items():
        if rn < first_row:
            continue
        lines = [l.strip() for l in val.split("\n") if l.strip()]
        if not lines:
            continue
        difficulty = lines[1].strip().upper() if len(lines) > 1 else "ESP"
        if difficulty == "EXP":          # a couple of cells typo ESP as EXP
            difficulty = "ESP"
        if difficulty not in DIFFS:
            difficulty = "ESP"
        history = [int(n) for n in re.findall(r"(\d+)\s*p", lines[2], re.I)] \
            if len(lines) > 2 else []
        out.append({
            "col": col,
            "row": rn,
            "title": lines[0],
            "difficulty": difficulty,
            "perfects": min(history) if history else None,
            "history": history,
        })
    out.sort(key=lambda e: (len(e["col"]), e["col"], e["row"]))
    return out


# --------------------------------------------------------------------------- #
# Jackets
# --------------------------------------------------------------------------- #

def fetch_jackets(records):
    os.makedirs(JACKET_DIR, exist_ok=True)
    wanted = {r["jacket"] for r in records if r.get("jacket")}
    got = skipped = failed = 0
    for i, rel in enumerate(sorted(wanted), 1):
        dest = os.path.join(JACKET_DIR, rel)
        if os.path.exists(dest) and os.path.getsize(dest) > 0:
            skipped += 1
            continue
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        url = f"{GH_RAW}/src/assets/jackets/{urllib.parse.quote(rel)}"
        try:
            blob = http_get(url, timeout=30)
            if not blob:
                raise IOError(url)
            with open(dest, "wb") as f:
                f.write(blob)
            got += 1
        except Exception:
            failed += 1
            if os.path.exists(dest):
                os.remove(dest)
        if i % 100 == 0:
            print(f"  jackets {i}/{len(wanted)} ...")
    print(f"jackets: {got} downloaded, {skipped} cached, {failed} unavailable")


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

MONTHS = ["jan", "feb", "mar", "apr", "may", "jun",
          "jul", "aug", "sep", "oct", "nov", "dec"]


def workbook_date(path):
    """
    The workbook is versioned in its own filename -- "... (Aug 26 2023).xlsx".
    Prefer that over the file's mtime, which only records when the file was last
    copied around and would show a misleading "last updated" on the dashboard.
    """
    name = os.path.basename(path)
    m = re.search(r"([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})", name)
    if m and m.group(1).lower() in MONTHS:
        month = MONTHS.index(m.group(1).lower()) + 1
        try:
            return datetime(int(m.group(3)), month, int(m.group(2))).date().isoformat()
        except ValueError:
            pass
    return datetime.fromtimestamp(
        os.path.getmtime(path), tz=timezone.utc).date().isoformat()


def load_banners():
    """song title -> banner filename, populated by --banners."""
    if not os.path.exists(BANNER_INDEX):
        return {}
    with open(BANNER_INDEX, encoding="utf-8") as f:
        return json.load(f)


def png_size(blob):
    """Width/height straight out of a PNG (or JPEG) header, no image library."""
    if blob[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack(">II", blob[16:24])
        return w, h
    if blob[:2] == b"\xff\xd8":
        i = 2
        while i < len(blob) - 9:
            if blob[i] != 0xFF:
                i += 1
                continue
            marker = blob[i + 1]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3):
                h, w = struct.unpack(">HH", blob[i + 5:i + 9])
                return w, h
            i += 2 + struct.unpack(">H", blob[i + 2:i + 4])[0]
    return None, None


def fetch_banners(records, songids):
    """
    Last-resort artwork for songs with no square jacket.

    DDR only adopted square jackets around 2013; before that every song had a
    wide banner instead. ZIv still hosts those, so a song that has no jacket can
    at least show its real banner. ZIv falls back to a square game logo when a
    song has no art of its own -- those are rejected on aspect ratio, since a
    banner is always much wider than tall.
    """
    os.makedirs(BANNER_DIR, exist_ok=True)
    todo = [r for r in records if not r["jacket"] and songids.get(norm(r["title"]))]
    seen, got, cached, skipped = {}, 0, 0, 0

    for i, r in enumerate(todo, 1):
        sid = songids[norm(r["title"])]
        if sid in seen:
            r["banner"] = seen[sid]
            continue
        dest_rel = f"{sid}.png"
        dest = os.path.join(BANNER_DIR, dest_rel)
        if os.path.exists(dest) and os.path.getsize(dest) > 0:
            seen[sid] = dest_rel
            r["banner"] = dest_rel
            cached += 1
            continue
        try:
            page = http_get(f"{ZIV}/v5.2/songdb.php?songid={sid}", 30).decode("utf-8", "replace")
        except IOError:
            continue
        start = page.find("Graphics")
        if start < 0:
            skipped += 1
            continue
        m = re.search(r'<img src="(/images/songs/[^"]+)"', page[start:start + 1500])
        if not m:
            skipped += 1
            continue
        try:
            blob = http_get(ZIV + m.group(1), 30)
        except IOError:
            continue
        w, h = png_size(blob)
        if not w or not h or w / h < 1.6:
            # Square: ZIv's generic per-release logo, not this song's artwork.
            skipped += 1
            continue
        with open(dest, "wb") as f:
            f.write(blob)
        seen[sid] = dest_rel
        r["banner"] = dest_rel
        got += 1
        if i % 25 == 0:
            print(f"  banners {i}/{len(todo)} ...")

    # Remember which song got which banner, so an ordinary rebuild (without
    # --banners) still attaches the artwork already sitting on disk.
    index = load_banners()
    for r in records:
        if r.get("banner"):
            index[norm(r["title"])] = r["banner"]
    with open(BANNER_INDEX, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=1, sort_keys=True)

    print(f"banners: {got} downloaded, {cached} cached, {skipped} without artwork")


def proof_index():
    """
    Map result-screen photos to charts.

    Drop a photo in assets/img/proof named `<slug>-<esp|csp>.<ext>`, where the
    slug is the song title lowercased with everything but letters and digits
    removed -- e.g. "PARANOiA" Expert becomes `paranoia-esp.jpg`. Anything that
    does not match that shape (like the shared sample photo) is ignored, and
    those charts fall back to the placeholder in the drawer.
    """
    index = {}
    if not os.path.isdir(PROOF_DIR):
        return index
    for name in os.listdir(PROOF_DIR):
        stem, ext = os.path.splitext(name)
        if ext.lower() not in PROOF_EXTS:
            continue
        m = re.match(r"^(.*)-(esp|csp)$", stem, re.I)
        if not m:
            continue
        index[(norm(m.group(1)), m.group(2).upper())] = f"assets/img/proof/{name}"
    return index


def mix_of(folder):
    if not folder:
        return None, 99
    if folder in FOLDER_TO_MIX:
        return FOLDER_TO_MIX[folder]
    return CROSSOVER


def write_output(payload):
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print(f"wrote {os.path.relpath(OUT_PATH, ROOT)}")

    # Same payload as a plain script, so the site also works when opened
    # straight off the filesystem (file:// blocks fetch()).
    js_path = OUT_PATH[:-5] + ".js"
    with open(js_path, "w", encoding="utf-8") as f:
        f.write("/* Generated by tools/build_data.py -- do not edit by hand. */\n")
        f.write("window.DDR_DATA = ")
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")
    print(f"wrote {os.path.relpath(js_path, ROOT)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("xlsx", nargs="?", help="path to the score tracker .xlsx")
    ap.add_argument("--refresh-songdb", action="store_true")
    ap.add_argument("--jackets", action="store_true",
                    help="download song jacket artwork into assets/img/jackets")
    ap.add_argument("--banners", action="store_true",
                    help="fetch ZIv banners for songs that have no square jacket")
    ap.add_argument("--report", action="store_true",
                    help="print every song that could not be matched")
    args = ap.parse_args()

    if args.refresh_songdb:
        refresh_songdb()
    if not args.xlsx:
        return
    if not os.path.exists(args.xlsx):
        sys.exit(f"no such workbook: {args.xlsx}")

    songs = load_songdb()
    ziv = load_ziv()
    # DDRCardDraw first (it has jackets and current levels); ZIv fills the gaps
    # left by songs that have since been removed from the arcade.
    index = build_index(songs + ziv)
    overrides = load_overrides()
    proofs = proof_index()
    banners = load_banners()

    entries = parse_entries(read_cells(args.xlsx))
    print(f"parsed {len(entries)} entries from {os.path.basename(args.xlsx)}")

    records, unmatched = [], []
    for e in entries:
        hits = lookup(index, e["title"], e["difficulty"])
        ov = overrides.get(norm(e["title"])) or {}

        title, title_alt = e["title"], None
        level = origin = origin_order = jacket = artist = bpm = remy = None

        if hits:
            song = merge_hits(hits, e["difficulty"])
            title = song["name"]
            title_alt = song["translation"]
            level = song["level"]
            origin, origin_order = song["origin"], song["originOrder"]
            jacket, artist = song["jacket"], song["artist"]
            bpm, remy = song["bpm"], song["remy"]
        else:
            unmatched.append(e["title"])
            jp, latin = split_romaji(e["title"])
            if jp and latin:
                title, title_alt = jp, latin

        level = ov.get("level", level)
        origin = ov.get("origin", origin)
        if ov.get("origin"):
            origin_order = next(
                (o for n, o, _ in MIXES if n == ov["origin"]), origin_order)

        perfects = e["perfects"]
        score = None if perfects is None else 1_000_000 - 10 * perfects

        records.append({
            "title": title,
            "titleAlt": title_alt if title_alt and norm(title_alt) != norm(title) else None,
            "source": e["title"],
            "artist": artist,
            "bpm": bpm,
            "difficulty": e["difficulty"],
            "level": level,
            "perfects": perfects,
            "history": e["history"] if len(e["history"]) > 1 else [],
            "score": score,
            "origin": origin,
            "originOrder": origin_order if origin_order is not None else 99,
            "jacket": jacket,
            "banner": None if jacket else banners.get(norm(title)),
            "remy": remy,
            "proof": proofs.get((norm(title), e["difficulty"]))
                     or proofs.get((norm(e["title"]), e["difficulty"])),
            "matched": bool(hits),
        })

    records.sort(key=lambda r: (norm(r["title"]), r["difficulty"]))

    matched = sum(1 for r in records if r["matched"])
    levelled = sum(1 for r in records if r["level"])
    print(f"matched {matched}/{len(records)} songs "
          f"({levelled} with a chart level, {len(records) - levelled} without)")
    if args.report and unmatched:
        print("\nunmatched (add to tools/overrides.json to fill in by hand):")
        for u in sorted(set(unmatched)):
            print("   ", u)

    updated = workbook_date(args.xlsx)
    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sourceFile": os.path.basename(args.xlsx),
        "sourceUpdated": updated,
        "site": load_site(),
        "mixes": [{"name": n, "order": o} for n, o, _ in MIXES]
                 + [{"name": CROSSOVER[0], "order": CROSSOVER[1]}],
        "records": records,
    }
    write_output(payload)

    if args.jackets:
        fetch_jackets(records)

    if args.banners:
        songids = {}
        for s in ziv:
            if s.get("songid"):
                songids.setdefault(norm(s["name"]), s["songid"])
        fetch_banners(records, songids)
        # Re-emit now that records carry their banner paths.
        write_output(payload)


if __name__ == "__main__":
    sys.exit(main())
