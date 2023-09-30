from datetime import datetime
import logging
from multiprocessing import Pool, Queue, Value, cpu_count
from multiprocessing.synchronize import Event
import typing as t

from atproto import CAR, CID, AtUri, models
from atproto.firehose import FirehoseSubscribeReposClient, parse_subscribe_repos_message
from atproto.xrpc_client.models.dot_dict import DotDict
from atproto.xrpc_client.models.unknown_type import UnknownRecordType
from atproto.xrpc_client.models.utils import get_or_create, is_record_type
from atproto.xrpc_client.models.app.bsky.feed.post import Main as Post
from atproto.xrpc_client.models.app.bsky.feed.like import Main as Like
from atproto.xrpc_client.models.app.bsky.feed.repost import Main as Repost
from atproto.xrpc_client.models.app.bsky.graph.follow import Main as Follow

from django.utils import timezone

from firehose.models import SubscriptionState

logger = logging.getLogger("feed")


if t.TYPE_CHECKING:
    from atproto.firehose import MessageFrame


T = t.TypeVar("T", UnknownRecordType, DotDict)


class CreatedRecordOperation(t.Generic[T]):
    """Represents a record that was created in a user's repo."""

    record: T
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

    car = CAR.from_bytes(commit.blocks)
    for op in commit.ops:
        uri = AtUri.from_str(f"at://{commit.repo}/{op.path}")

        if op.action == "update":
            # not supported yet
            continue

        if op.action == "create":
            if not op.cid:
                continue

            record_raw_data = car.blocks.get(op.cid)
            if not record_raw_data:
                continue

            record = get_or_create(record_raw_data, strict=False)
            if record is None:
                continue

            if uri.collection == models.ids.AppBskyFeedLike and is_record_type(
                record, models.AppBskyFeedLike
            ):
                operation = CreatedRecordOperation[Like](
                    record=record, uri=str(uri), cid=op.cid, author=commit.repo
                )
                operation_by_type.likes.created.append(operation)

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
            elif uri.collection == models.ids.AppBskyFeedRepost and is_record_type(
                record, models.AppBskyFeedRepost
            ):
                operation = CreatedRecordOperation[Repost](
                    record=record, uri=str(uri), cid=op.cid, author=commit.repo
                )
                operation_by_type.reposts.created.append(operation)

        if op.action == "delete":
            if uri.collection == models.ids.AppBskyFeedLike:
                operation_by_type.likes.deleted.append(str(uri))
            if uri.collection == models.ids.AppBskyFeedPost:
                operation_by_type.posts.deleted.append(str(uri))
            if uri.collection == models.ids.AppBskyGraphFollow:
                operation_by_type.follows.deleted.append(str(uri))
            if uri.collection == models.ids.AppBskyFeedRepost:
                operation_by_type.reposts.deleted.append(str(uri))

    return operation_by_type


def process_queue(cursor_value, queue: Queue, operations_callback):
    logger.info("Starting subscription worker")
    while True:
        message: MessageFrame = queue.get()
        # stop on next message if requested

        commit = parse_subscribe_repos_message(message)
        if not isinstance(commit, models.ComAtprotoSyncSubscribeRepos.Commit):
            continue

        if commit.seq > cursor_value.value:  # type: ignore
            cursor_value.value = commit.seq

        ops = _get_ops_by_type(commit)
        operations_callback(ops)


def get_firehose_params(cursor_value) -> models.ComAtprotoSyncSubscribeRepos.Params:
    return models.ComAtprotoSyncSubscribeRepos.Params(cursor=cursor_value.value)


def run(name, operations_callback, stream_stop_event: Event):
    # initialize client and state
    state, _ = SubscriptionState.objects.get_or_create(
        service=name, defaults={"cursor": 0}
    )

    cursor = Value("i", state.cursor)
    params = models.ComAtprotoSyncSubscribeRepos.Params(
        cursor=state.cursor if state.cursor > 0 else None
    )

    client = FirehoseSubscribeReposClient(params)

    workers_count = 3  # cpu_count() * 2 - 1
    max_queue_size = 500

    queue = Queue(maxsize=max_queue_size)
    pool = Pool(
        workers_count,
        process_queue,
        (cursor, queue, operations_callback),
    )

    def on_message_handler(message: "MessageFrame") -> None:
        if cursor.value:  # type: ignore
            # we are using updating the cursor state here because of multiprocessing
            # typically you can call client.update_params() directly on commit processing
            client.update_params(get_firehose_params(cursor))

            # If the current state has fallen at least 20 behind, update it
            if cursor.value % 20 == 0:  # type: ignore
                SubscriptionState.objects.filter(service=name).update(cursor=cursor.value)  # type: ignore

        queue.put(message)

    client.start(on_message_handler)
    logger.info("Subscription workers stopped")
