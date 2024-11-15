import asyncio
import logging
import signal
import typing as t

import sentry_sdk
from asgiref.sync import sync_to_async
from atproto import (
    CAR,
    AsyncFirehoseSubscribeReposClient,
    AtUri,
    models,
    parse_subscribe_repos_message,
)
from atproto_client.exceptions import ModelError
from atproto_client.models.app.bsky.feed.post import Record as Post
from atproto_client.models.app.bsky.graph.follow import Record as Follow
from atproto_client.models.dot_dict import DotDict
from atproto_client.models.unknown_type import UnknownRecordType
from atproto_client.models.utils import get_or_create, is_record_type
from atproto_firehose.exceptions import FirehoseError
from django import db

from firehose.models import CommitOperations, CreatedRecordOperation, SubscriptionState
from firehose.settings import INDEXER_SENTRY_DNS

logger = logging.getLogger("feed")

# Initialize Sentry
if INDEXER_SENTRY_DNS:
    sentry_sdk.init(
        dsn=INDEXER_SENTRY_DNS,
        # Set traces_sample_rate to 1.0 to capture 100%
        # of transactions for tracing.
        traces_sample_rate=1.0,
        # Set profiles_sample_rate to 1.0 to profile 100%
        # of sampled transactions.
        # We recommend adjusting this value in production.
        profiles_sample_rate=1.0,
    )

if t.TYPE_CHECKING:
    from atproto_client.models.base import ModelBase
    from atproto_firehose.models import MessageFrame


T = t.TypeVar("T", UnknownRecordType, DotDict)

_INTERESTED_RECORDS = {
    models.ids.AppBskyFeedPost: models.AppBskyFeedPost,
    models.ids.AppBskyGraphFollow: models.AppBskyGraphFollow,
}


class WatchDogTimeoutError(Exception):
    """Raised when the watchdog detects a stall."""

    pass


def _get_ops_by_type(
    commit: models.ComAtprotoSyncSubscribeRepos.Commit,
) -> CommitOperations:  # noqa: C901
    operation_by_type = CommitOperations()

    # if commit is string, convert to bytes
    if isinstance(commit.blocks, str):
        commit.blocks = commit.blocks.encode()
    try:
        car = CAR.from_bytes(commit.blocks)
    except BaseException:  # pylint: disable=broad-except
        logger.exception("Failed to parse CAR")
        return operation_by_type

    for op in commit.ops:
        uri = AtUri.from_str(f"at://{commit.repo}/{op.path}")

        if uri.collection not in _INTERESTED_RECORDS:
            continue

        if op.action == "update":
            # not supported yet
            continue

        if op.action == "create":
            if not op.cid:
                continue

            record_raw_data = car.blocks.get(op.cid)
            if not record_raw_data:
                continue
            try:
                record = get_or_create(record_raw_data, strict=False)
            except ModelError as e:
                logger.error("Failed to parse record: %s", record_raw_data)
                logger.error("Error: %s", e)
                continue

            except Exception:  # pylint
                logger.exception("Failed to parse record: %s", record_raw_data)
                continue

            if record is None:
                continue

            elif uri.collection == models.ids.AppBskyFeedPost and is_record_type(
                record, models.AppBskyFeedPost
            ):
                operation = CreatedRecordOperation[Post](
                    record=record, uri=str(uri), cid=op.cid, author=commit.repo
                )
                operation_by_type.posts.created.append(operation)
            elif uri.collection == models.ids.AppBskyGraphFollow and is_record_type(
                record, models.AppBskyGraphFollow
            ):
                operation = CreatedRecordOperation[Follow](
                    record=record, uri=str(uri), cid=op.cid, author=commit.repo
                )
                operation_by_type.follows.created.append(operation)

        if op.action == "delete":
            if uri.collection == models.ids.AppBskyFeedPost:
                operation_by_type.posts.deleted.append(str(uri))
            if uri.collection == models.ids.AppBskyGraphFollow:
                operation_by_type.follows.deleted.append(str(uri))

    return operation_by_type


def get_firehose_params(cursor_value) -> models.ComAtprotoSyncSubscribeRepos.Params:
    return models.ComAtprotoSyncSubscribeRepos.Params(cursor=cursor_value.value)


async def update_cursor(
    uri: str, cursor: int, client: AsyncFirehoseSubscribeReposClient
) -> None:
    if cursor % 100 == 0:
        client.update_params(models.ComAtprotoSyncSubscribeRepos.Params(cursor=cursor))
        await SubscriptionState.objects.aupdate_or_create(
            service=uri, defaults={"cursor": cursor}
        )


async def signal_handler(client: AsyncFirehoseSubscribeReposClient) -> None:
    print("Keyboard interrupt received. Stopping...")

    # Stop receiving new messages
    await client.stop()


async def consumer_watchdog(
    client: AsyncFirehoseSubscribeReposClient, base_uri: str
) -> None:
    """Task that monitors the current cursor state and stops the client if it stalls.

    Args:
        client (AsyncFirehoseSubscribeReposClient): The firehose client.
        base_uri (str): The base URI of the firehose service.
    """
    last_state, _ = await SubscriptionState.objects.aget_or_create(
        service=base_uri, defaults={"cursor": 0}
    )
    while True:
        await asyncio.sleep(60)
        state = await SubscriptionState.objects.aget(service=base_uri)
        if not state.cursor > last_state.cursor:
            raise WatchDogTimeoutError("Firehose client has stalled.")


async def run(base_uri, operations_callback):
    # initialize client and state
    state, _ = await SubscriptionState.objects.aget_or_create(
        service=base_uri, defaults={"cursor": 0}
    )

    params = models.ComAtprotoSyncSubscribeRepos.Params(cursor=state.cursor)

    client = AsyncFirehoseSubscribeReposClient(params, base_uri=base_uri)
    signal.signal(
        signal.SIGINT, lambda _, __: asyncio.create_task(signal_handler(client))
    )

    async def on_message_handler(message: "MessageFrame") -> None:
        # Ensure there is a db connection since this is a long running process without a request context
        await sync_to_async(db.connection.connect)()

        # Ignore messages that are not commits
        if message.type != "#commit" or "blocks" not in message.body:
            return

        try:
            commit = parse_subscribe_repos_message(message)
        except ModelError as e:
            logger.error("Failed to parse message: %s", str(message))
            logger.error("Error: %s", e)
            return

        except Exception:  # pylint: disable=broad-except
            logger.exception("Failed to parse message: %s", str(message))
            return

        # Update the cursor
        await update_cursor(base_uri, commit.seq, client)

        if (
            not isinstance(commit, models.ComAtprotoSyncSubscribeRepos.Commit)
            or not commit.blocks
        ):
            return

        ops = _get_ops_by_type(commit)
        await operations_callback(ops)

    try:
        async with asyncio.TaskGroup() as group:
            # Spawn the client and watchdog tasks
            group.create_task(client.start(on_message_handler))
            group.create_task(consumer_watchdog(client, base_uri))
    except (FirehoseError, WatchDogTimeoutError) as e:
        logger.warning("Firehose consumer has terminated due to en error: %s", e)

    logger.info("Shutting down firehose client")
