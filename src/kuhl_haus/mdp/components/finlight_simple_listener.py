"""Simplified Finlight WebSocket listener for real-time news article ingestion.

Uses the exact pattern verified to work with the Finlight SDK:
- Sync on_article callback (SDK calls it synchronously)
- WebSocketOptions(takeover=True) / RawWebSocketOptions(takeover=True) to
  prevent multi-session conflicts
- includeEntities=True on enhanced (non-raw) subscription for entity tagging

Serializes each incoming article to JSON and publishes to the RabbitMQ
news queue via FinlightDataQueues.
"""
import asyncio
import logging
from typing import Optional, List

from finlight_client import FinlightApi, ApiConfig, WebSocketOptions, RawWebSocketOptions
from finlight_client.models import GetArticlesWebSocketParams, GetRawArticlesWebSocketParams

from kuhl_haus.mdp.components.finlight_data_queues import FinlightDataQueues
from kuhl_haus.mdp.helpers.serde import to_dict


class FinlightSimpleListener:
    """Simplified Finlight WebSocket listener that publishes articles to RabbitMQ.

    Mirrors the pattern from the verified working Finlight SDK examples:
    - Sync on_article callback scheduled onto the event loop via create_task
    - WebSocketOptions(takeover=True) to avoid session conflicts
    - includeEntities=True for entity-tagged articles (enhanced mode)

    Lifecycle: call start() to connect and begin consuming. Call stop() to
    disconnect. Designed to run as a background asyncio task.
    """

    def __init__(
        self,
        api_key: str,
        queues: FinlightDataQueues,
        raw: bool = False,
        include_entities: bool = True,
    ):
        self.logger = logging.getLogger(__name__)

        self.api_key = api_key
        self.queues = queues
        self.raw = raw
        self.include_entities = include_entities
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self.connection_status = {
            "connected": False,
            "healthy": False,
            "articles_received": 0,
            "errors": 0,
        }
        if raw:
            self.finlight_api = FinlightApi(
                config=ApiConfig(api_key=self.api_key),
                raw_websocket_options=RawWebSocketOptions(takeover=True),
            )
            self.finlight_params = GetRawArticlesWebSocketParams(
                language="en"
            )
        else:
            self.finlight_api = FinlightApi(
                config=ApiConfig(api_key=self.api_key),
                websocket_options=WebSocketOptions(takeover=True),
            )
            self.finlight_params = GetArticlesWebSocketParams(
                language="en",
                includeEntities=include_entities
            )

    async def start(self):
        """Connect to Finlight WebSocket and begin publishing articles to RabbitMQ."""
        self._running = True
        self._task = asyncio.create_task(self._run())
        self.logger.info("FinlightSimpleListener started.")

    async def stop(self):
        """Disconnect and cancel the background task."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self.connection_status["connected"] = False
        self.connection_status["healthy"] = False
        self.logger.info("FinlightSimpleListener stopped.")

    async def _run(self):
        """Main loop: connect and stream articles. Reconnects on disconnect."""
        loop = asyncio.get_event_loop()

        while self._running:
            try:
                self.logger.info("Connecting to Finlight WebSocket...")

                def on_article(article):
                    loop.create_task(self._handle_article(article))
                if self.raw:
                    self.connection_status["connected"] = True
                    self.connection_status["healthy"] = True
                    await self.finlight_api.raw_websocket.connect(
                        request_payload=self.finlight_params,
                        on_article=on_article,
                    )
                else:
                    self.connection_status["connected"] = True
                    self.connection_status["healthy"] = True
                    await self.finlight_api.websocket.connect(
                        request_payload=self.finlight_params,
                        on_article=on_article,
                    )

                # Disconnected cleanly
                self.connection_status["connected"] = False
                self.logger.info("Finlight WebSocket disconnected.")

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.connection_status["connected"] = False
                self.connection_status["healthy"] = False
                self.connection_status["errors"] += 1
                self.logger.error(f"FinlightSimpleListener error: {e}", exc_info=True)
                if self._running:
                    self.logger.info("Reconnecting in 5s...")
                    await asyncio.sleep(5)

    async def _handle_article(self, article):
        """Serialize and publish a single article to RabbitMQ."""
        try:
            self.connection_status["articles_received"] += 1
            await self.queues.handle_message(to_dict(article))
            self.logger.debug(f"Article published: {getattr(article, 'headline', str(article))[:80]}")
        except Exception as e:
            self.connection_status["errors"] += 1
            self.logger.error(f"Failed to publish article: {e}", exc_info=True)
