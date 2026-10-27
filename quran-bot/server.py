"""Local server for the Premiere panel. Run start_bot.bat and keep the window open.

POST /jobs     {"items": [{"media", "start", "duration", "seq_time", "name"}]} -> {"id"}
GET  /jobs/ID  -> {"state": "queued|running|done|error", "done", "total", "log", "result"}
GET  /health   -> {"ok": true}
"""
import json
import queue
import threading
import traceback
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from quran_bot.pipeline import Bot, Item, load_config

CFG = load_config()
JOBS = {}
WORK = queue.Queue()
_bot = None


def worker():
    global _bot
    while True:
        jid = WORK.get()
        job = JOBS[jid]
        job["state"] = "running"

        def log(msg):
            print(msg, flush=True)
            job["log"].append(msg)

        try:
            if _bot is None:
                log("Mushaf aur Whisper load ho rahe hain (pehli dafa model download hoga)…")
                _bot = Bot(CFG, log)
            _bot.log = log
            items = [Item(i["media"], float(i["start"]), float(i.get("duration") or 0),
                          i.get("seq_time"), i.get("name", "")) for i in job["items"]]
            job["total"] = len(items)

            def progress(done, total):
                job["done"] = done

            job["result"] = _bot.run(items, progress)
            job["state"] = "done"
            log(f"Mukammal: {len(job['result']['results'])} PNG — {job['result']['folder']}")
        except Exception as e:
            job["state"] = "error"
            log(f"Error: {e}")
            traceback.print_exc()


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body):
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self._send(204, {})

    def do_GET(self):
        if self.path == "/health":
            return self._send(200, {"ok": True})
        if self.path.startswith("/jobs/"):
            job = JOBS.get(self.path.split("/")[-1])
            if not job:
                return self._send(404, {"error": "job nahi mila"})
            return self._send(200, {k: v for k, v in job.items() if k != "items"})
        self._send(404, {"error": "?"})

    def do_POST(self):
        if self.path != "/jobs":
            return self._send(404, {"error": "?"})
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        jid = uuid.uuid4().hex[:8]
        JOBS[jid] = {"state": "queued", "done": 0, "total": len(body.get("items", [])),
                     "log": [], "result": None, "items": body.get("items", [])}
        WORK.put(jid)
        self._send(200, {"id": jid})

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    threading.Thread(target=worker, daemon=True).start()
    port = CFG.get("port", 8765)
    print(f"Quran Bot chal raha hai: http://127.0.0.1:{port}  (yeh window band na karein)")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
