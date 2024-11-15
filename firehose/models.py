import logging
from datetime import datetime
from typing import Generic, TypeVar

from atproto import CID
from atproto_client.models.app.bsky.feed.like import Record as Like
from atproto_client.models.app.bsky.feed.post import Record as Post
from atproto_client.models.app.bsky.feed.repost import Record as Repost
from atproto_client.models.app.bsky.graph.follow import Record as Follow
from atproto_client.models.dot_dict import DotDict
from atproto_client.models.unknown_type import UnknownRecordType
from django.db import models
from django.utils import timezone

logger = logging.getLogger("feed")

T = TypeVar("T", UnknownRecordType, DotDict)


# Subscription State model
class SubscriptionState(models.Model):
    """Subscription State model
    Records the current state of a subscription to the ATP feed.
    """

    service = models.CharField(max_length=255, unique=True)
    cursor = models.BigIntegerField()

    def __str__(self) -> str:
        return f"{self.service} - {self.cursor}"


class CreatedRecordOperation(Generic[T]):
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

        if hasattr(self.record, "created_at"):
            datetime_value = self.record.created_at  # type: ignore
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
        return timezone.now()

    @property
    def record_subject_uri(self) -> str | None:
        """Returns the subject of the record, if it has one."""
        if isinstance(self.record, dict):
            return self.record.get("subject", {}).get("uri")
        if not isinstance(self.record, Post) and hasattr(self.record, "subject"):
            if isinstance(self.record.subject, str):  # type: ignore
                return self.record.subject  # type: ignore
            else:
                return self.record.subject.uri  # type: ignore
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


class RecordOperations(Generic[T]):
    """Represents a collection of operations on a specific record type."""

    created: list[CreatedRecordOperation[T]]
    deleted: list[str]

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
