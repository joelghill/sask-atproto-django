import asyncio
import logging

from firehose.jetstream import JetStreamClient

logger = logging.getLogger("feed")


class WatchDogTimeoutError(Exception):
    """Raised when the firehose client stalls."""


async def start_watchdog(client: JetStreamClient) -> None:
    """Task that monitors the current cursor state and stops the client if it stalls.

    Args:
        base_uri (str): The base URI of the firehose service.
    """
    try:
        last_cursor = client.cursor or 0
        last_count = JetStreamClient.event_counter
        consumer_sleep_time = 60
        while True:
            await asyncio.sleep(consumer_sleep_time)
            cursor = client.cursor or 0
            if not cursor > last_cursor:
                raise WatchDogTimeoutError("Firehose client has stalled.")

            rate = (JetStreamClient.event_counter - last_count) / consumer_sleep_time
            logger.debug("Processing rate: %d/s", rate)

            last_cursor = cursor
            last_count = JetStreamClient.event_counter
    except asyncio.CancelledError:
        pass
