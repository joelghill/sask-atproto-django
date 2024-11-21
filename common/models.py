"""Model definitions to be shared with other packages."""

import abc
import logging
from datetime import datetime
from enum import StrEnum
from typing import Any

logger = logging.getLogger("feed")


class JetstreamEventKinds(StrEnum):
    """Kinds of Jetstream events."""

    COMMIT = "commit"
    IDENTITY = "identity"
    ACCOUNT = "account"
    UNKNOWN = "unknown"


class JetstreamEventOps(StrEnum):
    """Kinds of Jetstream operations."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    UNKNOWN = "unknown"


class JetstreamEventWrapper:
    """Jetstream Event Wrapper model
    Wraps the event received from the JetStream client and provides properties and helper functions.
    """

    def __init__(self, event: dict[str, Any]) -> None:
        self._event = event

        if JetstreamEventOps.CREATE in self._event:
            self._operation = JetstreamEventOps.CREATE
        elif JetstreamEventOps.UPDATE in self._event:
            self._operation = JetstreamEventOps.UPDATE
        elif JetstreamEventOps.DELETE in self._event:
            self._operation = JetstreamEventOps.DELETE
        else:
            self._operation = JetstreamEventOps.UNKNOWN

        self._created_at = None
        if (
            self.kind == JetstreamEventKinds.COMMIT
            and self._operation == JetstreamEventOps.CREATE
        ):
            iso = self._event["commit"]["record"].get("createdAt")
            self._created_at = datetime.fromisoformat(iso)

    @property
    def timestamp(self) -> float:
        return float(self._event["time_us"])

    @property
    def author(self) -> str:
        return self._event["did"]

    @property
    def kind(self) -> str:
        return self._event["kind"]

    @property
    def created_at(self) -> datetime | None:
        return self._created_at

    @property
    def operation(self) -> str | None:
        if self.kind == JetstreamEventKinds.COMMIT:
            return self._event["commit"]["operation"]

    @property
    def cid(self) -> str | None:
        if self.kind == JetstreamEventKinds.COMMIT:
            return self._event["commit"]["cid"]
        return None

    @property
    def uri(self) -> str | None:
        if self.kind == JetstreamEventKinds.COMMIT:
            return f"at://{self.author}/{self._event['commit']['collection']}/{self._event['commit']['rkey']}"
        return None

    @property
    def text(self) -> str:
        if self.kind == JetstreamEventKinds.COMMIT:
            return self._event["commit"]["record"].get("text")
        return ""

    @property
    def collection(self) -> str | None:
        if self.kind == JetstreamEventKinds.COMMIT:
            return self._event["commit"]["collection"]
        return None

    @property
    def cursor_str(self) -> str | None:
        """Returns the cursor as a properly formatted string for use in the JetStream API."""
        return f"{self.timestamp:.0f}"

    @property
    def reply_parent(self) -> str | None:
        if self.kind == JetstreamEventKinds.COMMIT:
            return (
                self._event["commit"]["record"]
                .get("reply", {})
                .get("parent", {})
                .get("uri")
            )
        return None

    @property
    def reply_root(self) -> str | None:
        if self.kind == JetstreamEventKinds.COMMIT:
            return (
                self._event["commit"]["record"]
                .get("reply", {})
                .get("root", {})
                .get("uri")
            )
        return None

    def __str__(self) -> str:
        return f"{self.timestamp}-{self.author}-{self.kind}-{self.operation}"


class FeedAlgorithm(abc.ABC):
    """Base class for feed algorithms"""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Returns the name of the feed algorithm"""

    @property
    @abc.abstractmethod
    def wanted_collections(self) -> list[str]:
        """Gets the collections the feed algorithm is interested in"""

    @property
    @abc.abstractmethod
    def wanted_dids(self) -> list[str]:
        """Gets the DIDs the feed algorithm is interested in"""

    @abc.abstractmethod
    async def process_event(self, event: JetstreamEventWrapper) -> None:
        """Processes an incoming JetStream event"""
        pass

    def on_process_event_error(self, error: Exception) -> None:
        """Handles an error in the feed algorithm"""
        logger.error("Error processing event: %s", error)

    @abc.abstractmethod
    def get_feed(self, cursor: str | None, limit: int) -> dict[str, Any]:
        """Returns a feed of post skeletons (very spooky)"""
        pass
