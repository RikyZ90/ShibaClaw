"""Session routing module for handling cross-session tracking."""

import time
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class Route:
    origin_key: str
    target_key: str
    expires_at: float


class SessionRouter:
    """Maintains temporary links between sessions for cross-channel routing."""

    def __init__(self):
        self._routes: Dict[str, Route] = {}

    def link(self, target: str, origin: str, ttl_seconds: float = 600.0) -> None:
        """Link a target session key to an origin session key."""
        expires_at = time.time() + ttl_seconds
        self._routes[target] = Route(origin_key=origin, target_key=target, expires_at=expires_at)

    def resolve(self, target: str) -> Optional[str]:
        """Resolve a target session key to its origin if a valid link exists."""
        self._cleanup()
        route = self._routes.get(target)
        if route:
            return route.origin_key
        return None

    def _cleanup(self) -> None:
        """Remove expired routes."""
        now = time.time()
        expired = [k for k, v in self._routes.items() if v.expires_at < now]
        for k in expired:
            del self._routes[k]
