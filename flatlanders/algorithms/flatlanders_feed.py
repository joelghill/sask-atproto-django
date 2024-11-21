import logging
import re
from datetime import datetime, timezone
from typing import Any

from common.models import FeedAlgorithm, JetstreamEventOps, JetstreamEventWrapper
from flatlanders.algorithms.errors import InvalidCursorError
from flatlanders.keywords import SASK_WORDS, is_sask_text
from flatlanders.models.posts import Post
from flatlanders.models.users import RegisteredUser

logger = logging.getLogger("feed")

COMPILED_PATTERNS = [re.compile(rf"\b{word}\b") for word in SASK_WORDS]


class FlatlandersAlgorithm(FeedAlgorithm):
    """Implementation of an algorithm for the flatlanders feed"""

    def __init__(self) -> None:
        self._wanted_dids = []
        self._wanted_collections = ["app.bsky.feed.post"]

    @property
    def wanted_collections(self) -> list[str]:
        return self._wanted_collections

    @property
    def wanted_dids(self) -> list[str]:
        return self._wanted_dids

    @property
    def name(self) -> str:
        return "flatlanders_jetstream"

    def get_feed(self, cursor: str | None, limit: int) -> dict[str, Any]:
        """Return the feed skeleton for the flatlanders algorithm.

        A chronological feed of posts that have been indexed by the algorithm.
        """
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

    async def process_event(self, event: JetstreamEventWrapper) -> None:
        if event.collection == "app.bsky.feed.post":
            if event.operation == JetstreamEventOps.CREATE:
                await self._process_created_post(event)
            elif event.operation == JetstreamEventOps.DELETE:
                await self._process_deleted_post(event)

    async def _process_created_post(self, event: JetstreamEventWrapper) -> None:
        """Indexes a post from a commit operations object.

        Args:
            event: The Jetstream event wrapper object.
        """
        record_text = event.text

        # Check if the author is in the dictionary
        author = await RegisteredUser.objects.filter(did=event.author).afirst()

        # Get the text of the post and check if it contains an SK keyword
        is_sask_post = False
        if record_text:
            is_sask_post = is_sask_text(record_text)

        # Index post from keyword match
        if is_sask_post:
            logger.info("Indexing post from keyword match")
            await Post.afrom_event(event, is_community_match=True, author=author)

        elif author:
            # Replies to non-indexed posts are ignored
            if (
                event.reply_parent
                and not await Post.objects.filter(uri=event.reply_parent).aexists()
            ):
                return

            # Index post from registered author
            logger.info("Indexing post from registered author: %s", record_text)
            await Post.afrom_event(event, is_community_match=True, author=author)

    async def _process_deleted_post(self, event: JetstreamEventWrapper):
        """Deletes a post from the database"""
        if event.uri:
            await Post.objects.filter(uri=event.uri).adelete()
