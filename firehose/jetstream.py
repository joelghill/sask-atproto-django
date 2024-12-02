import asyncio
import json
import logging
import random
from typing import Any, Callable, Coroutine

from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed
from zstandard import ZstdCompressionDict, ZstdDecompressor

from common.models import FeedAlgorithm, JetstreamEventWrapper
from firehose.models import SubscriptionState

logger = logging.getLogger("feed")


PUBLIC_HOSTS = [
    "jetstream1.us-east.bsky.network",
    "jetstream2.us-east.bsky.network",
    "jetstream1.us-west.bsky.network",
    "jetstream2.us-west.bsky.network",
]

_MAX_MESSAGE_SIZE_BYTES = 1024 * 1024 * 5  # 5MB


OnMessageCallback = Callable[[JetstreamEventWrapper], Coroutine[Any, Any, None]]
OnCallbackErrorCallback = Callable[[BaseException], Coroutine[Any, Any, None]]


class JetStreamError(Exception):
    pass


class JetStreamClient:
    event_counter = 0

    def __init__(
        self,
        algorithm: FeedAlgorithm,
        max_reconnect_delay: int = 64,
        max_queue_size: int = 500,
    ) -> None:
        self._algorithm = algorithm
        self._stop_event = asyncio.Event()
        self._cursor: float | None = None
        self._reconnect_no = 0
        self._max_queue_size = max_queue_size
        self._max_reconnect_delay_sec = max_reconnect_delay
        self._client_connection: ClientConnection | None = None
        self._decompressor = self._load_decompressor()

    @property
    def cursor(self) -> float | None:
        return self._cursor

    def _load_decompressor(self) -> ZstdDecompressor:
        with open("firehose/zstd_dictionary", "rb") as f:
            dict_data = f.read()
        decompress_dict = ZstdCompressionDict(data=dict_data)
        return ZstdDecompressor(dict_data=decompress_dict)

    def _get_uri(self) -> str:
        uri = f"wss://{random.choice(PUBLIC_HOSTS)}/subscribe?"

        if self._algorithm.wanted_collections:
            for collection in self._algorithm.wanted_collections:
                uri += f"wantedCollections={collection}&"

        if self._algorithm.wanted_dids:
            for did in self._algorithm.wanted_dids:
                uri += f"wantedDids={did}&"

        # Remove the last "&"
        uri = uri[:-1]

        if self._cursor:
            uri += f"&cursor={self._cursor:.0f}"

        uri += "&compress=true"

        # url encode the uri
        return uri

    def _connect(self) -> connect:
        uri = self._get_uri()
        return connect(
            uri,
            max_size=_MAX_MESSAGE_SIZE_BYTES,
            close_timeout=0.5,
            ping_interval=None,
            ping_timeout=None,
            compression=None,
            max_queue=self._max_queue_size,
        )

    async def start(self) -> None:
        await self._init_cursor()
        """Subscribe to Jetstream and start client."""
        while not self._stop_event.is_set():
            try:
                async for client in self._connect():
                    while not self._stop_event.is_set():
                        compressed: bytes = await client.recv(decode=False)  # type: ignore
                        try:
                            event = self._decompress_event(compressed)
                            await self._set_cursor(event.timestamp)
                            await self._algorithm.process_event(event)
                        except Exception as e:
                            self._algorithm.on_process_event_error(e)
            except ConnectionClosed:
                if self._stop_event.is_set():
                    break
                logger.warning("Connection closed. Reconnecting...")

    async def stop(self) -> None:
        """Unsubscribe and stop the Jetstream client."""
        self._stop_event.set()
        if self._client_connection:
            await self._client_connection.close()

    async def _init_cursor(self) -> None:
        # try:
        #     state = await SubscriptionState.objects.aget(service=self._algorithm.name)
        #     self._cursor = state.cursor
        # except SubscriptionState.DoesNotExist:
        self._cursor = 0.0

    async def _set_cursor(self, cursor: float) -> None:
        self._cursor = cursor
        if cursor % 100 == 0:
            await SubscriptionState.objects.aupdate_or_create(
                service=self._algorithm.name, defaults={"cursor": cursor}
            )

    def _decompress_event(self, data: bytes) -> JetstreamEventWrapper:
        event_bytes = self._decompressor.decompress(
            data, max_output_size=_MAX_MESSAGE_SIZE_BYTES
        )
        JetStreamClient.event_counter += 1
        return JetstreamEventWrapper(json.loads(event_bytes))
