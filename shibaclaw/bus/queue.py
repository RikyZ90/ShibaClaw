"""Async message queue for decoupled channel-agent communication."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from typing import Optional

from loguru import logger
from shibaclaw.bus.events import InboundMessage, OutboundMessage


class MessageBus:
    """
    Async message bus that decouples chat channels from the agent core.

    Channels push messages to the inbound queue, and the agent processes
    them and pushes responses to the outbound queue.

    Optional **rate limiting** can be enabled per-sender by passing
    ``rate_limit_per_minute`` (default ``0`` = disabled).  When a sender
    exceeds the limit the message is silently dropped and a warning is
    logged.  This is opt-in — no limit is enforced unless the caller
    explicitly requests it.
    """

    def __init__(self, *, rate_limit_per_minute: int = 0):
        self.inbound: asyncio.Queue[InboundMessage] = asyncio.Queue()
        self.outbound: asyncio.Queue[OutboundMessage] = asyncio.Queue()
        self._rate_limit = max(rate_limit_per_minute, 0)
        # sliding window: sender_id -> list of timestamps
        self._inbound_timestamps: dict[str, list[float]] = defaultdict(list)

    def _is_rate_limited(self, sender_id: str) -> bool:
        """Return True if *sender_id* exceeds the per-minute inbound rate limit."""
        if self._rate_limit <= 0:
            return False
        now = time.monotonic()
        window = self._inbound_timestamps[sender_id]
        # Evict entries older than 60 s
        cutoff = now - 60.0
        self._inbound_timestamps[sender_id] = window = [
            ts for ts in window if ts > cutoff
        ]
        if len(window) >= self._rate_limit:
            return True
        window.append(now)
        return False

    async def publish_inbound(self, msg: InboundMessage) -> None:
        """Publish a message from a channel to the agent.

        If rate limiting is enabled and the sender has exceeded the
        threshold, the message is silently dropped.
        """
        if self._is_rate_limited(msg.sender_id):
            logger.warning(
                "Rate limit exceeded for sender {} on {} — message dropped",
                msg.sender_id,
                msg.channel,
            )
            return
        await self.inbound.put(msg)

    async def consume_inbound(self) -> InboundMessage:
        """Consume the next inbound message (blocks until available)."""
        return await self.inbound.get()

    async def publish_outbound(self, msg: OutboundMessage) -> None:
        """Publish a response from the agent to channels."""
        await self.outbound.put(msg)

    async def consume_outbound(self) -> OutboundMessage:
        """Consume the next outbound message (blocks until available)."""
        return await self.outbound.get()

    @property
    def inbound_size(self) -> int:
        """Number of pending inbound messages."""
        return self.inbound.qsize()

    @property
    def outbound_size(self) -> int:
        """Number of pending outbound messages."""
        return self.outbound.qsize()
