from collections import defaultdict
from typing import Callable, List, Dict, Any
import asyncio
import logging

logger = logging.getLogger("lms_broadcaster")

class Broadcaster:
    def __init__(self):
        self._subscribers: Dict[str, List[asyncio.Queue]] = defaultdict(list)
        logger.info("Broadcaster initialized.")

    async def publish(self, channel: str, message: Dict[str, Any]):
        """
        Publishes a message to a given channel.
        Messages are put into the queue of each subscriber.
        """
        logger.debug(f"Publishing to channel '{channel}': {message}")
        if channel in self._subscribers:
            for queue in list(self._subscribers[channel]): # Iterate over a copy to avoid issues during modification
                try:
                    await queue.put(message)
                except Exception as e:
                    logger.error(f"Error publishing to queue for channel {channel}: {e}")
        else:
            logger.debug(f"No subscribers for channel '{channel}'. Message not delivered.")

    async def subscribe(self, channel: str) -> asyncio.Queue:
        """
        Subscribes to a channel and returns an asyncio.Queue to receive messages.
        """
        queue = asyncio.Queue()
        self._subscribers[channel].append(queue)
        logger.info(f"New subscriber for channel '{channel}'. Total: {len(self._subscribers[channel])}")
        return queue

    def unsubscribe(self, channel: str, queue: asyncio.Queue):
        """
        Unsubscribes a queue from a channel.
        """
        if channel in self._subscribers and queue in self._subscribers[channel]:
            self._subscribers[channel].remove(queue)
            logger.info(f"Unsubscribed from channel '{channel}'. Remaining: {len(self._subscribers[channel])}")
        else:
            logger.warning(f"Attempted to unsubscribe non-existent queue or channel: {channel}")

# Global broadcaster instance
broadcaster = Broadcaster()
