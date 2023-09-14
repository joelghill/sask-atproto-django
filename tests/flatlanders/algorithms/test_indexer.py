from unittest.mock import MagicMock
from atproto import CID
from django.utils import timezone

import pytest
from firehose.subscription import (
    CommitOperations,
    CreatedRecordOperation,
)
from flatlanders.algorithms import index_commit_operations, is_sask_text

from atproto.xrpc_client.models.app.bsky.feed.post import Main as MainPost
from atproto.xrpc_client.models.app.bsky.feed.like import Main as MainLike
from atproto.xrpc_client.models.app.bsky.feed.repost import Main as MainRepost
from atproto.xrpc_client.models.com.atproto.repo.strong_ref import Main as MainStrongRef

from flatlanders.models import Post, RegisteredUser


def test_is_sask_text():
    text_1 = "Saskatchewan"
    assert is_sask_text(text_1) is True

    spotify_link = "https://open.spotify.com/intl-ja/track/4H8yXebQbN6Hua9WGjSq1r?si=953dd974cc244673"
    assert is_sask_text(spotify_link) is False

    youtube_link = "Also the screen flashes between light and dark mode when coming back to the app youtube.com/shorts/yXE-z..."
    assert is_sask_text(youtube_link) is False


@pytest.mark.django_db
def test_index_new_sask_post():
    # Creation of post record
    uri = "test_uri"
    cid = MagicMock(spec=CID)
    author_did = "test_author_did"
    post_record = MainPost(createdAt=timezone.now().isoformat(), text="Saskatchewan")
    create_record_operation = CreatedRecordOperation[MainPost](
        post_record, uri, cid, author_did
    )

    # Creation of commit operations
    operations = CommitOperations()
    operations.posts.created.append(create_record_operation)

    # Indexing of commit operations
    index_commit_operations(operations)

    assert Post.objects.count() == 1
    assert Post.objects.first().text == "Saskatchewan"

    assert RegisteredUser.objects.count() == 1
    assert RegisteredUser.objects.first().did == author_did


# @pytest.mark.django_db
# def test_index_post_like():
#     # Create post author
#     author_did = "test_author_did"
#     author = RegisteredUser.objects.create(did=author_did)

#     # Creation of post record
#     uri = "test_uri"
#     cid = "test_cid"

#     post = Post.objects.create(uri=uri, cid=cid, author=author, text="Saskatchewan")

#     ref_like = MainStrongRef(cid, uri)

#     post_record = MainLike(createdAt=datetime.now().isoformat(), subject=ref_like)
#     create_record_operation = CreatedRecordOperation[MainLike](
#         post_record, uri, cid, author_did
#     )

#     # Creation of commit operations
#     operations = CommitOperations()
#     operations.likes.created.append(create_record_operation)

#     # Indexing of commit operations
#     index_commit_operations(operations)

#     post.refresh_from_db()

#     assert post.likes == 1

# @pytest.mark.django_db
# def test_index_post_repost():
#     # Create post author
#     author_did = "test_author_did"
#     author = RegisteredUser.objects.create(did=author_did)

#     # Creation of post record
#     uri = "test_uri"
#     cid = "test_cid"

#     post = Post.objects.create(uri=uri, cid=cid, author=author, text="Saskatchewan")

#     ref_like = MainStrongRef(cid, uri)

#     post_record = MainRepost(createdAt=datetime.now().isoformat(), subject=ref_like)
#     create_record_operation = CreatedRecordOperation[MainRepost](
#         post_record, uri, cid, author_did
#     )

#     # Creation of commit operations
#     operations = CommitOperations()
#     operations.reposts.created.append(create_record_operation)

#     # Indexing of commit operations
#     index_commit_operations(operations)

#     post.refresh_from_db()

#     assert post.reposts == 1


# @pytest.mark.django_db
# def test_index_post_like_delete():
#     # Create post author
#     author_did = "test_author_did"
#     author = RegisteredUser.objects.create(did=author_did)

#     # Creation of post record
#     uri = "test_uri"
#     cid = "test_cid"

#     post = Post.objects.create(
#         uri=uri, cid=cid, author=author, text="Saskatchewan", likes=1
#     )

#     # Creation of commit operations
#     operations = CommitOperations()
#     operations.likes.deleted.append(uri)

#     # Indexing of commit operations
#     index_commit_operations(operations)

#     post.refresh_from_db()

#     assert post.likes == 0
