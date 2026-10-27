"""Find which Quran words were recited, from a Whisper Arabic transcript."""
import re
from collections import defaultdict
from dataclasses import dataclass

from rapidfuzz import fuzz, process

MARKS = re.compile("[ؐ-ًؚ-ٰٟۖ-ۭـ]")
FOLD = str.maketrans({
    "ٱ": "ا", "أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ة": "ه",
    "ؤ": "و", "ئ": "ي", "ء": "", "ـ": "",
})
NON_LETTER = re.compile("[^ء-ي]")


def norm(word):
    # Uthmani writes many alifs as a dagger alif (ٱلْخَٰلِقُ = الخالق); Whisper writes them in full
    word = word.replace("ىٰ", "ى").replace("ٰ", "ا")
    return NON_LETTER.sub("", MARKS.sub("", word).translate(FOLD))


@dataclass
class Match:
    first_id: int        # layout word ids, inclusive
    last_id: int
    score: float         # 0..1, share of transcript words that matched
    ambiguous: bool      # the same words appear elsewhere in the Quran too
    label: str           # e.g. "2:136-137" or "2:137 (1-3)"


class Matcher:
    def __init__(self, quran):
        self.quran = quran
        self.ids = [w.id for w in quran.words[1:] if not w.is_marker]
        self.text = [norm(quran.words[i].text) for i in self.ids]
        self.where = defaultdict(list)
        for k, t in enumerate(self.text):
            self.where[t].append(k)
        self.vocab = list(self.where)

    def _anchors(self, token, limit=40):
        hits = process.extract(token, self.vocab, scorer=fuzz.ratio, limit=limit, score_cutoff=75)
        for word, score, _ in hits:
            for k in self.where[word]:
                yield k, score / 100

    def _align(self, toks, lo, hi):
        """Local alignment of toks against self.text[lo:hi]. Returns (score, start, end, hits)."""
        ref = self.text[lo:hi]
        n, m = len(toks), len(ref)
        S = [[0.0] * (m + 1) for _ in range(n + 1)]
        B = [[None] * (m + 1) for _ in range(n + 1)]
        best = (0.0, 0, 0)
        for i in range(1, n + 1):
            for j in range(1, m + 1):
                sim = fuzz.ratio(toks[i - 1], ref[j - 1]) / 100
                diag = S[i - 1][j - 1] + (2 * sim - 1 if sim >= 0.6 else -1.0)
                up = S[i - 1][j] - 0.6      # extra word in the transcript
                left = S[i][j - 1] - 0.8    # Quran word Whisper missed
                v = max(0.0, diag, up, left)
                S[i][j] = v
                B[i][j] = "d" if v == diag else "u" if v == up else "l" if v == left else None
                if v > best[0]:
                    best = (v, i, j)
        score, i, j = best
        end = j
        hits = 0
        while i > 0 and j > 0 and B[i][j]:
            step = B[i][j]
            if step == "d":
                if fuzz.ratio(toks[i - 1], ref[j - 1]) >= 60:
                    hits += 1
                i, j = i - 1, j - 1
            elif step == "u":
                i -= 1
            else:
                j -= 1
        return score, lo + j, lo + end - 1, hits

    def find(self, transcript):
        toks = [t for t in (norm(w) for w in transcript.split()) if t]
        if not toks:
            return None
        n = len(toks)
        starts = set()
        for i, tok in enumerate(toks[: min(n, 6)]):
            if len(tok) < 2:
                continue
            for k, _ in self._anchors(tok):
                starts.add(max(0, k - i))
        if not starts:
            return None
        results = []
        for s in starts:
            lo, hi = max(0, s - 3), min(len(self.text), s + n + 8)
            score, a, b, hits = self._align(toks, lo, hi)
            if hits:
                results.append((score, hits, a, b))
        if not results:
            return None
        results.sort(key=lambda r: (-r[0], r[2]))
        score, hits, a, b = results[0]
        same = {(r[2] - r[3]) for r in results if abs(r[0] - score) < 1e-6 and r[2] != a}
        share = hits / n
        letters = sum(len(t) for t in self.text[a:b + 1])
        if share < 0.6 or (hits == 1 and letters < 5):
            return None
        first_id, last_id = self.ids[a], self.ids[b]
        last_word = self.quran.words[last_id]
        if self.quran.words[last_id + 1].is_marker:   # whole ayah end: keep the ۝
            last_id += 1
        return Match(first_id, last_id, share, bool(same), self.label(first_id, last_word.id))

    def label(self, first_id, last_id):
        w0, w1 = self.quran.words[first_id], self.quran.words[last_id]
        f0, _ = self.quran.ayah_range(w0.surah, w0.ayah)
        _, l1 = self.quran.ayah_range(w1.surah, w1.ayah)
        whole = first_id == f0 and last_id >= l1 - 1
        if (w0.surah, w0.ayah) == (w1.surah, w1.ayah):
            base = f"{w0.surah}:{w0.ayah}"
            return base if whole else f"{base} ({w0.pos}-{w1.pos})"
        if w0.surah == w1.surah:
            base = f"{w0.surah}:{w0.ayah}-{w1.ayah}"
        else:
            base = f"{w0.surah}:{w0.ayah}-{w1.surah}:{w1.ayah}"
        return base if whole else f"{base} (words {w0.pos}..{w1.pos})"
