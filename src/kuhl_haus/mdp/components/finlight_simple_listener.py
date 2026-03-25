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
import json
import logging
from typing import Optional, List

from finlight_client import FinlightApi, ApiConfig, WebSocketOptions, RawWebSocketOptions
from finlight_client.models import GetArticlesWebSocketParams, GetRawArticlesWebSocketParams

from kuhl_haus.mdp.components.finlight_data_queues import FinlightDataQueues
from kuhl_haus.mdp.helpers.observability import get_tracer

tracer = get_tracer(__name__)

logger = logging.getLogger(__name__)


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
        query: Optional[str] = None,
        tickers: Optional[List[str]] = None,
        sources: Optional[List[str]] = None,
        language: Optional[str] = None,
        raw: bool = False,
        include_entities: bool = True,
    ):
        self.api_key = api_key
        self.queues = queues
        self.query = query
        self.tickers = tickers
        self.sources = sources
        self.language = language
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

    async def start(self):
        """Connect to Finlight WebSocket and begin publishing articles to RabbitMQ."""
        self._running = True
        self._task = asyncio.create_task(self._run())
        logger.info("FinlightSimpleListener started.")

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
        logger.info("FinlightSimpleListener stopped.")

    async def _run(self):
        """Main loop: connect and stream articles. Reconnects on disconnect."""
        loop = asyncio.get_event_loop()

        while self._running:
            try:
                logger.info("Connecting to Finlight WebSocket...")

                if self.raw:
                    client = FinlightApi(
                        config=ApiConfig(api_key=self.api_key),
                        raw_websocket_options=RawWebSocketOptions(takeover=True),
                    )
                    params = GetRawArticlesWebSocketParams(
                        query=self.query,
                        sources=self.sources,
                        language=self.language,
                    )

                    def on_article(article):
                        loop.create_task(self._handle_article(article))

                    self.connection_status["connected"] = True
                    self.connection_status["healthy"] = True
                    await client.raw_websocket.connect(
                        request_payload=params,
                        on_article=on_article,
                    )
                else:
                    client = FinlightApi(
                        config=ApiConfig(api_key=self.api_key),
                        websocket_options=WebSocketOptions(takeover=True),
                    )
                    params = GetArticlesWebSocketParams(
                        query=self.query,
                        tickers=self.tickers,
                        sources=self.sources,
                        language=self.language,
                        includeEntities=self.include_entities,
                    )

                    def on_article(article):
                        loop.create_task(self._handle_article(article))

                    self.connection_status["connected"] = True
                    self.connection_status["healthy"] = True
                    await client.websocket.connect(
                        request_payload=params,
                        on_article=on_article,
                    )

                # Disconnected cleanly
                self.connection_status["connected"] = False
                logger.info("Finlight WebSocket disconnected.")

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.connection_status["connected"] = False
                self.connection_status["healthy"] = False
                self.connection_status["errors"] += 1
                logger.error(f"FinlightSimpleListener error: {e}", exc_info=True)
                if self._running:
                    logger.info("Reconnecting in 5s...")
                    await asyncio.sleep(5)

    async def _handle_article(self, article):
        """Serialize and publish a single article to RabbitMQ."""
        try:
            await self.queues.handle_message(article)
            self.connection_status["articles_received"] += 1
            logger.debug(f"Article published: {getattr(article, 'headline', str(article))[:80]}")
        except Exception as e:
            self.connection_status["errors"] += 1
            logger.error(f"Failed to publish article: {e}", exc_info=True)
