"""
FastAPI mock backend for EA Gateway integration testing.

Provides all gateway endpoints with configurable response behaviors
(success, 4xx, 5xx, timeout, invalid JSON) and request recording.

Feature: ea-gateway
"""

import asyncio
from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI, Request, Response


@dataclass
class EndpointConfig:
    """Configurable behavior for an endpoint."""

    status_code: int = 200
    body: Any = None
    delay_seconds: float = 0.0
    return_invalid_json: bool = False


@dataclass
class RecordedRequest:
    """A recorded incoming request."""

    method: str
    path: str
    headers: dict[str, str]
    body: Any


class MockBackend:
    """
    Configurable mock backend that records all requests and allows
    per-endpoint response customization.
    """

    def __init__(self) -> None:
        self.app = FastAPI(title="EA Gateway Mock Backend")
        self.requests: list[RecordedRequest] = []
        self.endpoint_configs: dict[str, EndpointConfig] = {}
        self._default_responses: dict[str, Any] = {
            "/api/v1/market/tick": {"status": "received"},
            "/api/v1/market/candle": {"status": "received"},
            "/api/v1/health/heartbeat": {"status": "ok"},
            "/api/v1/state/transition": {
                "approved": True,
                "new_state": "CHECK_RISK",
                "command": None,
            },
            "/api/v1/trade/result": {"status": "acknowledged"},
            "/api/v1/position/status": {"status": "acknowledged"},
            "/api/v1/position/orphan": {"action": "close", "ticket": 123456789},
            "/api/v1/state/recovery": {
                "confirmed_state": "WAIT_SESSION",
                "command": None,
            },
            "/api/v1/position/known": {"positions": []},
            "/api/v1/health/mt5disconnect": {"status": "acknowledged"},
            "/api/v1/health/mt5reconnect": {"status": "acknowledged"},
        }
        self._register_routes()

    def configure_endpoint(
        self,
        path: str,
        *,
        status_code: int = 200,
        body: Any = None,
        delay_seconds: float = 0.0,
        return_invalid_json: bool = False,
    ) -> None:
        """Configure response behavior for a specific endpoint."""
        self.endpoint_configs[path] = EndpointConfig(
            status_code=status_code,
            body=body,
            delay_seconds=delay_seconds,
            return_invalid_json=return_invalid_json,
        )

    def reset(self) -> None:
        """Reset all recorded requests and endpoint configurations."""
        self.requests.clear()
        self.endpoint_configs.clear()

    def get_requests_for(self, path: str) -> list[RecordedRequest]:
        """Get all recorded requests for a specific path."""
        return [r for r in self.requests if r.path == path]

    async def _handle_request(self, request: Request, path: str) -> Response:
        """Common handler for all endpoints."""
        body = await request.json()
        headers = dict(request.headers)

        self.requests.append(
            RecordedRequest(
                method=request.method,
                path=path,
                headers=headers,
                body=body,
            )
        )

        config = self.endpoint_configs.get(path)

        if config and config.delay_seconds > 0:
            await asyncio.sleep(config.delay_seconds)

        if config and config.return_invalid_json:
            return Response(
                content="this is not valid json {{{",
                status_code=config.status_code if config else 200,
                media_type="text/plain",
            )

        if config:
            import json

            response_body = config.body if config.body is not None else self._default_responses.get(path, {})
            return Response(
                content=json.dumps(response_body),
                status_code=config.status_code,
                media_type="application/json",
            )

        # Default: 200 with default body
        import json

        default_body = self._default_responses.get(path, {})
        return Response(
            content=json.dumps(default_body),
            status_code=200,
            media_type="application/json",
        )

    def _register_routes(self) -> None:
        """Register all gateway endpoints."""

        @self.app.post("/api/v1/market/tick")
        async def market_tick(request: Request) -> Response:
            return await self._handle_request(request, "/api/v1/market/tick")

        @self.app.post("/api/v1/market/candle")
        async def market_candle(request: Request) -> Response:
            return await self._handle_request(request, "/api/v1/market/candle")

        @self.app.post("/api/v1/health/heartbeat")
        async def health_heartbeat(request: Request) -> Response:
            return await self._handle_request(request, "/api/v1/health/heartbeat")

        @self.app.post("/api/v1/state/transition")
        async def state_transition(request: Request) -> Response:
            return await self._handle_request(request, "/api/v1/state/transition")

        @self.app.post("/api/v1/trade/result")
        async def trade_result(request: Request) -> Response:
            return await self._handle_request(request, "/api/v1/trade/result")

        @self.app.post("/api/v1/position/status")
        async def position_status(request: Request) -> Response:
            return await self._handle_request(request, "/api/v1/position/status")

        @self.app.post("/api/v1/position/orphan")
        async def position_orphan(request: Request) -> Response:
            return await self._handle_request(request, "/api/v1/position/orphan")

        @self.app.post("/api/v1/state/recovery")
        async def state_recovery(request: Request) -> Response:
            return await self._handle_request(request, "/api/v1/state/recovery")

        @self.app.post("/api/v1/position/known")
        async def position_known(request: Request) -> Response:
            return await self._handle_request(request, "/api/v1/position/known")

        @self.app.post("/api/v1/health/mt5disconnect")
        async def health_mt5disconnect(request: Request) -> Response:
            return await self._handle_request(request, "/api/v1/health/mt5disconnect")

        @self.app.post("/api/v1/health/mt5reconnect")
        async def health_mt5reconnect(request: Request) -> Response:
            return await self._handle_request(request, "/api/v1/health/mt5reconnect")


def create_mock_backend() -> MockBackend:
    """Factory function to create a fresh MockBackend instance."""
    return MockBackend()
