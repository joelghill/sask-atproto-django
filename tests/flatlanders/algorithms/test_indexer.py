from unittest.mock import MagicMock

import pytest

from django.utils import timezone
from regex import R

from flatlanders.algorithms.flatlanders_feed import (

    FlatlandersAlgorithm,
    is_sask_text,
)
from flatlanders.models.posts import Post
from flatlanders.models.users import RegisteredUser
from common.models import JetstreamEventWrapper
from tests.jetstream.sample_json import REPLY_POST


def test_is_sask_text():
    text_1 = "Saskatchewan"
    assert is_sask_text(text_1) is True

    spotify_link = "https://open.spotify.com/intl-ja/track/4H8yXebQbN6Hua9WGjSq1r?si=953dd974cc244673"
    assert is_sask_text(spotify_link) is False

    youtube_link = "Also the screen flashes between light and dark mode when coming back to the app youtube.com/shorts/yXE-z..."
    assert is_sask_text(youtube_link) is False


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_index_new_sask_post():
    # Creation of post record

    algo = FlatlandersAlgorithm()
    event = JetstreamEventWrapper(REPLY_POST)
    await algo.process_event(event)

    assert await Post.objects.acount() == 1
    post = await Post.objects.afirst()
    assert post.text == event.text
    assert post.author_did == event.author
