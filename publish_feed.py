#!/usr/bin/env python3
# YOU MUST INSTALL ATPROTO SDK
# pip3 install atproto
from flatlanders.settings import (
    PUBLISHER_APP_PASSWORD,
    PUBLISHER_HANDLE,
    FEEDGEN_HOSTNAME,
    RECORD_NAME,
    DISPLAY_NAME,
    DESCRIPTION,
    AVATAR_PATH,
)

from atproto import Client, models

# YOUR bluesky handle
# Ex: user.bsky.social
HANDLE: str = PUBLISHER_HANDLE

# YOUR bluesky password, or preferably an App Password (found in your client settings)
# Ex: abcd-1234-efgh-5678
PASSWORD: str = PUBLISHER_APP_PASSWORD

# The hostname of the server where feed server will be hosted
# Ex: feed.bsky.dev
HOSTNAME: str = FEEDGEN_HOSTNAME

# (Optional). Only use this if you want a service did different from did:web
SERVICE_DID: str = ""


# -------------------------------------
# NO NEED TO TOUCH ANYTHING BELOW HERE
# -------------------------------------


def main():
    client = Client()
    client.login(HANDLE, PASSWORD)

    if not client.me:
        raise Exception("Login failed")

    feed_did = SERVICE_DID
    if not feed_did:
        feed_did = f"did:web:{HOSTNAME}"

    avatar_blob = None
    if AVATAR_PATH:
        with open(AVATAR_PATH, "rb") as f:
            avatar_data = f.read()
            avatar_blob = client.com.atproto.repo.upload_blob(avatar_data).blob

    response = client.com.atproto.repo.put_record(
        models.ComAtprotoRepoPutRecord.Data(
            repo=client.me.did,
            collection=models.ids.AppBskyFeedGenerator,
            rkey=RECORD_NAME,
            record=models.AppBskyFeedGenerator.Main(
                did=feed_did,
                display_name=DISPLAY_NAME,
                description=DESCRIPTION,
                avatar=avatar_blob,
                created_at=client.get_current_time_iso(),
            ),
        )
    )

    print("Successfully published!")
    print('Feed URI (put in "WHATS_ALF_URI" env var):', response.uri)


if __name__ == "__main__":
    main()
