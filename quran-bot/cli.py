"""Use the bot without Premiere.

  python cli.py lecture.wav --color mauve     only markers of one colour (exported WAV)
  python cli.py lecture.wav --all-markers     every marker in the WAV
  python cli.py lecture.mp4 --full            no markers: listen to the whole file
  python cli.py --colors lecture.wav          list the marker colours in the WAV
"""
import argparse

from quran_bot.audio import wav_markers
from quran_bot.pipeline import Bot, Item

COLORS = {"mauve": 0xFFB18BAF, "green": 0xFF378671}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("media")
    ap.add_argument("--color", help="marker colour name (mauve, green) or ARGB number")
    ap.add_argument("--all-markers", action="store_true")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--colors", action="store_true")
    a = ap.parse_args()

    if a.colors:
        counts = {}
        for m in wav_markers(a.media):
            counts[m["color"]] = counts.get(m["color"], 0) + 1
        names = {v: k for k, v in COLORS.items()}
        for c, n in counts.items():
            print(f"{names.get(c, hex(c) if c else '?')}: {n} markers")
        return

    bot = Bot()
    if a.full:
        items = bot.full_scan(a.media)
    else:
        marks = wav_markers(a.media)
        if a.color:
            want = COLORS.get(a.color.lower()) or int(a.color, 0)
            marks = [m for m in marks if m["color"] == want]
        elif not a.all_markers:
            ap.error("--color, --all-markers ya --full mein se ek chuniye")
        items = [Item(a.media, m["start"], m["duration"], m["start"], m["name"]) for m in marks]
    print(f"{len(items)} jagah check hongi")
    out = bot.run(items)
    print(f"\n{len(out['results'])} PNG bani: {out['folder']}")


if __name__ == "__main__":
    main()
