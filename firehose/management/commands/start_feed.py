import logging
import signal
import sys
import threading

from django.core.management.base import BaseCommand

from firehose.subscription import CommitOperations, run
from flatlanders.algorithms.flatlanders_feed import index_commit_operations

logger = logging.getLogger("feed")
stream_stop_event = threading.Event()


def log_post(commits: CommitOperations):
    for post in commits.posts.created:
        print(f"[{post.record.created_at}]: {post.record_text}")


def sigint_handler(*_):
    print("Stopping data stream...")
    stream_stop_event.set()
    sys.exit(0)


signal.signal(signal.SIGINT, sigint_handler)


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
            run(options["service"], log_post, stream_stop_event)
        elif options["algorithm"] == "flatlanders":
            run(options["service"], index_commit_operations, stream_stop_event)
