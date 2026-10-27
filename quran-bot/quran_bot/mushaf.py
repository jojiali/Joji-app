"""Find words on the scanned Taj 13-line Mushaf pages and cut them out as PNGs.

How it works:
  * The layout database says which word ids sit on which page/line.
  * A page is rendered from E:\\Quran\\ChapterNN.pdf, the frame and the ruled lines
    between text lines are found, and the ink is split into connected components.
  * Each component is given to the line whose band holds its centre, so harakat that
    cross a ruled line still stay with their own line.
  * On a line, ayah markers (۝) are found by shape and used as anchors; the remaining
    gaps between letter bodies are chosen as word boundaries so that word widths fit
    the expected widths from the text.
"""
import re
import sqlite3
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

DATA = Path(__file__).resolve().parent.parent / "data"
DIACRITICS = re.compile("[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640]")

INK = 128            # gray < INK counts as ink
BODY_AREA = 600      # components at least this big are letter bodies (not harakat/dots)
MARKER_PX = 87          # ۝ is about 87 px wide at 300 dpi
MARKER_SIZE = (80, 94)
LINE_PITCH = 187.2   # at 300 dpi, 13-line page


@dataclass
class Word:
    id: int
    surah: int
    ayah: int
    pos: int          # 0 = ayah-end marker
    text: str

    @property
    def is_marker(self):
        return self.pos == 0


class Quran:
    """Word ids 1..83668 as used by the layout (quran.com numbering)."""

    def __init__(self, path=DATA / "quran_words.tsv"):
        self.words = [None]
        self.ayah_ids = {}
        for line in open(path, encoding="utf-8"):
            if line.startswith("#"):
                continue
            wid, s, a, p, text = line.rstrip("\n").split("\t")
            w = Word(int(wid), int(s), int(a), int(p), text)
            self.words.append(w)
            first, _ = self.ayah_ids.get((w.surah, w.ayah), (w.id, w.id))
            self.ayah_ids[(w.surah, w.ayah)] = (first, w.id)

    def ayah_range(self, surah, ayah, with_marker=True):
        first, last = self.ayah_ids[(surah, ayah)]
        return first, last if with_marker else last - 1


@dataclass
class Line:
    number: int
    kind: str
    first: int
    last: int
    top: int = 0
    bottom: int = 0
    comps: list = field(default_factory=list)   # (label, x0, x1, y0, y1, area)
    cuts: list = field(default_factory=list)    # x boundaries, right to left, len = items + 1


class Layout:
    def __init__(self, path=DATA / "indopak-13-lines-taj-company.db"):
        db = sqlite3.connect(path)
        self.lines = {}
        for page, num, kind, first, last in db.execute(
            "select page_number, line_number, line_type, first_word_id, last_word_id from pages"
        ):
            self.lines.setdefault(page, []).append(
                (num, kind, first or 0, last or 0)
            )
        self.word_line = {}
        for page, rows in self.lines.items():
            for num, kind, first, last in rows:
                if kind == "ayah":
                    for wid in range(first, last + 1):
                        self.word_line[wid] = (page, num)


class Book:
    """Maps printed page numbers to (pdf, page index) across ChapterNN.pdf files."""

    def __init__(self, folder, printed_offset=1):
        import pypdfium2 as pdfium

        self.pdfium = pdfium
        self.printed_offset = printed_offset
        files = []
        for f in Path(folder).glob("*.pdf"):
            m = re.fullmatch(r"chapter\s*0*(\d+)", f.stem, re.I)
            if m:
                files.append((int(m.group(1)), f))
        if not files:
            raise FileNotFoundError(f"{folder} mein Chapter01.pdf jaisi files nahi milin")
        self.chapters = []
        start = 1
        for num, f in sorted(files):
            count = len(pdfium.PdfDocument(f))
            self.chapters.append((num, f, start, count))
            start += count

    def locate(self, layout_page):
        printed = layout_page + self.printed_offset
        for num, f, start, count in self.chapters:
            if start <= printed < start + count:
                return f, printed - start
        raise LookupError(f"Mushaf page {printed} kisi Chapter PDF mein nahi mila")

    def render(self, layout_page, dpi=300):
        f, idx = self.locate(layout_page)
        doc = self.pdfium.PdfDocument(f)
        img = doc[idx].render(scale=dpi / 72, grayscale=True).to_pil().convert("L")
        if img.size != (2250, 3150):
            img = img.resize((2250, 3150), Image.LANCZOS)
        return np.asarray(img) < INK


