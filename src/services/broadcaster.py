from collections import defaultdict
from typing import Callable, List, Dict, Any
import asyncio
from src.services.audit_log import AuditLogger
import logging # For level constants



class Broadcaster:
    def __init__(self):
        self._subscribers: Dict[str, List[asyncio.Queue]] = defaultdict(list)
        AuditLogger.log_sync("Broadcaster initialized.")

    async def publish(self, channel: str, message: Dict[str, Any]):
        """
        Publishes a message to a given channel.
        Messages are put into the queue of each subscriber.
        """
        await AuditLogger.log(f"Publishing to channel '{channel}': {message}", level=logging.DEBUG)
        if channel in self._subscribers:
            for queue in list(self._subscribers[channel]): # Iterate over a copy to avoid issues during modification
                try:
                    await queue.put(message)
                except Exception as e:
                    await AuditLogger.log(f"Error publishing to queue for channel {channel}: {e}", level=logging.ERROR)
        else:
            await AuditLogger.log(f"No subscribers for channel '{channel}'. Message not delivered.", level=logging.DEBUG)

    async def subscribe(self, channel: str) -> asyncio.Queue:
        """
        Subscribes to a channel and returns an asyncio.Queue to receive messages.
        """
        queue = asyncio.Queue()
        self._subscribers[channel].append(queue)
        await AuditLogger.log(f"New subscriber for channel '{channel}'. Total: {len(self._subscribers[channel])}")
        return queue

    def unsubscribe(self, channel: str, queue: asyncio.Queue):
        """
        Unsubscribes a queue from a channel.
        """
        if channel in self._subscribers and queue in self._subscribers[channel]:
            self._subscribers[channel].remove(queue)
            AuditLogger.log_sync(f"Unsubscribed from channel '{channel}'. Remaining: {len(self._subscribers[channel])}")
        else:
            AuditLogger.log_sync(f"Attempted to unsubscribe non-existent queue or channel: {channel}", level=logging.WARNING)

# Global broadcaster instance
broadcaster = Broadcaster()
