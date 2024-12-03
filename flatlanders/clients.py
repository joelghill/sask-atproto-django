"""Module containing the FlatlandersATProtoClient class."""

import asyncio
import logging
from typing import TYPE_CHECKING

from atproto import Client, DidDocument
from atproto.exceptions import AtProtocolError

from flatlanders.models.users import RegisteredUser
from flatlanders.settings import FEEDGEN_PUBLISHER_DID, PUBLISHER_APP_PASSWORD

if TYPE_CHECKING:
    from atproto_client.models.app.bsky.actor.defs import ProfileViewDetailed

logger = logging.getLogger("feed")


class FlatlandersATProtoClientError(Exception):
    """Raised when an error occurs with the Flatlander client."""


class FlatlandersATProtoClient:
    def __init__(self) -> None:
        self._client = Client()
        self._admin_profile: ProfileViewDetailed | None = None

    def is_logged_in(self) -> bool:
        """Check if the admin profile is not None.

        Returns:
            bool: True if the admin profile is not None.
        """
        return self._admin_profile is not None

    def login(self) -> None:
        """Get the admin client instance.

        Returns:
            Client: The admin client instance.
        """
        try:
            self._admin_profile = self._client.login(
                FEEDGEN_PUBLISHER_DID, PUBLISHER_APP_PASSWORD
            )
        except AtProtocolError as e:
            logger.error("Error logging in: %s", e)
            return

        # Update the base url to the PDS
        # This may no longer be required
        repo = self._client.com.atproto.repo.describe_repo(
            {"repo": FEEDGEN_PUBLISHER_DID}
        )
        did_doc = DidDocument.from_dict(repo.did_doc)
        self._client._base_url = f"{did_doc.get_pds_endpoint()}/xrpc"

    
    
    async def start(self, consumer_sleep_time=300) -> None:
        """Task that monitors the current cursor state and stops the client if it stalls.
        Args:
            base_uri (str): The base URI of the firehose service.

        """
        try:
            while True:
                try:
                    created, deleted = await self._sync_registered_users()
                    logger.info(f"Created {created} new users and deleted {deleted} users.")
                except Exception as e:
                    logger.error("Error syncing registered users: %s", e)
                await asyncio.sleep(consumer_sleep_time)
        except asyncio.CancelledError:
            pass

    async def _sync_registered_users(self) -> tuple[int, int]:
            """Add users to the database that are following the admin profile and remove users that are no longer following.

            Returns:
                tuple[int, int]: The number of users created and deleted.
            """
            created_count = 0
            deleted_count = 0
            limit = 100

            if not self._admin_profile:
                raise FlatlandersATProtoClientError("Admin profile is not logged in")

            response = self._client.get_followers(self._admin_profile.did, limit=limit)
            follower_dids = []

            while True:
                batch_dids = [follower.did for follower in response.followers]  # type: ignore
                follower_dids.extend(batch_dids)  # type: ignore
                for did in batch_dids:
                    user, created = await RegisteredUser.objects.aget_or_create(did=did)
                    if created:
                        created_count += 1

                if response.cursor is None:
                    break
                response = self._client.get_followers(
                    self._admin_profile.did, cursor=response.cursor
                )

            deleted_count, _ = await RegisteredUser.objects.exclude(
                did__in=follower_dids
            ).adelete()
            return created_count, deleted_count
