import asyncio
import logging
import threading

from django.core.management.base import BaseCommand

from firehose.subscription import CommitOperations, run
from flatlanders.algorithms.flatlanders_feed import index_commit_operations

logger = logging.getLogger("feed")
stream_stop_event = threading.Event()


async def log_post(commits: CommitOperations):
    for post in commits.posts.created:
        print(f"[{post.record.created_at}]: {post.record_text}") # type: ignore


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
        if options["algorithm"] == "logger":
            asyncio.get_event_loop().run_until_complete(run(options["service"], log_post))
        elif options["algorithm"] == "flatlanders":
            asyncio.get_event_loop().run_until_complete(run(options["service"], index_commit_operations))
