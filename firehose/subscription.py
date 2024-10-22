import asyncio
import logging
import signal
import typing as t
from datetime import datetime

import sentry_sdk
from asgiref.sync import sync_to_async
from atproto import (
    CAR,
    CID,
    AsyncFirehoseSubscribeReposClient,
    AtUri,
    models,
    parse_subscribe_repos_message,
)
from atproto_client.exceptions import ModelError
from atproto_client.models.app.bsky.feed.like import Record as Like
from atproto_client.models.app.bsky.feed.post import Record as Post
from atproto_client.models.app.bsky.feed.repost import Record as Repost
from atproto_client.models.app.bsky.graph.follow import Record as Follow
from atproto_client.models.dot_dict import DotDict
from atproto_client.models.unknown_type import UnknownRecordType
from atproto_client.models.utils import get_or_create, is_record_type
from django import db
from django.utils import timezone

from firehose.models import SubscriptionState
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


class CreatedRecordOperation(t.Generic[T]):
    """Represents a record that was created in a user's repo."""

    record: T | DotDict
    uri: str
    cid: CID
    author_did: str

    def __init__(self, record: T, uri: str, cid: CID, author: str) -> None:
        self.record = record
        self.uri = uri
        self.cid = cid
        self.author_did = author

    @property
    def record_created_at(self) -> datetime:
        """Returns the created_at date of the record."""
        # If the record does not have a created_at field, return the current time
        if not hasattr(self.record, "created_at"):
            return timezone.now()

        datetime_value = self.record.created_at
        try:
            # Convert to date if string
            if datetime_value and isinstance(datetime_value, str):
                return datetime.fromisoformat(datetime_value)
            elif datetime_value and isinstance(datetime_value, datetime):
                return datetime_value  # TODO: It should be a string.
            else:
                return timezone.now()

        except ValueError:
            logger.error(
                "Invalid datetime value string: %s", datetime_value, exc_info=True
            )
            return timezone.now()

    @property
    def record_subject_uri(self) -> str | None:
        """Returns the subject of the record, if it has one."""
        if isinstance(self.record, dict):
            return self.record.get("subject", {}).get("uri")
        if not isinstance(self.record, Post) and self.record.subject:
            if isinstance(self.record.subject, str):
                return self.record.subject
            else:
                return self.record.subject.uri
        return None

    @property
    def record_text(self) -> str:
        """Returns the text of the record, if it has one."""
        if isinstance(self.record, dict):
            return self.record.get("text", "")
        return self.record.text  # type: ignore

    @property
    def record_reply(self) -> str | None:
        """Returns the reply of the record, if it has one."""
        if isinstance(self.record, dict):
            return self.record.get("reply", {}).get("parent", {}).get("uri")
        if (
            isinstance(self.record, Post)
            and self.record.reply
            and self.record.reply.parent.uri
        ):
            return self.record.reply.parent.uri

        return None

    @property
    def record_reply_root(self) -> str | None:
        """Returns the root reply of the record, if it has one."""
        if isinstance(self.record, dict):
            return self.record.get("reply", {}).get("root", {}).get("uri")
        if (
            isinstance(self.record, Post)
            and self.record.reply
            and self.record.reply.root.uri
        ):
            return self.record.reply.root.uri

        return None


class RecordOperations(t.Generic[T]):
    """Represents a collection of operations on a specific record type."""

    created: t.List[CreatedRecordOperation[T]]
    deleted: t.List[str]

    def __init__(self):
        self.created = []
        self.deleted = []


class CommitOperations:
    """Represents a collection of operations on different record types."""

    posts: RecordOperations[Post]
    reposts: RecordOperations[Repost]
    likes: RecordOperations[Like]
    follows: RecordOperations[Follow]

    def __init__(self):
        self.posts = RecordOperations[Post]()
        self.reposts = RecordOperations[Repost]()
        self.follows = RecordOperations[Follow]()
        self.likes = RecordOperations[Like]()


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
            logger.error("Subscription stalled. Stopping client...")
            await client.stop()
            break
        last_state = state


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

    async with asyncio.TaskGroup() as group:
        # Spawn the client and watchdog tasks
        group.create_task(client.start(on_message_handler))
        #group.create_task(consumer_watchdog(client, base_uri))

    logger.info("Shutting down firehose client")
