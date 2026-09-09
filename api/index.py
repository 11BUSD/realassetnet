"""Vercel entry point for the deliberately ephemeral simulation demo.

The import is intentionally delayed until request time.  Vercel's Python
runtime otherwise turns a startup exception into an opaque 500 with no usable
diagnostic in the deployment UI.
"""
import json
from http.server import BaseHTTPRequestHandler


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self._serve()

    def do_POST(self):
        self._serve()

    def _serve(self):
        try:
            from server import Handler
            # Keep the production request implementation in exactly one place.
            Handler.handle_request(self, self.command)
        except Exception as error:
            # This is intentionally non-sensitive: it identifies an import or
            # platform incompatibility without exposing credentials or files.
            payload = json.dumps({"error": "Simulation bootstrap failed", "type": type(error).__name__}).encode()
            self.send_response(503)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)
