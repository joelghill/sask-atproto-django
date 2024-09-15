import logging
import re
import time
from datetime import datetime

from atproto import Client, DidDocument
from atproto_client.models.com.atproto.repo.strong_ref import Main as StrongRef
from atproto_client.models.tools.ozone.moderation.defs import ModEventLabel
from atproto_client.models.tools.ozone.moderation.emit_event import Data as EventData

from flatlanders.keywords import POLITICAL_CONTENT
from flatlanders.models.labelers import LabelerCursorState, SKPoliLabels
from flatlanders.models.posts import Post
from flatlanders.settings import FEEDGEN_PUBLISHER_DID, PUBLISHER_APP_PASSWORD

DEFAULT_labeler_SERVICE = "skpoli"

logger = logging.getLogger("labeler")


# initialize client and update base url to PDS
client = Client()
profile = client.login(FEEDGEN_PUBLISHER_DID, PUBLISHER_APP_PASSWORD)
repo = client.com.atproto.repo.describe_repo({"repo": FEEDGEN_PUBLISHER_DID})
did_doc = DidDocument.from_dict(repo.did_doc)
client._base_url = f"{did_doc.get_pds_endpoint()}/xrpc"

compiled_patterns = [re.compile(rf"\b{word}\b") for word in POLITICAL_CONTENT]

def has_political_content(post: Post) -> bool:
    """Indicate if a post has political content.

    Args:
        post (Post): The post to check for political content.

    Returns:
        bool: True if text matches any of the political content keywords.
    """
    lower_text = post.text.lower()
    return any(pattern.search(lower_text) for pattern in compiled_patterns)


def raise_label_event(post: Post, label: str):
    """Apply a label to a post.

    Args:
        post (Post): The post to label.
        label (str): The label value.
    """

    # Create the event with the label
    event = ModEventLabel(
        create_label_vals=[label],
        negate_label_vals=[],
    )

    # Create the subject reference
    subject = StrongRef(cid=post.cid, uri=post.uri)

    # Emit the event from the profile
    event = EventData(
        created_by=profile.did,
        event=event,
        subject=subject,
        subject_blob_cids=[],
    )

    # Apply headers to redirect the event to the labeler from the PDS
    headers = {"atproto-proxy": f"{FEEDGEN_PUBLISHER_DID}#atproto_labeler"}

    # Emit the event
    client.tools.ozone.moderation.emit_event(data=event, headers=headers)


def run(reset: bool = False):
    # Get the cursor state if there is one
    cursor_state, _ = LabelerCursorState.objects.get_or_create(
        labeler_service=DEFAULT_labeler_SERVICE
    )

    # Reset the cursor state if requested
    if reset or cursor_state.cursor is None:
        cursor_state.cursor = datetime.min

    while True:
        try:
            posts = Post.objects.filter(created_at__gt=cursor_state.cursor)
            logger.debug(f"Processing {posts.count()} posts")

            for post in posts:
                # Update cursor state
                cursor_state.cursor = post.created_at
                # process post
                if has_political_content(post):
                    raise_label_event(post, SKPoliLabels.POLITICAL_CONTENT)

            cursor_state.save()
        except Exception as e:
            logger.exception(e)
        time.sleep(60)
