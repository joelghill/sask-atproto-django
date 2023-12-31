from datetime import datetime
from unittest.mock import MagicMock

import pytest
from flatlanders.algorithms import flatlanders_handler
from flatlanders.models import Post, RegisteredUser
from django.utils import timezone


@pytest.mark.django_db
def test_flatlanders_handler():
    user = RegisteredUser.objects.create(did="did")
    # Create some test posts
    post1 = Post.objects.create(
        uri="post1_uri", cid="post1_cid", created_at=timezone.now(), author=user
    )
    post2 = Post.objects.create(
        uri="post2_uri", cid="post2_cid", created_at=timezone.now(), author=user
    )
    post3 = Post.objects.create(
        uri="post3_uri", cid="post3_cid", created_at=timezone.now(), author=user
    )

    # Call the flatlanders_handler function
    result = flatlanders_handler(limit=2, cursor=None)
    cursor = result["cursor"]

    # Check the result
    assert result["cursor"] != ""
    assert len(result["feed"]) == 2
    assert result["feed"][0]["post"] == "post3_uri"
    assert result["feed"][1]["post"] == "post2_uri"

    # Call the flatlanders_handler function with cursor
    result = flatlanders_handler(limit=2, cursor=cursor)
    assert len(result["feed"]) == 1
    assert result["feed"][0]["post"] == "post1_uri"
    
