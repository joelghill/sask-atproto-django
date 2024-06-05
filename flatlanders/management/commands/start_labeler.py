import logging

from django.core.management.base import BaseCommand

from flatlanders.labelers import run

logger = logging.getLogger("labeler")


class Command(BaseCommand):
    help = "Starts a process to label posts from a feed"

    def add_arguments(self, parser):

        parser.add_argument(
            "--reset",
            action="store_true",
            help="Resets the current labeler cursor and processes all posts from the earliest recorded.",
        )

    def handle(self, *args, **options):
        run(options["reset"])

