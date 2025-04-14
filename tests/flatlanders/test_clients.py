import pytest

from flatlanders.clients import FlatlandersATProtoClient, FlatlandersATProtoClientError


@pytest.mark.asyncio
async def test_sync_registered_users_not_logged_in():
    client = FlatlandersATProtoClient()
    client._admin_profile = None

    with pytest.raises(FlatlandersATProtoClientError, match="Admin profile is not logged in"):
        await client.sync_registered_users()