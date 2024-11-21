import asyncio
import logging
import signal
from asyncio import TaskGroup

from atproto_firehose.exceptions import FirehoseError

from firehose.jetstream import JetStreamClient
from firehose.watchdog import WatchDogTimeoutError, start_watchdog
from flatlanders.algorithms.flatlanders_feed import FlatlandersAlgorithm
from flatlanders.clients import FlatlandersATProtoClient

logger = logging.getLogger("feed")


async def signal_handler(client: JetStreamClient) -> None:
    print("Keyboard interrupt received. Stopping...")

    # Stop receiving new messages
    await client.stop()
    raise asyncio.CancelledError


async def run_jetstream() -> None:
    """Run the JetStream client"""
    algorithm = FlatlandersAlgorithm()
    client = JetStreamClient(algorithm=algorithm)

    flatlanders_client = FlatlandersATProtoClient()
    flatlanders_client.login()
    
    try:
        async with TaskGroup() as group:
            # Spawn the client and watchdog tasks
            group.create_task(client.start())
            group.create_task(start_watchdog(client))
            group.create_task(flatlanders_client.start())
            signal.signal(
                signal.SIGINT, lambda _, __: asyncio.create_task(signal_handler(client))
            )
    except (FirehoseError, WatchDogTimeoutError) as e:
        logger.warning("Firehose consumer has terminated due to en error: %s", e)

    logger.info("Shutting down firehose client")
