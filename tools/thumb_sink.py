"""Serveur temporaire (port 8778) : reçoit en POST les vignettes WebP des modèles 3D rendues par le
navigateur et les écrit dans Site/models/<cat>/<name>.webp."""
import os, json, base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

OUT = r"E:\Projets\BloodAndSilver\Site\models"

class H(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
    def do_OPTIONS(self):
        self.send_response(204); self._cors(); self.end_headers()
    def do_POST(self):
        d = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        cat, name = os.path.basename(d["cat"]), os.path.basename(d["name"])
        data = base64.b64decode(d["data"].split(",", 1)[1])
        open(os.path.join(OUT, cat, name + ".webp"), "wb").write(data)
        self.send_response(200); self._cors(); self.end_headers(); self.wfile.write(b"ok")
    def log_message(self, *a): pass

ThreadingHTTPServer(("127.0.0.1", 8778), H).serve_forever()
