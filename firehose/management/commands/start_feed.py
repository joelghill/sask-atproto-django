import asyncio
import logging

import uvloop
from django.core.management.base import BaseCommand

from firehose.jetstream import JetStreamClient
from firehose.subscription import CommitOperations
from flatlanders.algorithms.flatlanders_feed import index_commit_operations

logger = logging.getLogger("feed")


async def log_post(commits: CommitOperations):
    for post in commits.posts.created:
        print(f"[{post.record.created_at}]: {post.record_text}")  # type: ignore

class Command(BaseCommand):
    help = "Connects to the BSky firehose and starts processing repository commits."

    def add_arguments(self, parser):
        # Positional arguments
        parser.add_argument(
            "service",
            type=str,
            help="Name of service supplying the feed. Example: wss://bsky.social",
        )

        parser.add_argument(
            "--algorithm",
            type=str,
            help="The algorithm to use for processing each post.",
            choices=["logger", "flatlanders"],
            default="logger",
        )

    def handle(self, *args, **options):
        # operations_callback = None
        # if options["algorithm"] == "logger":
        #     operations_callback = log_post
        # elif options["algorithm"] == "flatlanders":
        #     operations_callback = index_commit_operations

        with asyncio.Runner(loop_factory=uvloop.new_event_loop) as runner:
            client = JetStreamClient()
            runner.run(client.start())
