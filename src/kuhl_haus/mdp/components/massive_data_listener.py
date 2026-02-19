import asyncio
import logging
from typing import Awaitable, Callable, Optional, List, Union

from massive import RESTClient, WebSocketClient
from massive.rest.models import MarketStatus
from massive.websocket import Feed, Market, WebSocketMessage

from kuhl_haus.mdp.enum.market_status_value import MarketStatusValue


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
        self.logger = logging.getLogger(__name__)
        self.rest_client = RESTClient(api_key=api_key)
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
            "feed": self.feed,
            "healthy": False,
            "market": self.market,
            "reconnects": 0,
            "subscriptions": self.subscriptions,
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
            self.connection_status["healthy"] = True
            await asyncio.gather(
                self.ws_connection.connect(self.message_handler),
                return_exceptions=True
            )
            self.connection_status["connected"] = False
            self.logger.info("Disconnected from market data provider...")
            pending_restart = True
            while pending_restart:
                market_status: MarketStatus = (
                    self.rest_client.get_market_status()
                )
                market_open: bool = (
                    market_status.market is not None
                    and market_status.market != MarketStatusValue.CLOSED.value
                )

                if market_open:
                    self.connection_status["healthy"] = False
                    self.connection_status["reconnects"] += 1
                    self.logger.info(
                        f"Reconnection attempt "
                        f"{self.connection_status['reconnects']}..."
                    )
                    await self.start()
                    pending_restart = False
                else:
                    self.logger.info(
                        f"Market status is ({market_status.market}), "
                        f"sleeping..."
                    )
                    await asyncio.sleep(60)
        except Exception as e:
            self.logger.error(
                f"Unhandled exception thrown: {e}",
                exc_info=True,
                stack_info=True
            )
            await self.stop()
