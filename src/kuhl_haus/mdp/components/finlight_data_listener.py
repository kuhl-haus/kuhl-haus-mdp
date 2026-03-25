"""WebSocket client wrapper for Finlight financial news streams.

Manages a persistent WebSocket connection to the Finlight news API, handles
reconnection logic on disconnect, and delegates incoming articles to a user-
provided handler. Designed to run as a long-lived background task that survives
temporary connection failures.

Key design decisions (mirroring FinlightSimpleListener):
- WebSocketOptions(takeover=True) to prevent multi-session conflicts
- Direct await on connect coroutine (not asyncio.gather with swallowed exceptions)
- while-loop reconnect in a single background task (no recursive start())
- includeEntities=True by default on enhanced subscriptions
- Async handler support via loop.create_task() when message_handler is a coroutine
"""
import asyncio
import inspect
import logging
from typing import Awaitable, Callable, List, Optional, Union

from finlight_client import ApiConfig, FinlightApi, WebSocketOptions, RawWebSocketOptions
from finlight_client.models import (
    GetArticlesWebSocketParams,
    GetRawArticlesWebSocketParams,
)


class FinlightDataListener:
    """Maintain Finlight WebSocket connection with auto-reconnect logic.

    Wraps the official Finlight SDK FinlightApi, providing lifecycle management
    (start/stop), connection health tracking, and automatic reconnection.
    When the WebSocket disconnects, automatically attempts to reconnect via a
    while-loop in a single background task. Delegates each incoming article to
    the provided message_handler callable.

    Supports both sync and async message handlers — async handlers are scheduled
    via loop.create_task() since the Finlight SDK calls on_article synchronously.

    Threading: Spawns a single asyncio.Task; caller is responsible for awaiting
    or managing the task lifecycle via start()/stop().
    """

    connection_status: dict
    _task: Optional[asyncio.Task]
    _query: Optional[str]
    _tickers: Optional[List[str]]
    _sources: Optional[List[str]]
    _language: Optional[str]
    raw: bool
    include_entities: bool
    max_reconnects: Optional[int]

    @property
    def query(self) -> Optional[str]:
        """Current WebSocket article query filter."""
        return self._query

    @query.setter
    def query(self, value: Optional[str]):
        self._query = value
        self.connection_status["query"] = value
        if self.connection_status.get("connected"):
            asyncio.create_task(self.restart())

    @property
    def tickers(self) -> Optional[List[str]]:
        """Current WebSocket ticker filter."""
        return self._tickers

    @tickers.setter
    def tickers(self, value: Optional[List[str]]):
        self._tickers = value
        self.connection_status["tickers"] = value
        if self.connection_status.get("connected"):
            asyncio.create_task(self.restart())

    @property
    def sources(self) -> Optional[List[str]]:
        """Current WebSocket news source filter."""
        return self._sources

    @sources.setter
    def sources(self, value: Optional[List[str]]):
        self._sources = value
        self.connection_status["sources"] = value
        if self.connection_status.get("connected"):
            asyncio.create_task(self.restart())

    @property
    def language(self) -> Optional[str]:
        """Current WebSocket language filter."""
        return self._language

    @language.setter
    def language(self, value: Optional[str]):
        self._language = value
        self.connection_status["language"] = value
        if self.connection_status.get("connected"):
            asyncio.create_task(self.restart())

    def __init__(
        self,
        api_key: str,
        message_handler: Union[
            Callable[..., Awaitable],
            Callable,
        ],
        query: Optional[str] = None,
        tickers: Optional[List[str]] = None,
        sources: Optional[List[str]] = None,
        language: Optional[str] = None,
        raw: bool = False,
        include_entities: bool = True,
        max_reconnects: Optional[int] = None,
        **kwargs,
    ):
        self.logger = logging.getLogger(__name__)
        self.api_key = api_key
        self.message_handler = message_handler
        self._query = query
        self._tickers = tickers
        self._sources = sources
        self._language = language
        self.raw = raw
        self.include_entities = include_entities
        self.max_reconnects = max_reconnects
        self.kwargs = kwargs
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self.connection_status = {
            "connected": False,
            "healthy": False,
            "language": self.language,
            "query": self.query,
            "reconnects": 0,
            "sources": self.sources,
            "tickers": self.tickers,
        }

    async def start(self):
        """Spawn the background connection task.

        Creates a single asyncio.Task that connects to Finlight and handles
        reconnection via a while-loop. Does not block.

        Side effects: Spawns asyncio.Task; updates _running flag.
        """
        if self._task and not self._task.done():
            self.logger.warning("FinlightDataListener already running; ignoring start()")
            return
        self._running = True
        self._task = asyncio.create_task(self._run())
        self.logger.info("FinlightDataListener started.")

    async def stop(self):
        """Cancel the background task and reset connection status.

        Cancels the asyncio.Task and waits for it to finish. Uses task
        cancellation rather than SDK stop() for clean async teardown.

        Side effects: Cancels asyncio.Task; updates connection_status.
        """
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        self.connection_status["connected"] = False
        self.connection_status["healthy"] = False
        self.logger.info("FinlightDataListener stopped.")

    async def restart(self):
        """Stop and restart the connection task."""
        self.logger.info("FinlightDataListener restarting...")
        await self.stop()
        await asyncio.sleep(1)
        await self.start()

    async def _run(self):
        """Connect to Finlight WebSocket and handle disconnections.

        Runs a while-loop that connects, streams articles, and reconnects on
        disconnect. Respects max_reconnects if set. Exits cleanly on
        CancelledError or when _running is set to False.

        Side effects: Network I/O (WebSocket); calls message_handler for each
        incoming article via create_task() if async, or directly if sync.
        """
        # Build FinlightApi with takeover=True to avoid session conflicts
        if self.raw:
            ws_client = FinlightApi(
                config=ApiConfig(api_key=self.api_key),
                raw_websocket_options=RawWebSocketOptions(takeover=True),
                **self.kwargs,
            )
        else:
            ws_client = FinlightApi(
                config=ApiConfig(api_key=self.api_key),
                websocket_options=WebSocketOptions(takeover=True),
                **self.kwargs,
            )

        # Build sync on_article handler (SDK calls it synchronously)
        loop = asyncio.get_event_loop()
        if inspect.iscoroutinefunction(self.message_handler):
            def on_article(article):
                loop.create_task(self.message_handler(article))
        else:
            def on_article(article):
                self.message_handler(article)

        while self._running:
            try:
                self.logger.info("Connecting to Finlight news stream...")
                self.connection_status["connected"] = True
                self.connection_status["healthy"] = True

                if self.raw:
                    params = GetRawArticlesWebSocketParams(
                        query=self._query,
                        sources=self._sources,
                        language=self._language,
                    )
                    await ws_client.raw_websocket.connect(
                        request_payload=params,
                        on_article=on_article,
                    )
                else:
                    params = GetArticlesWebSocketParams(
                        query=self._query,
                        tickers=self._tickers,
                        sources=self._sources,
                        language=self._language,
                        includeEntities=self.include_entities,
                    )
                    await ws_client.websocket.connect(
                        request_payload=params,
                        on_article=on_article,
                    )

                # Clean disconnect
                self.connection_status["connected"] = False
                self.connection_status["healthy"] = False
                self.logger.info("Disconnected from Finlight news stream.")

            except asyncio.CancelledError:
                break

            except Exception as e:
                self.connection_status["connected"] = False
                self.connection_status["healthy"] = False
                self.logger.error(
                    f"FinlightDataListener error: {e}",
                    exc_info=True,
                )

            if not self._running:
                break

            self.connection_status["reconnects"] += 1
            reconnects = self.connection_status["reconnects"]
            self.logger.info(f"Reconnection attempt {reconnects}...")

            if self.max_reconnects and reconnects >= self.max_reconnects:
                self.logger.error(
                    f"Max reconnects ({self.max_reconnects}) reached. Stopping."
                )
                break

            await asyncio.sleep(5)

        self.connection_status["connected"] = False
        self.connection_status["healthy"] = False
