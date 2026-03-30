"""Lightweight HTTP wrapper around the MediaInfo CLI for audio/video analysis."""

import json
import subprocess
import tempfile
import os
from http.server import HTTPServer, BaseHTTPRequestHandler


class MediaInfoHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "healthy"}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if not self.path.startswith("/mediainfo/"):
            self.send_response(404)
            self.end_headers()
            return

        filename = os.path.basename(self.path.split("/mediainfo/", 1)[1])
        if not filename:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "filename is required"}).encode())
            return
        content_length = int(self.headers.get("Content-Length", 0))
        file_bytes = self.rfile.read(content_length)

        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{filename}") as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        try:
            result = subprocess.run(
                ["mediainfo", "--Output=JSON", tmp_path],
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(result.stdout.encode())
        except subprocess.TimeoutExpired:
            self.send_response(504)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "MediaInfo timed out"}).encode())
        finally:
            os.unlink(tmp_path)


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 8081), MediaInfoHandler)
    print("MediaInfo server listening on port 8081")
    server.serve_forever()