def _clusters(idx):
    out = []
    for i in idx:
        if out and i - out[-1][1] <= 2:
            out[-1][1] = i
        else:
            out.append([i, i])
    return out


def _edge(idx, from_end=False, reach=60):
    """Inner edge of a (double) border: the clusters nearest the page edge."""
    cl = _clusters(idx)
    if from_end:
        cl = [[-b, -a] for a, b in reversed(cl)]
    group = [c for c in cl if c[0] - cl[0][1] <= reach]
    inner = group[-1][1]
    return -inner if from_end else inner


def find_frame(ink, n_lines=13):
    H, W = ink.shape
    if n_lines < 13:
        return _opening_frame(ink, n_lines)
    cols = np.where(ink.mean(0) > 0.5)[0]
    rows = np.where(ink.mean(1) > 0.5)[0]
    left = [c for c in cols if c < W * 0.25]
    right = [c for c in cols if c > W * 0.75]
    top = [r for r in rows if r < H * 0.2]
    bottom = [r for r in rows if r > H * 0.8]
    x0 = _edge(left) + 1 if left else int(W * 0.12)
    x1 = _edge(right, True) if right else int(W * 0.88)
    y0 = _edge(top) + 1 if top else int(H * 0.11)
    y1 = _edge(bottom, True) if bottom else int(H * 0.89)
    return x0, x1, y0, y1


def _opening_frame(ink, n_lines):
    """The two opening pages (Fatiha, start of Baqarah): a big ornament on top and a
    short text box under it. The text box ends at the first ruled line of the bottom
    border; the frame top is set so that n_lines fit at the normal pitch. The ornament
    falls on the surah-name line, which is never cropped."""
    H, W = ink.shape
    rows = np.where(ink[:, int(W * 0.2):int(W * 0.8)].mean(1) > 0.5)[0]
    bottom = [r for r in rows if r > H * 0.8]
    y1 = _clusters(bottom)[0][0] if bottom else int(H * 0.83)
    text_top = int(y1 - (n_lines - 1) * LINE_PITCH)
    cols = np.where(ink[text_top:y1].mean(0) > 0.5)[0]
    left = [c for c in cols if c < W * 0.3]
    right = [c for c in cols if c > W * 0.7]
    x0 = max(left) + 1 if left else int(W * 0.15)
    x1 = min(right) if right else int(W * 0.85)
    y0 = int(y1 - n_lines * LINE_PITCH)
    return x0, x1, y0, y1


def find_bands(ink, frame, n_lines):
    """Return [(top, bottom)] for each text line, split at the ruled lines."""
    x0, x1, y0, y1 = frame
    row = ink[:, x0:x1].mean(1)
    pitch = (y1 - y0) / n_lines
    bounds = [y0]
    for k in range(1, n_lines):
        b = int(round(y0 + k * pitch))
        win = row[b - 14:b + 15]
        peak = int(np.argmax(win))
        bounds.append(b - 14 + peak if win[peak] > 0.5 else b)
    bounds.append(y1)
    return list(zip(bounds[:-1], bounds[1:]))


def erase_rules(ink, frame, bands):
    """Remove the ruled lines but keep letter strokes that cross them."""
    x0, x1, _, _ = frame
    out = ink.copy()
    for top, _ in bands[1:]:
        lo, hi = top - 6, top + 7
        rows = [r for r in range(lo, hi) if ink[r, x0:x1].mean() > 0.3]
        if not rows:
            continue
        r0, r1 = min(rows), max(rows)
        above, below = ink[r0 - 2, :], ink[r1 + 2, :]
        keep = above & below
        out[r0:r1 + 1, :] &= keep[None, :]
    return out


def _letters(text):
    return max(1.0, len(DIACRITICS.sub("", text).replace(" ", "")))


