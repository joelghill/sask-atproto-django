import pytest

from flatlanders.models.posts import Post
from flatlanders.models.users import RegisteredUser


@pytest.mark.django_db
def test_post_create():
    """Test that a post can be created"""
    user = RegisteredUser.objects.create(did="did")
    post = Post.objects.create(
        uri="uri",
        cid="cid",
        author=user,
        author_did=user.did,
        text="text",
        reply_parent=None,
        reply_root=None,
    )

    assert post.author_did == "did"
    assert user.posts.first().uri == "uri"
