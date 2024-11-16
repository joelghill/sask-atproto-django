import asyncio
import logging

import uvloop
from django.core.management.base import BaseCommand

from firehose.jetstream import run_jetstream
from firehose.subscription import CommitOperations

logger = logging.getLogger("feed")


async def log_post(commits: CommitOperations):
    for post in commits.posts.created:
        print(f"[{post.record.created_at}]: {post.record_text}")  # type: ignore


class Command(BaseCommand):
    help = "Connects to the BSky jetstream and starts processing repository commits."

    def handle(self, *args, **options):
        with asyncio.Runner(loop_factory=uvloop.new_event_loop) as runner:
            runner.run(run_jetstream())
