import asyncio
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from logging import Logger
from typing import Awaitable, Callable, Optional, List, Union

from massive import WebSocketClient
from massive.websocket import Feed, Market, WebSocketMessage


class MassiveDataListener:
    connection_status: dict
    ws_connection: Union[WebSocketClient, None]
    ws_coroutine: Union[asyncio.Task, None]
    feed: Feed
    market: Market
    subscriptions: List[str]
    raw: bool
    verbose: bool
    max_reconnects: Optional[int]
    secure: bool

    def __init__(
        self,
        logger: Logger,
        message_handler: Union[
            Callable[[List[WebSocketMessage]], Awaitable],
            Callable[[Union[str, bytes]], Awaitable],
        ],
        api_key: str,
        feed: Feed,
        market: Market,
        subscriptions: List[str],
        raw: bool = False,
        verbose: bool = False,
        max_reconnects: Optional[int] = 5,
        secure: bool = True,
        **kwargs,
    ):
        self.logger = logger
        self.message_handler = message_handler
        self.api_key = api_key
        self.feed = feed
        self.market = market
        self.subscriptions = subscriptions
        self.raw = raw
        self.verbose = verbose
        self.max_reconnects = max_reconnects
        self.secure = secure
        self.kwargs = kwargs
        self.connection_status = {
            "connected": False,
            "feed": feed,
            "market": market,
            "subscriptions": subscriptions,
        }

    async def start(self):
        """Start WebSocket client"""
        try:
            self.logger.info("Instantiating WebSocket client...")
            self.ws_connection = WebSocketClient(
                api_key=self.api_key,
                feed=self.feed,
                market=self.market,
                raw=self.raw,
                verbose=self.verbose,
                subscriptions=self.subscriptions,
                max_reconnects=self.max_reconnects,
                secure=self.secure,
                **self.kwargs,
            )
            self.logger.info("Scheduling WebSocket client task...")
            self.ws_coroutine = asyncio.create_task(self.async_task())
        except Exception as e:
            self.logger.error(f"Error starting WebSocket client: {e}")
            await self.stop()

    async def stop(self):
        """Stop WebSocket client"""
        try:
            self.logger.info("Shutting down WebSocket client...")
            self.ws_coroutine.cancel()
            await asyncio.sleep(1)
            self.logger.info("unsubscribing from all feeds...")
            self.ws_connection.unsubscribe_all()
            await asyncio.sleep(1)
            self.logger.info("closing connection...")
            await self.ws_connection.close()
            self.logger.info("done.")
        except Exception as e:
            self.logger.error(f"Error stopping WebSocket client: {e}")
        self.connection_status["connected"] = False
        self.ws_connection = None
        self.ws_coroutine = None

    async def restart(self):
        """Restart WebSocket client"""
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
        """Main task that runs the WebSocket client"""
        try:
            self.logger.info("Connecting to market data provider...")
            self.connection_status["connected"] = True
            await asyncio.gather(
                self.ws_connection.connect(self.message_handler),
                return_exceptions=True
            )
            self.connection_status["connected"] = False
            self.logger.info("Disconnected from market data provider...")
            pending_restart = True
            while pending_restart:
                # Get current time in UTC, then convert to Eastern Time
                utc_now = datetime.now(timezone.utc)
                et_now = utc_now.astimezone(ZoneInfo("America/New_York"))

                # Check if within trading hours: Mon-Fri, 04:00-19:59 ET
                is_weekday = et_now.weekday() < 5
                is_trading_hours = 4 <= et_now.hour < 20

                if is_weekday and is_trading_hours:
                    self.logger.info(f"Reconnecting at {et_now.strftime('%H:%M:%S %Z')}...")
                    await self.start()
                    pending_restart = False
                else:
                    self.logger.info(f"Outside market hours ({et_now.strftime('%H:%M:%S %Z')}), sleeping 5 min...")
                    await asyncio.sleep(300)
        except Exception as e:
            self.logger.error(f"Fatal error in WebSocket client: {e}")
            await self.stop()
