from datetime import datetime
from typing import Iterable
from django.conf import settings
from flatlanders.models import Post


class InvalidCursor(ValueError):
    """Raised when the cursor is malformed"""


def flatlanders_handler(limit: int = 20, cursor: str = None):
    """Return the feed skeleton for the flatlanders algorithm"""
    indexed_at: datetime | None = None
    if cursor:
        (indexed_at_timestamp, cid) = cursor.split("::")
        if not indexed_at_timestamp or not cid:
            raise InvalidCursor(f"Malformed cursor: {cursor}")

        indexed_at = datetime.fromtimestamp(int(indexed_at_timestamp))

        posts: Iterable[Post] = (
            Post.objects.filter(indexed_at__lt=indexed_at)
            .order_by("-indexed_at")[:limit]
        )
    else:
        posts: Iterable[Post] = Post.objects.order_by("-indexed_at")[:limit]

    feed = [{"post": post.uri} for post in posts]

    cursor = None
    if posts:
        last = posts[-1]
        cursor = f"{last.indexed_at.timestamp()}::{last.cid}"

    return {
        "cursor": cursor,
        "feed": feed,
    }


FLATLANDERS_URI = f"at://{settings.FEEDGEN_PUBLISHER_DID}/app.bsky.feed.generator/{settings.RECORD_NAME}"
ALGORITHMS = {FLATLANDERS_URI: flatlanders_handler}
