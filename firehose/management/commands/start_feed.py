import asyncio
import logging

import sentry_sdk
import uvloop
from django.core.management.base import BaseCommand

from firehose.main import run_jetstream
from firehose.settings import INDEXER_SENTRY_DNS

logger = logging.getLogger("feed")

# Initialize Sentry
if INDEXER_SENTRY_DNS:
    sentry_sdk.init(
        dsn=INDEXER_SENTRY_DNS,
        # Set traces_sample_rate to 1.0 to capture 100%
        # of transactions for tracing.
        traces_sample_rate=1.0,
        # Set profiles_sample_rate to 1.0 to profile 100%
        # of sampled transactions.
        # We recommend adjusting this value in production.
        profiles_sample_rate=1.0,
    )


POSTS_COLLECTION = "app.bsky.feed.post"


class Command(BaseCommand):
    help = "Connects to the BSky jetstream and starts processing repository commits."

    def handle(self, *args, **options):
        with asyncio.Runner(loop_factory=uvloop.new_event_loop) as runner:
            runner.run(run_jetstream())
