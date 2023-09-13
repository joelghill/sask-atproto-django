import logging

from datetime import datetime, timezone
import re
from typing import Iterable, List
from django.conf import settings
from django.db.models import F
from atproto.xrpc_client.models.app.bsky.feed.post import Main as MainPost
from atproto.xrpc_client.models.app.bsky.feed.like import Main as MainLike
from atproto.xrpc_client.models.app.bsky.feed.repost import Main as MainRepost
from atproto.xrpc_client.models.app.bsky.graph.follow import Main as MainFollow
from firehose.subscription import CommitOperations, CreatedRecordOperation
from flatlanders.models import Follow, Post, RegisteredUser
from flatlanders.keywords import SASK_WORDS
from flatlanders.settings import FEEDGEN_ADMIN_DID


logger = logging.getLogger("feed")


class InvalidCursor(ValueError):
    """Raised when the cursor is malformed"""


def flatlanders_handler(limit: int = 20, cursor: str | None = None):
    """Return the feed skeleton for the flatlanders algorithm"""
    indexed_at: datetime | None = None
    if cursor:
        logger.debug("Incoming cursor: %s", cursor)
        (indexed_at_timestamp, cid) = cursor.split("::")
        if not indexed_at_timestamp or not cid:
            raise InvalidCursor(f"Malformed cursor: {cursor}")

        indexed_at = datetime.fromtimestamp(int(indexed_at_timestamp))

        posts = Post.objects.filter(indexed_at__lt=indexed_at).order_by("-indexed_at")[
            :limit
        ]
    else:
        posts = Post.objects.order_by("-indexed_at")[:limit]

    feed = [{"post": post.uri} for post in posts]

    cursor = None
    if posts:
        last = list(posts)[-1]
        cursor = f"{last.indexed_at.timestamp()}::{last.cid}"

    logger.debug("Outgoing cursor: %s", cursor)
    return {
        "cursor": cursor,
        "feed": feed,
    }


def index_commit_operations(commits: CommitOperations):
    """Update indexed posts and author records from a commit operations object.

    Args:
        commits (CommitOperations): Repro operations to index
    """
    # Process each commit operation
    _process_created_posts(commits.posts.created)
    _process_deleted_posts(commits.posts.deleted)

    # _process_created_likes(commits.likes.created)
    # _process_deleted_likes(commits.likes.deleted)

    # _process_created_reposts(commits.reposts.created)
    # _process_deleted_reposts(commits.reposts.deleted)
    _process_created_follows(commits.follows.created)
    _process_deleted_follows(commits.follows.deleted)


def _process_created_posts(created_posts: Iterable[CreatedRecordOperation[MainPost]]):
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
    for post in created_posts:
        # Get the author of the post from the database
        author = RegisteredUser.objects.filter(did=post.author_did).first()
        # Get the text of the post and check if it contains an SK keyword
        is_sask_post = is_sask_text(post.record_text)

        # If the post is not a sask post, and we don't have an author, skip it
        if not author and not is_sask_post:
            continue

        # If we have a sask post, update the author record
        if is_sask_post:
            logger.debug("Post contains SK keyword: %s", post.record_text)
            # If we don't have an author, create one
            if not author:
                logger.debug("Creating new author: %s", post.author_did)
                author = RegisteredUser.objects.create(did=post.author_did)
                logger.info("New author registered: %s", author.did)
            # If the author is not active, and the post is a sask post, extend their
            # active status by 3 days and save the author
            elif not author.is_registered():
                author.extend(30)
                author.save()
            logger.info("Indexing post from keyword match: %s", post.record_text)
            Post.from_post_record(post, is_sask_post, author)

        elif author and author.is_active():
            logger.debug("Post from registered author: %s", post.record_text)
            # Replies to non-indexed posts are ignored
            if (
                post.record_reply
                and not Post.objects.filter(uri=post.record_reply).exists()
            ):
                continue
            logger.info("Indexing post from registered author: %s", post.record_text)
            Post.from_post_record(post, is_sask_post, author)


def _process_deleted_posts(uris: List[str]):
    """Deletes a post from the database"""
    if uris:
        Post.objects.filter(uri__in=uris).delete()


def _process_created_likes(like_operations: List[CreatedRecordOperation[MainLike]]):
    """Increments the likes of a post from the database"""
    uris = [like.record_subject_uri for like in like_operations]
    if uris:
        Post.objects.filter(uri__in=uris).update(likes=F("likes") + 1)


def _process_deleted_likes(uris: List[str]):
    """Removes a like from a post from the database"""
    if uris:
        Post.objects.filter(uri__in=uris).update(likes=F("likes") - 1)


def _process_created_reposts(reposts: List[CreatedRecordOperation[MainRepost]]):
    """Increments the reposts of a post from the database"""
    uris = [repost.record_subject_uri for repost in reposts]
    if uris:
        Post.objects.filter(uri__in=uris).update(reposts=F("reposts") + 1)


def _process_deleted_reposts(uris: List[str]):
    """Removes a repost from a post from the database"""
    if uris:
        Post.objects.filter(uri__in=uris).update(reposts=F("reposts") - 1)


def _process_created_follows(follows: List[CreatedRecordOperation[MainFollow]]):
    """If you follow the feed admin, you are added to the feed"""
    for follow in follows:
        if follow.record_subject_uri == FEEDGEN_ADMIN_DID:
            logger.info("User followed feed admin: %s", follow.author_did)
            Follow.objects.get_or_create(
                uri=follow.uri,
                cid=follow.cid,
                subject=follow.record_subject_uri,
                author=follow.author_did,
            )

            user, created = RegisteredUser.objects.get_or_create(
                did=follow.author_did, defaults={"expires_at": None}
            )

            if created:
                logger.info("New user registered: %s", follow.author_did)
            else:
                user.expires_at = None
                user.save()
                logger.info(
                    "User already registered. Setting expiry to None: %s",
                    follow.author_did,
                )


def _process_deleted_follows(unfollows: List[str]):
    """If you unfollow the feed admin, you are removed from the feed"""
    for unfollow in unfollows:
        record = Follow.objects.filter(uri=unfollow).first()
        if record:
            record.delete()
            now = datetime.now(timezone.utc)
            if record.subject == FEEDGEN_ADMIN_DID:
                RegisteredUser.objects.filter(did=record.author).update(expires_at=now)
                logger.info("User expired via unfollow: %s", record.author)


def is_sask_text(text: str) -> bool:
    """Returns True if the text contains an SK keyword"""
    lower_text = text.lower()
    return any([re.search(rf"\b{word}\b", lower_text) for word in SASK_WORDS])

FLATLANDERS_URI = f"at://{settings.FEEDGEN_PUBLISHER_DID}/app.bsky.feed.generator/{settings.RECORD_NAME}"
ALGORITHMS = {FLATLANDERS_URI: flatlanders_handler}
