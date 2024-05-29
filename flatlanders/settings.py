"""
Feed gen settings
"""

import os

from dotenv import load_dotenv

load_dotenv()

FEEDGEN_HOSTNAME = os.getenv("FEEDGEN_HOSTNAME", "feed.flatlander.social")
FEEDGEN_SERVICE_DID = os.getenv("FEEDGEN_SERVICE_DID", f"did:web:{FEEDGEN_HOSTNAME}")
FEEDGEN_LISTENHOST = os.getenv("FEEDGEN_LISTENHOST", "localhost")
FEEDGEN_URI = os.getenv("FEEDGEN_URI")
FEEDGEN_SERVICE_DID = f"did:web:{FEEDGEN_HOSTNAME}"
FEEDGEN_DB_URL = os.getenv("FEEDGEN_DB_URL")
FEEDGEN_DB_TYPE = os.getenv("FEEDGEN_DB_TYPE", "sqlite")
FEEDGEN_DB_HOST = os.getenv("FEEDGEN_DB_HOST", "localhost")
FEEDGEN_DB_PORT = int(os.getenv("FEEDGEN_DB_PORT", "5432"))
FEEDGEN_DB_USERNAME = os.getenv("FEEDGEN_DB_USERNAME", "postgres")
FEEDGEN_DB_PASSWORD = os.getenv("FEEDGEN_DB_PASSWORD", "postgres")
FEEDGEN_DB_NAME = os.getenv("FEEDGEN_DB_NAME", "feedgen")
FEEDGEN_DB_SSL_MODE = os.getenv("FEEDGEN_DB_SSL_MODE", "require")
FEEDGEN_DB_SSL_CERT = os.getenv("FEEDGEN_DB_SSL_CERT", "")
FEEDGEN_ADMIN_DID = os.getenv("FEEDGEN_ADMIN_DID", "did:plc:cug2evrqa3nhdbvlfd2cvtky")
FEEDGEN_PUBLISHER_DID = os.getenv("FEEDGEN_PUBLISHER_DID", "")

PUBLISHER_HANDLE = os.getenv("PUBLISHER_HANDLE", "")
PUBLISHER_APP_PASSWORD = os.getenv("PUBLISHER_APP_PASSWORD", "")
RECORD_NAME = os.getenv("RECORD_NAME", "")
DISPLAY_NAME = os.getenv("DISPLAY_NAME", "")
DESCRIPTION = os.getenv("DESCRIPTION", "")
AVATAR_PATH = os.getenv("AVATAR_PATH", "")
