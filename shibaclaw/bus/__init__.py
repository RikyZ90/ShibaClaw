"""Message bus module for decoupled channel-agent communication."""

from shibaclaw.bus.events import InboundMessage, OutboundMessage
from shibaclaw.bus.queue import MessageBus

__all__ = ["MessageBus", "InboundMessage", "OutboundMessage"]