class Page:
    def __init__(self, ink, layout_rows, quran):
        self.quran = quran
        n_lines = max(r[0] for r in layout_rows)
        frame = find_frame(ink, n_lines)
        bands = find_bands(ink, frame, n_lines)
        clean = erase_rules(ink, frame, bands)
        x0, x1, y0, y1 = frame
        m = 8
        area = np.zeros_like(clean)
        area[y0 + 3:y1 - 3, x0 + m:x1 - m] = clean[y0 + 3:y1 - 3, x0 + m:x1 - m]
        self.labels, n = ndi.label(area, structure=np.ones((3, 3)))
        sizes = np.bincount(self.labels.ravel())
        tops = np.array([b[0] for b in bands])
        self.lines = {}
        for num, kind, first, last in sorted(layout_rows):
            t, b = bands[num - 1]
            self.lines[num] = Line(num, kind, first, last, t, b)
        ax0, ax1 = x0 + m, x1 - m
        edge = 45 if n_lines < 13 else 2   # the opening pages have a dotted inner border
        for lab, sl in enumerate(ndi.find_objects(self.labels), 1):
            if sl is None or sizes[lab] < 12:
                continue
            ys, xs = sl
            w, h = xs.stop - xs.start, ys.stop - ys.start
            # bits of the side border cut off at the text-area edge
            touches = xs.start <= ax0 + edge or xs.stop >= ax1 - edge
            if touches and (sizes[lab] < 900 or h > 0.8 * LINE_PITCH):
                continue
            # frame outlines and leftover pieces of ruled lines
            if h > 1.3 * LINE_PITCH or (w > 60 and h < 14) or (w > 600 and h < 45):
                continue
            yc = (ys.start + ys.stop) / 2
            num = int(np.searchsorted(tops, yc, side="right"))
            if num in self.lines:
                self.lines[num].comps.append(
                    (lab, xs.start, xs.stop, ys.start, ys.stop, int(sizes[lab]))
                )
        for line in self.lines.values():
            if line.kind == "ayah" and line.comps:
                self._segment(line)

    # --- word boundaries ---------------------------------------------------
    def _segment(self, line):
        items = [self.quran.words[i] for i in range(line.first, line.last + 1)]
        comps = line.comps
        expected_markers = sum(w.is_marker for w in items)
        found = []
        for c in comps:
            _, a, b, t, d, s = c
            w, h = b - a, d - t
            fill = s / (w * h)
            if not (MARKER_SIZE[0] <= w <= MARKER_SIZE[1] and MARKER_SIZE[0] <= h <= MARKER_SIZE[1]
                    and abs(w - h) <= 6 and fill < 0.28):
                continue
            # a real ۝ is a ring with the ayah number written inside it
            digits = [o for o in comps if o is not c and o[1] > a and o[2] < b and o[3] > t and o[4] < d]
            if digits:
                score = abs(w - MARKER_PX) + abs(h - MARKER_PX) + 100 * fill
                found.append((score, a, b))
        # letters like ف/ق can look ring-like; keep only the most marker-like ones
        found.sort()
        markers = sorted(((a, b) for _, a, b in found[:expected_markers]), key=lambda m: -m[1])

        def inside_marker(c):
            return any(a - 2 <= c[1] and c[2] <= b + 2 for a, b in markers)

        bodies = sorted(
            [(c[1], c[2]) for c in comps if c[5] >= BODY_AREA and not inside_marker(c)]
            + markers,
            key=lambda iv: -iv[1],
        )
        # merge overlapping intervals into blobs (right to left)
        blobs = []
        for a, b in bodies:
            if blobs and b >= blobs[-1][0] - 1:
                blobs[-1][0] = min(blobs[-1][0], a)
            else:
                blobs.append([a, b])
        right = max(c[2] for c in comps)
        left = min(c[1] for c in comps)

        marker_idx = [i for i, w in enumerate(items) if w.is_marker]
        cuts = [None] * (len(items) + 1)
        cuts[0], cuts[-1] = right, left
        if len(markers) == len(marker_idx):
            for i, (a, b) in zip(marker_idx, markers):
                cuts[i], cuts[i + 1] = b, a
        # fill the stretches between known cuts
        i = 0
        while i < len(items):
            j = i + 1
            while cuts[j] is None:
                j += 1
            if j - i > 1:
                inner = self._choose(items[i:j], cuts[i], cuts[j], blobs)
                cuts[i + 1:j] = inner
            i = j
        line.cuts = cuts

    def _choose(self, words, right, left, blobs):
        """Pick len(words)-1 cut positions between right and left (x decreasing)."""
        k = len(words)
        gaps = []  # (x position, gap width)
        inside = [bl for bl in blobs if bl[1] <= right + 1 and bl[0] >= left - 1]
        for (a1, b1), (a2, b2) in zip(inside, inside[1:]):
            if a1 > b2:
                gaps.append(((a1 + b2) / 2, a1 - b2))
        weights = np.array([_letters(w.text) if not w.is_marker else 3.0 for w in words])
        expected = weights / weights.sum() * (right - left)
        if len(gaps) < k - 1:
            pos = right - np.cumsum(expected)[:-1]
            return [int(p) for p in pos]
        span = right - left
        med = np.median([g for _, g in gaps]) or 1.0
        # DP over gaps: best[j][g] = min cost having placed j cuts, last at gap g
        G = len(gaps)
        INF = float("inf")
        best = np.full((k, G), INF)
        back = np.zeros((k, G), dtype=int)

        def cost(width, exp):
            return ((width - exp) / (span / k)) ** 2

        def bonus(g):
            return 0.6 * np.log(gaps[g][1] / med + 1e-6)

        for g in range(G):
            best[1][g] = cost(right - gaps[g][0], expected[0]) - bonus(g)
        for j in range(2, k):
            for g in range(G):
                for h in range(g):
                    c = best[j - 1][h] + cost(gaps[h][0] - gaps[g][0], expected[j - 1]) - bonus(g)
                    if c < best[j][g]:
                        best[j][g], back[j][g] = c, h
        final = [best[k - 1][g] + cost(gaps[g][0] - left, expected[k - 1]) for g in range(G)]
        g = int(np.argmin(final))
        chosen = [g]
        for j in range(k - 1, 1, -1):
            g = back[j][g]
            chosen.append(g)
        return [int(gaps[g][0]) for g in reversed(chosen)]

    # --- cutting -----------------------------------------------------------
    def crop(self, line_num, first_id, last_id):
        """Ink mask for words first_id..last_id on one line, plus its line-relative top."""
        line = self.lines[line_num]
        i0, i1 = first_id - line.first, last_id - line.first
        xr, xl = line.cuts[i0], line.cuts[i1 + 1]
        pick = [c for c in line.comps if xl <= (c[1] + c[2]) / 2 < xr]
        if not pick:
            return None, 0
        x0 = min(c[1] for c in pick); x1 = max(c[2] for c in pick)
        y0 = min(c[3] for c in pick); y1 = max(c[4] for c in pick)
        sub = self.labels[y0:y1, x0:x1]
        mask = np.isin(sub, [c[0] for c in pick])
        return mask, y0 - line.top


