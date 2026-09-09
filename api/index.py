"""Vercel entry point for the deliberately ephemeral simulation demo.

The domain service stays in ``server.Handler`` so local and Vercel request
handling use the same authorization and safety checks.
"""
from server import Handler


class handler(Handler):
    pass
