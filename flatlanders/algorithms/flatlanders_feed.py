import logging
import re
from asyncio import TaskGroup
from datetime import datetime, timedelta, timezone
from typing import Iterable, List

from asgiref.sync import sync_to_async
from atproto_client.models.app.bsky.feed.post import Record as MainPost
from atproto_client.models.app.bsky.graph.follow import Record as MainFollow

from firehose.subscription import CommitOperations, CreatedRecordOperation
from flatlanders.algorithms.errors import InvalidCursorError
from flatlanders.keywords import SASK_WORDS
from flatlanders.models.posts import Follow, Post
from flatlanders.models.users import RegisteredUser
from flatlanders.settings import FEEDGEN_ADMIN_DID, FEEDGEN_URI

logger = logging.getLogger("feed")


def flatlanders_handler(limit: int = 50, cursor: str | None = None):
    """Return the feed skeleton for the flatlanders algorithm"""
    try:
        indexed_at: datetime | None = None
        if cursor:
            logger.debug("Incoming cursor: %s", cursor)
            (indexed_at_timestamp, cid) = cursor.split("::")
            if not indexed_at_timestamp or not cid:
                raise InvalidCursorError(f"Malformed cursor: {cursor}")

            indexed_at = datetime.fromtimestamp(
                float(indexed_at_timestamp), timezone.utc
            )

            posts = Post.objects.filter(created_at__lt=indexed_at).order_by(
                "-created_at"
            )[:limit]
        else:
            posts = Post.objects.order_by("-created_at")[:limit]

        feed = [{"post": post.uri} for post in posts]

        if posts:
            last = list(posts)[-1]
            if last.created_at:
                cursor = f"{last.created_at.timestamp()}::{last.cid}"
            else:
                cursor = f"{last.indexed_at.timestamp()}::{last.cid}"
        else:
            # No more posts, no cursor. Must be empty string
            cursor = ""

        logger.debug("Outgoing cursor: %s", cursor)
    except Exception as error:
        logger.error("Error in flatlanders handler: %s", error, exc_info=True)
        raise error
    return {
        "cursor": cursor,
        "feed": feed,
    }


async def index_commit_operations(commits: CommitOperations):
    """Update indexed posts and author records from a commit operations object.

    Args:
        commits (CommitOperations): Repro operations to index
    """
    async with TaskGroup() as tg:
        tg.create_task(_process_created_posts(commits.posts.created))
        tg.create_task(_process_deleted_posts(commits.posts.deleted))
        tg.create_task(_process_created_follows(commits.follows.created))
        tg.create_task(_process_deleted_follows(commits.follows.deleted))


async def _process_created_posts(
    created_posts: Iterable[CreatedRecordOperation[MainPost]],
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
    for post in created_posts:
        # Get the author of the post from the database
        author = await sync_to_async(
            RegisteredUser.objects.filter(did=post.author_did).first,
            thread_sensitive=True,
        )()
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
                author = await sync_to_async(
                    RegisteredUser.objects.create, thread_sensitive=True
                )(did=post.author_did)
                logger.info("New author registered: %s", author.did)

            logger.info("Indexing post from keyword match")
            await sync_to_async(Post.from_post_record, thread_sensitive=True)(
                post, is_sask_post, author
            )

        elif author and author.is_active():
            logger.debug("Post from registered author: %s", post.record_text)
            # Replies to non-indexed posts are ignored
            if (
                post.record_reply
                and not await sync_to_async(
                    Post.objects.filter(uri=post.record_reply).exists,
                    thread_sensitive=True,
                )()
            ):
                continue
            logger.info("Indexing post from registered author: %s", post.record_text)
            await sync_to_async(Post.from_post_record, thread_sensitive=True)(
                post, is_sask_post, author
            )


async def _process_deleted_posts(uris: List[str]):
    """Deletes a post from the database"""
    if uris:
        await sync_to_async(
            Post.objects.filter(uri__in=uris).delete, thread_sensitive=True
        )()


async def _process_created_follows(follows: List[CreatedRecordOperation[MainFollow]]):
    """If you follow the feed admin, you are added to the feed"""
    for follow in follows:
        if follow.record_subject_uri == FEEDGEN_ADMIN_DID:
            logger.info("User followed feed admin: %s", follow.author_did)
            await sync_to_async(Follow.objects.get_or_create, thread_sensitive=True)(
                uri=follow.uri,
                cid=follow.cid,
                subject=follow.record_subject_uri,
                author=follow.author_did,
            )

            user, created = await sync_to_async(
                RegisteredUser.objects.get_or_create, thread_sensitive=True
            )(did=follow.author_did, defaults={"expires_at": None})

            if created:
                logger.info("New user registered: %s", follow.author_did)
            else:
                logger.info("User re-registered: %s", follow.author_did)
                user.expires_at = None
                await sync_to_async(user.save, thread_sensitive=True)()
            logger.info(
                "Registering user: %s",
                follow.author_did,
            )


async def _process_deleted_follows(unfollows: List[str]):
    """If you unfollow the feed admin, you are removed from the feed"""
    for unfollow in unfollows:
        record = await sync_to_async(
            Follow.objects.filter(uri=unfollow).first, thread_sensitive=True
        )()
        if record:
            await sync_to_async(record.delete, thread_sensitive=True)()
            yesterday = datetime.now(timezone.utc) - timedelta(days=1)
            if record.subject == FEEDGEN_ADMIN_DID:
                await sync_to_async(
                    RegisteredUser.objects.filter(did=record.author).update,
                    thread_sensitive=True,
                )(expires_at=yesterday)
                logger.info("User expired via unfollow: %s", record.author)


def is_sask_text(text: str) -> bool:
    """Returns True if the text contains an SK keyword"""
    lower_text = text.lower()
    return any([re.search(rf"\b{word}\b", lower_text) for word in SASK_WORDS])


ALGORITHMS = {FEEDGEN_URI: flatlanders_handler}
