"""WebSocket client wrapper for Finlight financial news streams.

Manages a persistent WebSocket connection to the Finlight news API, handles
reconnection logic on disconnect, and delegates incoming articles to a user-
provided handler. Designed to run as a long-lived background task that survives
temporary connection failures.
"""
import asyncio
import inspect
import logging
from typing import Awaitable, Callable, List, Optional, Union

from finlight_client import ApiConfig, FinlightApi
from finlight_client.models import (
    GetArticlesWebSocketParams,
    GetRawArticlesWebSocketParams,
)


class FinlightDataListener:
    """Maintain Finlight WebSocket connection with auto-reconnect logic.

    Wraps the official Finlight SDK FinlightApi, providing lifecycle management
    (start/stop/restart), connection health tracking, and automatic reconnection.
    When the WebSocket disconnects, automatically attempts to reconnect. Delegates
    each incoming article to the provided message_handler callable.

    Threading: Spawns async task for ws_connection WebSocket connect(); caller is
    responsible for awaiting or managing the task lifecycle.
    """

    connection_status: dict
    ws_connection: Union[FinlightApi, None]
    ws_coroutine: Union[asyncio.Task, None]
    _query: Optional[str]
    _tickers: Optional[List[str]]
    _sources: Optional[List[str]]
    _language: Optional[str]
    raw: bool
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
        max_reconnects: Optional[int] = 5,
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
        self.max_reconnects = max_reconnects
        self.kwargs = kwargs
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
        """Instantiate FinlightApi client and spawn connection task.

        Creates FinlightApi with configured API key, schedules async_task as a
        background task. Does not block; caller must await the task or manage it
        separately.

        Side effects: Spawns asyncio.Task; updates connection_status dict.
        """
        try:
            self.logger.info("Instantiating WebSocket client...")
            self.ws_connection = FinlightApi(
                config=ApiConfig(api_key=self.api_key),
                **self.kwargs,
            )
            self.logger.info("Scheduling WebSocket client task...")
            self.ws_coroutine = asyncio.create_task(self.async_task())
        except Exception as e:
            self.logger.error(f"Error starting WebSocket client: {e}")
            await self.stop()

    async def stop(self):
        """Shutdown WebSocket connection gracefully.

        Cancels coroutine task, stops the active WebSocket stream, and resets
        connection status. Waits 1s between steps to allow in-flight messages
        to flush.

        Side effects: Closes network socket; updates connection_status dict.
        """
        try:
            self.logger.info("Shutting down WebSocket client...")
            self.ws_coroutine.cancel()
            await asyncio.sleep(1)
            self.logger.info("stopping WebSocket stream...")
            if self.raw:
                self.ws_connection.raw_websocket.stop()
            else:
                self.ws_connection.websocket.stop()
            self.logger.info("done.")
        except Exception as e:
            self.logger.error(f"Error stopping WebSocket client: {e}")
        self.connection_status["connected"] = False
        self.ws_connection = None
        self.ws_coroutine = None

    async def restart(self):
        """Cycle connection: stop, wait 1s, start."""
        try:
            self.logger.info("Stopping WebSocket client...")
            await self.stop()
            self.logger.info("done")
            await asyncio.sleep(1)
            self.logger.info("Starting WebSocket client...")
            await self.start()
            self.logger.info("done")
        except Exception as e:
            self.logger.error(f"Error restarting WebSocket client: {e}")

    async def async_task(self):
        """Connect to Finlight WebSocket and handle disconnections.

        Calls ws_connection websocket connect() with message_handler and awaits
        it. On disconnect, reconnects immediately and increments the reconnect
        counter for observability.

        Side effects: Network I/O (WebSocket); calls message_handler for each
        incoming article.
        """
        try:
            self.logger.info("Connecting to Finlight news stream...")
            self.connection_status["connected"] = True
            self.connection_status["healthy"] = True

            # The Finlight SDK calls on_article synchronously. If message_handler
            # is a coroutine function, wrap it so it is scheduled on the running
            # event loop rather than returning an unawaited coroutine object.
            if inspect.iscoroutinefunction(self.message_handler):
                loop = asyncio.get_event_loop()

                def _sync_handler(article):
                    loop.create_task(self.message_handler(article))

                effective_handler = _sync_handler
            else:
                effective_handler = self.message_handler

            if self.raw:
                request_params = GetRawArticlesWebSocketParams(
                    query=self.query,
                    sources=self.sources,
                    language=self.language,
                )
                connect_coro = self.ws_connection.raw_websocket.connect(
                    request_payload=request_params,
                    on_article=effective_handler,
                )
            else:
                request_params = GetArticlesWebSocketParams(
                    query=self.query,
                    tickers=self.tickers,
                    sources=self.sources,
                    language=self.language,
                )
                connect_coro = self.ws_connection.websocket.connect(
                    request_payload=request_params,
                    on_article=effective_handler,
                )

            await asyncio.gather(connect_coro, return_exceptions=True)

            self.connection_status["connected"] = False
            self.logger.info("Disconnected from Finlight news stream...")
            self.connection_status["healthy"] = False
            self.connection_status["reconnects"] += 1
            self.logger.info(
                f"Reconnection attempt "
                f"{self.connection_status['reconnects']}..."
            )
            await self.start()
        except Exception as e:
            self.logger.error(
                f"Unhandled exception thrown: {e}",
                exc_info=True,
                stack_info=True,
            )
            await self.stop()
