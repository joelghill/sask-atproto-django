from datetime import datetime, timezone
import logging
from multiprocessing import Pool, Queue, Lock, cpu_count

import typing as t

from atproto import CAR, CID, AtUri, models
from atproto.firehose import FirehoseSubscribeReposClient, parse_subscribe_repos_message
from atproto.xrpc_client.models.utils import get_or_create, is_record_type
from atproto.xrpc_client.models.app.bsky.feed.post import Main as Post
from atproto.xrpc_client.models.app.bsky.feed.like import Main as Like
from atproto.xrpc_client.models.app.bsky.feed.repost import Main as Repost
from atproto.xrpc_client.models.app.bsky.graph.follow import Main as Follow


from firehose.models import SubscriptionState

logger = logging.getLogger("feed")


if t.TYPE_CHECKING:
    from atproto.firehose import MessageFrame


T = t.TypeVar("T", Post, Like, Repost, Follow)

# Lock used for multiprocessing
mutex = Lock()


class CreatedRecordOperation(t.Generic[T]):
    """Represents a record that was created in a user's repo."""

    record: T | dict
    uri: str
    cid: CID
    author_did: str

    def __init__(self, record: T | dict, uri: str, cid: CID, author: str) -> None:
        self.record = record
        self.uri = uri
        self.cid = cid
        self.author_did = author

    @property
    def record_created_at(self) -> datetime:
        """Returns the created_at date of the record."""
        datetime_value = ""
        if isinstance(self.record, dict):
            datetime_value = self.record.get("created_at", "")
        else:
            datetime_value = self.record.created_at
        try:
            # Convert to date if string
            if datetime_value and isinstance(datetime_value, str):
                return datetime.fromisoformat(datetime_value)
            elif datetime_value and isinstance(datetime_value, datetime):
                return datetime_value
            else:
                return datetime.now(timezone.utc)

        except ValueError:
            logger.error(
                "Invalid datetime value string: %s", datetime_value, exc_info=True
            )
            return datetime.now(timezone.utc)

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


def process_queue(queue: Queue, stream_stop_event, client, state, operations_callback):
    logger.info("Starting subscription worker")
    while True:
        message: MessageFrame = queue.get()
        # stop on next message if requested
        with mutex:
            if stream_stop_event and stream_stop_event.is_set():
                client.stop()
                return

        commit = parse_subscribe_repos_message(message)
        if not isinstance(commit, models.ComAtprotoSyncSubscribeRepos.Commit):
            return

        with mutex:
            # update state after every frame
            if commit.seq > state.cursor:
                state.cursor = commit.seq
            # save state every 20 frames
            if commit.seq % 20 == 0:
                state.save()

            operations_callback(_get_ops_by_type(commit))


def run(name, operations_callback, stream_stop_event=None):
    # initialize client and state
    state = SubscriptionState.objects.filter(service=name).first()

    params = None
    if state:
        params = models.ComAtprotoSyncSubscribeRepos.Params(cursor=state.cursor)
    else:
        state = SubscriptionState.objects.create(service=name, cursor=0)

    client = FirehoseSubscribeReposClient(params=params)

    # Setup muti-processing
    workers_count = 2 # Fix later
    # if workers_count > 8:
    #     workers_count = 8
    max_queue_size = 500

    queue = Queue(maxsize=max_queue_size)
    pool = Pool(
        workers_count,
        process_queue,
        (queue, stream_stop_event, client, state, operations_callback),
    )

    def on_message_handler(message: "MessageFrame") -> None:
        queue.put(message)

    client.start(on_message_handler)
