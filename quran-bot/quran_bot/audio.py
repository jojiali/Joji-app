"""Audio: Premiere markers inside an exported WAV, and Whisper transcription."""
import re
import struct

SR = 16000


def wav_markers(path):
    """Markers that Premiere writes into an exported WAV (XMP in the _PMX chunk).

    Returns [{"start", "duration", "name", "comment", "color"}] in seconds; color is
    the ARGB int Premiere stores (e.g. Mauve = 0xffb18baf)."""
    xmp = None
    with open(path, "rb") as f:
        f.read(12)
        while True:
            head = f.read(8)
            if len(head) < 8:
                break
            cid, size = head[:4], struct.unpack("<I", head[4:])[0]
            pos = f.tell()
            if cid == b"_PMX":
                xmp = f.read(size).decode("utf-8", "replace")
            f.seek(pos + size + (size & 1))
    if not xmp:
        return []
    rate = 48000
    m = re.search(r"<xmpDM:frameRate>f(\d+)", xmp)
    if m:
        rate = int(m.group(1))
    part = xmp[xmp.find("<xmpDM:trackName>Markers"):]
    out = []
    # each marker holds a nested cuePointParams list, so match up to its end
    for body in re.findall(
        r'<rdf:li rdf:parseType="Resource">\s*<xmpDM:startTime>(.*?)</rdf:li>\s*</rdf:Seq>\s*</xmpDM:cuePointParams>',
        part, re.S,
    ):
        item = "<xmpDM:startTime>" + body

        def tag(name):
            t = re.search(rf"<xmpDM:{name}>(.*?)</xmpDM:{name}>", item, re.S)
            return t.group(1) if t else ""

        color = re.search(r"&quot;color&quot;:(\d+)|\"color\":(\d+)", item)
        out.append({
            "start": int(tag("startTime")) / rate,
            "duration": int(tag("duration") or 0) / rate,
            "name": tag("name"),
            "comment": tag("comment"),
            "color": int(next(g for g in color.groups() if g)) if color else None,
        })
    return out


class Transcriber:
    def __init__(self, model="medium", threads=0):
        self.model_name = model
        self.threads = threads
        self._model = None
        self._audio = {}

    @property
    def model(self):
        if self._model is None:
            from faster_whisper import WhisperModel
            self._model = WhisperModel(self.model_name, device="cpu", compute_type="int8",
                                       cpu_threads=self.threads)
        return self._model

    def audio(self, path):
        """Whole file decoded to 16 kHz mono (works for video files too)."""
        if path not in self._audio:
            from faster_whisper.audio import decode_audio
            self._audio = {path: decode_audio(path, sampling_rate=SR)}
        return self._audio[path]

    def arabic(self, path, start, end, beam=5):
        """Arabic text spoken between start and end (seconds in the media file)."""
        a = self.audio(path)
        clip = a[max(0, int(start * SR)):int(end * SR)]
        if len(clip) < SR // 4:
            return ""
        segs, _ = self.model.transcribe(clip, language="ar", beam_size=beam,
                                        condition_on_previous_text=False, vad_filter=False)
        return " ".join(s.text.strip() for s in segs)

    def arabic_segments(self, path):
        """Whole-file Arabic pass: [(start, end, text)], for lectures without markers."""
        segs, _ = self.model.transcribe(self.audio(path), language="ar", beam_size=1,
                                        condition_on_previous_text=False, vad_filter=True)
        return [(s.start, s.end, s.text.strip()) for s in segs]
