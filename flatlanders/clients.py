"""Module containing the FlatlandersATProtoClient class."""

import asyncio
import logging
from typing import TYPE_CHECKING, Iterable

from asgiref.sync import sync_to_async
from atproto import Client, DidDocument
from atproto.exceptions import AtProtocolError
from atproto_client import models

from flatlanders.models.users import RegisteredUser
from flatlanders.settings import (
    FEEDGEN_ADMIN_DID,
    FEEDGEN_MUTE_LIST_URI,
    FEEDGEN_PUBLISHER_DID,
    PUBLISHER_APP_PASSWORD,
)

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
                    created, deleted = await self.sync_registered_users()
                    logger.info(
                        f"Created {created} new users and deleted {deleted} users."
                    )
                except Exception as e:
                    logger.error("Error syncing registered users: %s", e)
                await asyncio.sleep(consumer_sleep_time)
        except asyncio.CancelledError:
            pass

    async def sync_registered_users(self) -> tuple[int, int]:
        """Add users to the database that are following the admin profile and remove users that are no longer following.

        Returns:
            tuple[int, int]: The number of users created and deleted.
        """

        if not self._admin_profile:
            raise FlatlandersATProtoClientError("Admin profile is not logged in")

        follower_dids = set(self._get_all_followers())
        muted_dids = set(self._get_all_muted_users())

        registered_dids_query = RegisteredUser.objects.values_list("did", flat=True)
        registered_dids = await sync_to_async(set)(registered_dids_query)
    
        # Followers that are not muted and not registered need to be registered
        to_create = follower_dids.difference(muted_dids, registered_dids)
        # Registered users that are on the mute list need to be deleted.
        to_delete = registered_dids.intersection(muted_dids)

        created = await self._create_registered_users(to_create)
        deleted_count = await self._delete_registered_users(to_delete)

        return len(created), deleted_count

    async def _create_registered_users(
        self, dids: Iterable[str]
    ) -> list[RegisteredUser]:
        users: list[RegisteredUser] = []
        for did in dids:
            users.append(RegisteredUser(did=did))
        return await RegisteredUser.objects.abulk_create(users)

    async def _delete_registered_users(self, dids: Iterable[str]) -> int:
        count, _ = await RegisteredUser.objects.filter(did__in=dids).adelete()
        return count

    def _get_all_followers(self) -> list[str]:
        """Add users to the database that are following the admin profile and remove users that are no longer following.

        Returns:
            tuple[int, int]: The number of users created and deleted.
        """
        limit = 100

        if not self._admin_profile:
            raise FlatlandersATProtoClientError("Admin profile is not logged in")

        response = self._client.get_followers(self._admin_profile.did, limit=limit)
        follower_dids = [FEEDGEN_ADMIN_DID]

        while True:
            batch_dids = [follower.did for follower in response.followers]  # type: ignore
            follower_dids.extend(batch_dids)  # type: ignore

            if response.cursor is None:
                break
            response = self._client.get_followers(
                self._admin_profile.did, cursor=response.cursor
            )
        return follower_dids

    def _get_all_muted_users(self) -> list[str]:
        if not FEEDGEN_MUTE_LIST_URI:
            return []

        limit = 2

        if not self._admin_profile:
            raise FlatlandersATProtoClientError("Admin profile is not logged in")

        params = models.AppBskyGraphGetList.Params(
            list=FEEDGEN_MUTE_LIST_URI, limit=limit
        )
        response: models.AppBskyGraphGetList.Response = (
            self._client.app.bsky.graph.get_list(params)
        )

        muted_dids = []

        while True:
            batch_dids = [muted.subject.did for muted in response.items]  # type: ignore
            muted_dids.extend(batch_dids)  # type: ignore

            if response.cursor is None:
                break
            params.cursor = response.cursor
            response = self._client.app.bsky.graph.get_list(params)
        return muted_dids