class Mushaf:
    def __init__(self, pdf_folder, printed_offset=1):
        self.quran = Quran()
        self.layout = Layout()
        self.book = Book(pdf_folder, printed_offset)
        self._page = lru_cache(maxsize=8)(self._load_page)

    def _load_page(self, page):
        return Page(self.book.render(page), self.layout.lines[page], self.quran)

    def where(self, word_id):
        return self.layout.word_line[word_id]

    def span_image(self, first_id, last_id, gap=45, pad=30):
        """One-line ink mask for word ids first..last (may run over lines/pages)."""
        pieces = []
        wid = first_id
        while wid <= last_id:
            page, num = self.where(wid)
            p = self._page(page)
            line = p.lines[num]
            end = min(last_id, line.last)
            mask, rel_top = p.crop(num, wid, end)
            if mask is not None:
                pieces.append((mask, rel_top))
            wid = end + 1
            while wid <= last_id and wid not in self.layout.word_line:
                wid += 1
        if not pieces:
            raise ValueError("crop khaali aaya")
        top = min(t for _, t in pieces)
        bottom = max(t + m.shape[0] for m, t in pieces)
        width = sum(m.shape[1] for m, _ in pieces) + gap * (len(pieces) - 1)
        canvas = np.zeros((bottom - top + 2 * pad, width + 2 * pad), dtype=bool)
        x = canvas.shape[1] - pad
        for m, t in pieces:  # first piece goes on the right
            x -= m.shape[1]
            y = t - top + pad
            canvas[y:y + m.shape[0], x:x + m.shape[1]] |= m
            x -= gap
        return canvas


def save_png(mask, path, color):
    rgb = (255, 255, 255) if color == "white" else (0, 0, 0)
    h, w = mask.shape
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    arr[..., :3] = rgb
    arr[..., 3] = mask * 255
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(arr, "RGBA").save(path)
