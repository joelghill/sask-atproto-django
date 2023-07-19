import logging
import typing as t

from atproto import CAR, CID, AtUri, models
from atproto.firehose import FirehoseSubscribeReposClient, parse_subscribe_repos_message
from atproto.xrpc_client.models.utils import get_or_create, is_record_type
from atproto.xrpc_client.models.app.bsky.feed.post import Main as Post
from atproto.xrpc_client.models.app.bsky.feed.like import Main as Like
from atproto.xrpc_client.models.app.bsky.feed.repost import Main as Repost
from atproto.xrpc_client.models.app.bsky.graph.follow import Main as Follow


from firehose.models import SubscriptionState

logger = logging.getLogger(__name__)


if t.TYPE_CHECKING:
    from atproto.firehose import MessageFrame


T = t.TypeVar("T", Post, Like, Repost, Follow)


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
    def record_text(self) -> str:
        """Returns the text of the record, if it has one."""
        if isinstance(self.record, dict):
            return self.record.get("text", "")
        return self.record.text

    @property
    def record_reply(self) -> str | None:
        """Returns the reply of the record, if it has one."""
        if isinstance(self.record, dict):
            return self.record.get("reply", {}).get("parent", {}).get("uri")
        if self.record.reply and self.record.reply.parent.uri:
            return self.record.reply.parent.uri

        return None

    @property
    def record_reply_root(self) -> str | None:
        """Returns the root reply of the record, if it has one."""
        if isinstance(self.record, dict):
            return self.record.get("reply", {}).get("root", {}).get("uri")
        if self.record.reply and self.record.reply.root.uri:
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

    return operation_by_type


def run(name, operations_callback, stream_stop_event=None):
    state = SubscriptionState.objects.filter(service=name).first()

    params = None
    if state:
        params = models.ComAtprotoSyncSubscribeRepos.Params(cursor=state.cursor)

    client = FirehoseSubscribeReposClient(params)

    if not state:
        state = SubscriptionState.objects.create(service=name, cursor=0)

    def on_message_handler(message: "MessageFrame") -> None:
        # stop on next message if requested
        if stream_stop_event and stream_stop_event.is_set():
            client.stop()
            return

        commit = parse_subscribe_repos_message(message)
        if not isinstance(commit, models.ComAtprotoSyncSubscribeRepos.Commit):
            return

        # update state after every frame
        if commit.seq > state.cursor:
            state.cursor = commit.seq
        # save state every 20 frames
        if commit.seq % 20 == 0:
            state.save()

        operations_callback(_get_ops_by_type(commit))

    client.start(on_message_handler)
