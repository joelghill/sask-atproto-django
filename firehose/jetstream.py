import asyncio
import json
import logging
import os
import random
import re
import signal
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import Any, Callable, Coroutine

from atproto_firehose.exceptions import FirehoseError
from websockets import (
    ConnectionClosedError,
    ConnectionClosedOK,
    InvalidHandshake,
    PayloadTooBig,
    ProtocolError,
)
from websockets.asyncio.client import connect

from firehose.subscription import WatchDogTimeoutError
from flatlanders.keywords import SASK_WORDS
from flatlanders.models.posts import Follow, Post, RegisteredUser
from flatlanders.settings import FEEDGEN_ADMIN_DID

logger = logging.getLogger("feed")


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

FIREHOSE_WORKERS_COUNT = int(os.getenv("FIREHOSE_WORKERS_COUNT", 2))

COMPILED_PATTERNS = [re.compile(rf"\b{word}\b") for word in SASK_WORDS]


OnMessageCallback = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]
OnCallbackErrorCallback = Callable[[BaseException], Coroutine[Any, Any, None]]


class JetStreamError(Exception):
    pass


class JetStreamClient:

    event_counter = 0

    def __init__(
        self,
        cursor: int | None = None,
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

    @property
    def cursor(self) -> int | None:
        return self._cursor

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
                        
                        event_str = await client.recv()
                        try:
                            JetStreamClient.event_counter += 1
                            event = json.loads(event_str)
                            self._cursor = event["time_us"]
                            if self._on_message_callback:
                                await self._on_message_callback(event)  # type: ignore
                        except Exception as e:
                            logger.error("Error processing message: %s", e)

            except Exception as e:
                self._reconnect_no += 1

                should_stop = self._handle_websocket_error_or_stop(e)
                if should_stop:
                    break

    async def stop(self) -> None:
        """Unsubscribe and stop the Jetstream client."""
        self._stop_event.set()


async def _get_cursor() -> int:
    try:
        latest_post = await Post.objects.alatest("indexed_at")
        return int(latest_post.created_at.timestamp() * 1000)  # type: ignore
    except Post.DoesNotExist:
        return 0


async def consumer_watchdog(client: JetStreamClient) -> None:
    """Task that monitors the current cursor state and stops the client if it stalls.

    Args:
        base_uri (str): The base URI of the firehose service.
    """
    last_cursor = client.cursor or 0
    last_count = JetStreamClient.event_counter
    consumer_sleep_time = 10
    while True:
        await asyncio.sleep(consumer_sleep_time)
        cursor = client.cursor or 0
        if not cursor > last_cursor:
            raise WatchDogTimeoutError("Firehose client has stalled.")

        rate = (JetStreamClient.event_counter - last_count) / consumer_sleep_time
        logger.debug("Processing rate: %d/s", rate)

        last_cursor = cursor
        last_count = JetStreamClient.event_counter


async def signal_handler(client: JetStreamClient) -> None:
    print("Keyboard interrupt received. Stopping...")

    # Stop receiving new messages
    await client.stop()


def _get_uri(event: dict[str, Any]) -> str:
    uri = (
        f"at://{event['did']}/{event['commit']['collection']}/{event['commit']['rkey']}"
    )
    return uri


def _create_post(author: RegisteredUser, post: dict[str, Any]) -> Post:
    uri = _get_uri(post)
    return Post.objects.create(
        uri=uri,
        cid=str(post["commit"]["cid"]),
        author=post["did"],
        text=post["commit"]["record"]["text"],
        created_at=datetime.fromisoformat(post["commit"]["record"]["createdAt"]),
        reply_parent=post["commit"]["record"]
        .get("reply", {})
        .get("parent", {})
        .get("uri"),
        reply_root=post["commit"]["record"]
        .get("reply", {})
        .get("root", {})
        .get("uri"),
    )


def _process_created_post(
    post_event: dict[str, Any],
):
    """Indexes a post from a commit operations object.

    1. Check as to whether or not the record text contains an SK keyword
    2. Attempts to get the author of the post from the commit operations object from the
      database.
    3. If we have an author, and they are active, save the post to the database.
    4. If we have an author, and they are not active, but the text conatins sask, save
       the post to the database and update the author record
    5. If we do not have an author, but the text contains sask, save the post to the
       database and create the author record.
    """
    record_text = post_event["commit"]["record"]["text"]
    # Get the text of the post and check if it contains an SK keyword
    is_sask_post = is_sask_text(record_text)
    # Check if the author is in the dictionary
    author = RegisteredUser.objects.filter(did=post_event["did"]).first()
    # If the post is not a sask post, and we don't have an author, skip it
    if not author and not is_sask_post:
        return

    # If we have a sask post, update the author record
    if is_sask_post:
        logger.debug("Post contains SK keyword: %s", record_text)
        # If we don't have an author, create one
        if not author:
            author = RegisteredUser.objects.create(did=post_event["did"])
            logger.info("New author registered: %s", author.did)

        logger.info("Indexing post from keyword match")
        _create_post(author, post_event)

    elif author and author.is_active():
        # Replies to non-indexed posts are ignored
        reply_parent = (
            post_event["commit"]["record"].get("reply", {}).get("parent", {}).get("uri")
        )
        if reply_parent and not Post.objects.filter(uri=reply_parent).exists():
            return
        logger.info("Indexing post from registered author: %s", record_text)
        _create_post(author, post_event)


def _process_deleted_post(uri: str):
    """Deletes a post from the database"""
    Post.objects.filter(uri__in=uri).delete()


def _process_created_follow(follow: dict[str, Any]):
    """If you follow the feed admin, you are added to the feed"""
    subject_did = follow["commit"]["record"]["subject"]
    author_did = follow["did"]
    if subject_did == FEEDGEN_ADMIN_DID:
        logger.info("User followed feed admin: %s", author_did)
        uri = _get_uri(follow)
        Follow.objects.get_or_create(
            uri=uri,
            cid=follow["commit"]["cid"],
            subject=subject_did,
            author=author_did,
        )

        user, created = RegisteredUser.objects.get_or_create(
            did=author_did, defaults={"expires_at": None}
        )

        if created:
            logger.info("New user registered: %s", author_did)
        else:
            logger.info("User re-registered: %s", author_did)
            user.expires_at = None
            user.save()
        logger.info(
            "Registering user: %s",
            author_did,
        )


def _process_deleted_follow(unfollow_event: dict[str, Any]):
    """If you unfollow the feed admin, you are removed from the feed"""
    uri = _get_uri(unfollow_event)
    record = Follow.objects.filter(uri=uri).first()
    if record:
        record.delete()
        yesterday = datetime.now(UTC) - timedelta(days=1)
        if record.subject == FEEDGEN_ADMIN_DID:
            RegisteredUser.objects.filter(did=record.author).update(
                expires_at=yesterday
            )
            logger.info("User expired via unfollow: %s", record.author)


def is_sask_text(text: str) -> bool:
    lower_text = text.lower()
    return any(pattern.search(lower_text) for pattern in COMPILED_PATTERNS)


def _process_event(event: dict[str, Any]) -> None:
    event_kind = event["kind"]
    if event_kind == "commit":
        operation = event["commit"]["operation"]
        collection = event["commit"]["collection"]
        if operation == "create":
            if collection == "app.bsky.feed.post":
                _process_created_post(event)
            elif collection == "app.bsky.graph.follow":
                _process_created_follow(event)
        elif operation == "delete":
            if collection == "app.bsky.feed.post":
                uri = _get_uri(event)
                _process_deleted_post(uri)
            elif collection == "app.bsky.graph.follow":
                _process_deleted_follow(event)


async def run_jetstream():
    with ProcessPoolExecutor(max_workers=FIREHOSE_WORKERS_COUNT) as executor:
        loop = asyncio.get_running_loop()
        # initialize client and state

        cursor = await _get_cursor()

        async def on_event_handler(event: dict[str, Any]) -> None:
            await loop.run_in_executor(executor, _process_event, event)

        client = JetStreamClient(cursor=cursor, message_callback=on_event_handler)
        signal.signal(
            signal.SIGINT, lambda _, __: asyncio.create_task(signal_handler(client))
        )
        try:
            async with asyncio.TaskGroup() as group:
                # Spawn the client and watchdog tasks
                group.create_task(client.start())
                group.create_task(consumer_watchdog(client))
        except (FirehoseError, WatchDogTimeoutError) as e:
            logger.warning("Firehose consumer has terminated due to en error: %s", e)

    logger.info("Shutting down firehose client")
