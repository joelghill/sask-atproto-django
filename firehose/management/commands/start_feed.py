import logging
from math import e
import signal
import sys
import threading
from django.core.management.base import BaseCommand

from firehose.subscription import run


logger = logging.getLogger(__name__)
stream_stop_event = threading.Event()


def log_post(commits: dict):
    for post in commits.get("posts", {}).get("created", []):
        print(post["record"].text)


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
            raise NotImplementedError
