"""Build data/quran_words.tsv from the Tanzil Uthmani text.

The Taj 13-line layout (data/indopak-13-lines-taj-company.db) refers to words by
id 1..83668, using the quran.com numbering: every word of every ayah, followed by
one id for the ayah-end marker. This script recreates that numbering so the bot
can turn a word id into surah:ayah:word and back.

Source: Tanzil Quran Text (Uthmani), https://tanzil.net — CC BY 3.0, used verbatim.
JSON copy taken from https://github.com/risan/quran-json (data/tanzil/uthmani.json).

Usage: python tools/build_words.py path/to/uthmani.json
"""
import json
import re
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
ARABIC_LETTER = re.compile("[ء-يٱ]")


def ayah_words(surah, ayah, text):
    words = [t for t in text.split() if ARABIC_LETTER.search(t)]
    # Tanzil puts the Bismillah in front of ayah 1; the layout keeps it on its own line.
    if ayah == 1 and surah not in (1, 9) and "سْمِ" in words[0]:
        words = words[4:]
    # quran.com counts "إِلْ يَاسِينَ" (37:130) as one word.
    if (surah, ayah) == (37, 130):
        words = words[:2] + [" ".join(words[2:])]
    return words


def main(src):
    data = json.load(open(src, encoding="utf-8"))
    rows = []
    wid = 0
    for surah in range(1, 115):
        for v in data[str(surah)]:
            for pos, w in enumerate(ayah_words(surah, v["verse"], v["text"]), 1):
                wid += 1
                rows.append(f"{wid}\t{surah}\t{v['verse']}\t{pos}\t{w}")
            wid += 1
            rows.append(f"{wid}\t{surah}\t{v['verse']}\t0\t")  # pos 0 = ayah-end marker

    db = sqlite3.connect(HERE / "data" / "indopak-13-lines-taj-company.db")
    (last,) = db.execute("select max(last_word_id) from pages where line_type = 'ayah'").fetchone()
    if wid != last:
        sys.exit(f"word count {wid} does not match layout ({last})")

    out = HERE / "data" / "quran_words.tsv"
    header = "# id\tsurah\tayah\tword (0 = ayah marker)\ttext — Tanzil Uthmani text, CC BY 3.0, tanzil.net\n"
    out.write_text(header + "\n".join(rows) + "\n", encoding="utf-8")
    print(f"wrote {out} ({wid} ids)")


if __name__ == "__main__":
    main(sys.argv[1])
