"""This module contains the models for the flatlanders app."""

import logging

from atproto_client.models.app.bsky.feed.post import Record as MainPost
from django.db import models

from firehose.subscription import CreatedRecordOperation
from flatlanders.models.users import RegisteredUser

logger = logging.getLogger("feed")


class Record(models.Model):
    """Represents a generic record from a user"""

    # The CID of the post
    cid = models.CharField(max_length=255, null=True)  # noqa: DJ001

    # The URI of the record
    uri = models.CharField(max_length=255, primary_key=True)

    class Meta:
        abstract = True

    def __str__(self):
        return self.uri


class Follow(Record):
    """Represents a post from a user"""

    # Person being followed
    subject = models.TextField()
    author = models.TextField()


class Post(Record):
    """Represents a post from a user"""

    # The CID of the post
    cid = models.CharField(max_length=255)
    # Author of the post. Relationship to RegsiteredUser
    author = models.ForeignKey(
        "RegisteredUser", on_delete=models.CASCADE, related_name="posts"
    )
    # Post text
    text = models.TextField()
    # The parent of the post
    reply_parent = models.CharField(max_length=255, null=True)  # noqa: DJ001
    # The root of the post
    reply_root = models.CharField(max_length=255, null=True)  # noqa: DJ001
    # The date the post was created
    created_at = models.DateTimeField(null=True)
    # The date the post was indexed
    indexed_at = models.DateTimeField(auto_now_add=True)
    # number of reposts
    reposts = models.IntegerField(default=0)
    # number of likes
    likes = models.IntegerField(default=0)
    # Whether or not the post matched the algorithm
    is_community_match = models.BooleanField(default=False)

    @classmethod
    def from_post_record(
        cls,
        post_record: CreatedRecordOperation[MainPost],
        is_community_match: bool,
        author: RegisteredUser,
    ):
        """Creates a Post object from a firehose record.

        Args:
            post_record (CreatedRecordOperation[MainPost]): Record object from firehose
            is_community_match (bool): Wether or not the post matched the algorithm
            author (RegisteredUser): Author of the post

        Returns:
            Post: The post instance
        """
        try:
            cls.objects.create(
                uri=post_record.uri,
                cid=str(post_record.cid),
                author=author,
                text=post_record.record_text,
                created_at=post_record.record_created_at,
                reply_parent=post_record.record_reply,
                reply_root=post_record.record_reply_root,
                is_community_match=is_community_match,
            )
        except Exception as error:
            logger.error("Error creating post from record: %s", error)
