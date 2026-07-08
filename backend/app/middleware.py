"""Request logging middleware for structured logging of all requests.

Logs timestamp, endpoint, response status, and response time for all requests.
Also provides structured JSON logging for trade decisions.
"""
import json
import time
import logging
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all requests with structured JSON logging."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and log with structured data."""
        start_time = time.time()

        # Process the request
        response = await call_next(request)

        # Calculate response time
        process_time = time.time() - start_time
        process_time_ms = process_time * 1000

        # Build structured log entry
        log_entry = {
            "timestamp": start_time,
            "endpoint": f"{request.method} {request.url.path}",
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "response_time_ms": round(process_time_ms, 2),
            "client_host": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
        }

        # Log with structured data
        logger.info(json.dumps(log_entry, default=str))

        return response
