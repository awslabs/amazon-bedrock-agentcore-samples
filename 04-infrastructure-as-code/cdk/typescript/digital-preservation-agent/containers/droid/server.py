"""Lightweight HTTP wrapper around the DROID CLI for format profiling."""

import json
import subprocess
import tempfile
import os
import csv
from http.server import HTTPServer, BaseHTTPRequestHandler


class DroidHandler(BaseHTTPRequestHandler):
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
        if not self.path.startswith("/api/identify/"):
            self.send_response(404)
            self.end_headers()
            return

        filename = os.path.basename(self.path.split("/api/identify/", 1)[1])
        if not filename:
            self._respond(400, {"error": "filename is required"})
            return
        content_length = int(self.headers.get("Content-Length", 0))
        file_bytes = self.rfile.read(content_length)

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, filename)
            profile_path = os.path.join(tmpdir, "profile.droid")
            export_path = os.path.join(tmpdir, "export.csv")

            with open(file_path, "wb") as f:
                f.write(file_bytes)

            try:
                subprocess.run(
                    ["droid.sh", "-A", file_path, "-p", profile_path],
                    capture_output=True,
                    text=True,
                    timeout=90,
                )
                subprocess.run(
                    ["droid.sh", "-p", profile_path, "-e", export_path],
                    capture_output=True,
                    text=True,
                    timeout=90,
                )

                results = []
                if os.path.exists(export_path):
                    with open(export_path, "r") as csvfile:
                        reader = csv.DictReader(csvfile)
                        for row in reader:
                            if row.get("TYPE") == "File":
                                results.append(
                                    {
                                        "puid": row.get("PUID", ""),
                                        "format_name": row.get("FORMAT_NAME", ""),
                                        "format_version": row.get("FORMAT_VERSION", ""),
                                        "mime_type": row.get("MIME_TYPE", ""),
                                        "method": row.get("METHOD", ""),
                                        "file_size": row.get("SIZE", ""),
                                    }
                                )

                self._respond(200, {"results": results})
            except subprocess.TimeoutExpired:
                self._respond(504, {"error": "DROID timed out"})

    def _respond(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 8080), DroidHandler)
    print("DROID server listening on port 8080")
    server.serve_forever()
