"""Vercel entry point for the deliberately ephemeral simulation demo.

The domain service stays in ``server.Handler`` so local and Vercel request
handling use the same authorization and safety checks.
"""
from http.server import BaseHTTPRequestHandler

try:
    from server import Handler
except Exception as bootstrap_error:  # pragma: no cover - Vercel bundle diagnostic
    bootstrap_error_type=type(bootstrap_error).__name__
    class handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(503)
            self.send_header('Content-Type','application/json')
            self.end_headers()
            self.wfile.write((
                '{"error":"Serverless bootstrap failed","error_type":"'+bootstrap_error_type+'"}'
            ).encode())
else:
    class handler(Handler):
        pass
