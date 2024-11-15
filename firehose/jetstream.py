import asyncio
import random
import urllib.parse
from typing import Any, Callable, Coroutine
from venv import logger

from websockets import (
    ConnectionClosedError,
    ConnectionClosedOK,
    InvalidHandshake,
    PayloadTooBig,
    ProtocolError,
)
from websockets.asyncio.client import connect

PUBLIC_HOSTS = [
    "jetstream1.us-east.bsky.network",
    "jetstream2.us-east.bsky.network",
    "jetstream1.us-west.bsky.network",
    "jetstream2.us-west.bsky.network",
]

WANTED_COLLECTIONS = [
    "app.bsky.graph.follow",
    "app.bsky.feed.post",
]

_OK_ERRORS = (ConnectionClosedOK,)
_ERR_ERRORS = (
    ConnectionClosedError,
    InvalidHandshake,
    PayloadTooBig,
    ProtocolError,
)

_MAX_MESSAGE_SIZE_BYTES = 1024 * 1024 * 5  # 5MB

OnMessageCallback = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]
OnCallbackErrorCallback = Callable[[BaseException], Coroutine[Any, Any, None]]


class JetStreamError(Exception):
    pass


class JetStreamClient:
    def __init__(
        self,
        cursor: float | None = None,
        max_reconnect_delay: int = 64,
        max_queue_size: int = 16,
        message_callback: OnMessageCallback | None = None,
        error_callback: OnCallbackErrorCallback | None = None,
    ) -> None:
        self._stop_event = asyncio.Event()
        self._cursor = cursor
        self._reconnect_no = 0
        self._max_queue_size = max_queue_size
        self._max_reconnect_delay_sec = max_reconnect_delay
        self._on_message_callback = message_callback
        self._on_callback_error_callback = error_callback

    def _get_uri(self) -> str:
        uri = f"wss://{random.choice(PUBLIC_HOSTS)}/subscribe?"

        for collection in WANTED_COLLECTIONS:
            uri += f"wantedCollections={collection}&"

        # Remove the last "&"
        uri = uri[:-1]

        if self._cursor:
            uri += f"&cursor={self._cursor}"

        # url encode the uri
        return uri

    def _get_reconnection_delay(self) -> int:
        base_sec = 2**self._reconnect_no
        rand_sec = random.uniform(-0.5, 0.5)

        return min(base_sec, self._max_reconnect_delay_sec) + rand_sec

    def _get_client(self):
        uri = self._get_uri()
        return connect(
            uri,
            max_size=_MAX_MESSAGE_SIZE_BYTES,
            close_timeout=0.1,
            max_queue=self._max_queue_size,
        )

    def _handle_websocket_error_or_stop(self, exception: Exception) -> bool:
        """Return if the connection should be properly being closed or reraise exception."""
        if isinstance(exception, _OK_ERRORS):
            return True
        if isinstance(exception, _ERR_ERRORS):
            return False

        if isinstance(exception, JetStreamError):
            raise exception

        raise JetStreamError from exception

    async def start(self) -> None:
        """Subscribe to Jetstream and start client."""

        while not self._stop_event.is_set():
            try:
                if self._reconnect_no != 0:
                    await asyncio.sleep(self._get_reconnection_delay())

                async with self._get_client() as client:
                    self._reconnect_no = 0

                    while not self._stop_event.is_set():
                        event = await client.recv()
                        logger.info(f"Received event: {event}")

            except Exception as e:
                self._reconnect_no += 1

                should_stop = self._handle_websocket_error_or_stop(e)
                if should_stop:
                    break

    async def stop(self) -> None:
        """Unsubscribe and stop the Jetstream client."""
        self._stop_event.set()
