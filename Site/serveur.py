"""Serveur local du site Blood and Silver — Archives.

Comme python -m http.server, mais avec les requêtes « Range » (lecture partielle), indispensables
pour avancer / reculer dans les vidéos et les sons. Sert le dossier parent (E:\\Projets\\BloodAndSilver)
pour que le site accède aux animations, textures, etc.
Usage : python serveur.py [port]
"""
import os, re, sys, webbrowser, threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8777

class Handler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, ".webp": "image/webp", ".ogg": "audio/ogg",
                      ".vtt": "text/vtt", ".mp4": "video/mp4", ".js": "text/javascript", ".skel": "application/octet-stream"}

    def __init__(self, *a, **k):
        super().__init__(*a, directory=ROOT, **k)

    def log_message(self, *a):  # silencieux
        pass

    def send_head(self):
        rng = self.headers.get("Range")
        path = self.translate_path(self.path)
        if not rng or not os.path.isfile(path):
            return super().send_head()
        m = re.match(r"bytes=(\d*)-(\d*)", rng)
        size = os.path.getsize(path)
        start = int(m.group(1)) if m and m.group(1) else 0
        end = int(m.group(2)) if m and m.group(2) else size - 1
        if m and not m.group(1) and m.group(2):  # bytes=-N : N derniers octets
            start, end = size - int(m.group(2)), size - 1
        end = min(end, size - 1)
        if start > end or start >= size:
            self.send_response(416); self.send_header("Content-Range", f"bytes */{size}"); self.end_headers(); return None
        f = open(path, "rb"); f.seek(start)
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()
        self._remaining = end - start + 1
        return f

    def copyfile(self, source, outputfile):
        n = getattr(self, "_remaining", None)
        if n is None:
            return super().copyfile(source, outputfile)
        try:
            while n > 0:
                buf = source.read(min(1 << 16, n))
                if not buf: break
                outputfile.write(buf); n -= len(buf)
        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
            pass  # le navigateur a annulé la requête (déplacement dans la vidéo)

    def end_headers(self):
        if not self.headers.get("Range"):
            self.send_header("Accept-Ranges", "bytes")
        super().end_headers()

class ExclusiveServer(ThreadingHTTPServer):
    """Sous Windows, http.server autorise plusieurs serveurs sur le même port (SO_REUSEADDR) :
    on exige un accès exclusif pour qu'un port déjà pris soit bien détecté."""
    allow_reuse_address = False
    daemon_threads = True
    def server_bind(self):
        import socket
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()

if __name__ == "__main__":
    # si le port est déjà pris (autre serveur, ancienne fenêtre), on essaie les suivants
    srv = None
    for port in range(PORT, PORT + 20):
        try:
            srv = ExclusiveServer(("127.0.0.1", port), Handler); break
        except OSError:
            print(f"Port {port} déjà utilisé, essai du suivant…")
    if srv is None:
        sys.exit("Aucun port libre trouvé entre %d et %d." % (PORT, PORT + 19))
    url = f"http://localhost:{port}/Site/"
    print(f"Blood and Silver — Archives : {url}\n(fermez cette fenêtre pour arrêter le serveur)")
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    srv.serve_forever()
