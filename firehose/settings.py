"""Settings for firehose consumer"""

import os

from dotenv import load_dotenv

load_dotenv()

FIREHOSE_WORKERS_COUNT = int(os.getenv("FIREHOSE_WORKERS_COUNT", "3"))
INDEXER_SENTRY_DNS = os.getenv("INDEXER_SENTRY_DNS")
