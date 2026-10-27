"""Marker list in, Mushaf PNGs + Timestamps_List.txt out."""
import json
import re
from dataclasses import dataclass
from pathlib import Path

from .audio import Transcriber
from .matcher import Matcher
from .mushaf import Mushaf, save_png

ROOT = Path(__file__).resolve().parent.parent


def load_config():
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    return cfg


@dataclass
class Item:
    """One place to look: seconds in the media file, and where it sits on the timeline."""
    media: str
    start: float
    duration: float
    seq_time: float = None
    name: str = ""


def hms(t):
    t = int(round(t))
    return f"{t // 3600:02d}:{t % 3600 // 60:02d}:{t % 60:02d}"


def next_output_dir(root):
    root = Path(root)
    nums = [int(m.group(1)) for p in root.glob("Arabic Reference *")
            if (m := re.fullmatch(r"Arabic Reference (\d+)", p.name))]
    return root / f"Arabic Reference {max(nums, default=0) + 1}"


class Bot:
    def __init__(self, cfg=None, log=print):
        self.cfg = cfg or load_config()
        self.log = log
        self.mushaf = Mushaf(self.cfg["quran_folder"], self.cfg.get("printed_offset", 1))
        self.matcher = Matcher(self.mushaf.quran)
        self.whisper = Transcriber(self.cfg.get("whisper_model", "medium"),
                                   self.cfg.get("cpu_threads", 0))

    def _listen(self, it):
        dur = it.duration if it.duration > 0.3 else self.cfg.get("default_window", 12)
        text = self.whisper.arabic(it.media, it.start - 0.6, it.start + dur + 0.8)
        match = self.matcher.find(text)
        if not match:  # marker slightly off: listen a bit wider once
            wider = self.whisper.arabic(it.media, it.start - 8, it.start + dur + 8)
            match = self.matcher.find(wider) or None
            text = text or wider
        return text, match

    def run(self, items, progress=lambda done, total: None):
        out = next_output_dir(self.cfg["output_folder"])
        results, skipped = [], []
        for k, it in enumerate(items, 1):
            when = it.seq_time if it.seq_time is not None else it.start
            self.log(f"[{k}/{len(items)}] {hms(when)} sun raha hoon…")
            text, match = self._listen(it)
            if not match:
                skipped.append({"time": hms(when), "text": text, "marker": it.name})
                self.log(f"   Quran nahi mila: {text}")
                progress(k, len(items))
                continue
            n = len(results) + 1
            label = match.label.replace(":", "-").replace(" ", "_")
            label = re.sub(r"[^\w\-]", "", label)
            fname = f"{n:02d}_{hms(when).replace(':', '-')}_Surah-{label}.png"
            mask = self.mushaf.span_image(match.first_id, match.last_id)
            files = {}
            for color in ("White", "Black"):
                path = out / color / fname
                save_png(mask, path, color.lower())
                files[color.lower()] = str(path)
            words = self.mushaf.quran.words
            arabic = " ".join(words[i].text for i in range(match.first_id, match.last_id + 1)
                              if not words[i].is_marker)
            results.append({
                "n": n, "time": hms(when), "seq_time": it.seq_time, "duration": it.duration,
                "label": match.label, "arabic": arabic, "heard": text,
                "doubt": match.ambiguous or match.score < 0.8, "marker": it.name, **files,
            })
            self.log(f"   {match.label}  {arabic}")
            progress(k, len(items))
        if results or skipped:
            self._write_list(out, results, skipped)
        return {"folder": str(out), "results": results, "skipped": skipped}

    def full_scan(self, media):
        """No markers: listen to the whole file and keep the parts that match the Quran."""
        items = []
        for start, end, text in self.whisper.arabic_segments(media):
            if self.matcher.find(text):
                items.append(Item(media, start, end - start))
        return items

    @staticmethod
    def _write_list(out, results, skipped):
        out.mkdir(parents=True, exist_ok=True)
        lines = [f"{r['n']:02d} | {r['time']} | Surah-{r['label']} | {Path(r['white']).name}"
                 + ("  (shak)" if r["doubt"] else "") for r in results]
        if skipped:
            lines += ["", "Ghair-Qurani / pehchan nahi hua (PNG nahi bani):"]
            lines += [f"{s['time']} | {s['text']}" for s in skipped]
        (out / "Timestamps_List.txt").write_text("\r\n".join(lines) + "\r\n", encoding="utf-8-sig")
