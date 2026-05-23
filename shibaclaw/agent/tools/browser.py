"""Browser automation tool using Chrome DevTools Protocol (CDP)."""

import asyncio
import json
from typing import Any

import httpx
import websockets
from loguru import logger

from shibaclaw.agent.tools.base import Tool
from shibaclaw.security.network import validate_url_target


class BrowserCDPTool(Tool):
    """Control a local Chrome instance via CDP."""

    name = "browser_cdp"
    description = (
        "Interact with the user's running Chrome browser via CDP. "
        "Available actions: navigate, get_dom, click, type, evaluate_js, screenshot."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["navigate", "get_dom", "click", "type", "evaluate_js", "screenshot"],
                "description": "The browser action to perform."
            },
            "url": {"type": "string", "description": "URL for navigate action."},
            "selector": {"type": "string", "description": "CSS selector for click/type/get_dom."},
            "text": {"type": "string", "description": "Text for type action or JS code for evaluate_js."}
        },
        "required": ["action"]
    }

    def __init__(self, host: str = "127.0.0.1", port: int = 9222):
        self.host = host
        self.port = port
        self.ws_url = None
        self._msg_id = 0

    async def _get_ws_url(self) -> str | None:
        """Fetch the WebSocket URL from Chrome."""
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"http://{self.host}:{self.port}/json")
                resp.raise_for_status()
                targets = resp.json()
                
            for target in targets:
                if target.get("type") == "page" and "webSocketDebuggerUrl" in target:
                    return target["webSocketDebuggerUrl"]
            
            for target in targets:
                if "webSocketDebuggerUrl" in target:
                    return target["webSocketDebuggerUrl"]
                    
            return None
        except Exception as e:
            logger.debug(f"Failed to connect to CDP at {self.host}:{self.port}: {e}")
            return None

    async def _send_cdp(self, method: str, params: dict | None = None) -> dict:
        """Send a CDP command and wait for the response."""
        if not self.ws_url:
            self.ws_url = await self._get_ws_url()
            if not self.ws_url:
                raise ConnectionError(f"Could not connect to Chrome on {self.host}:{self.port}. Ensure Chrome is launched with --remote-debugging-port={self.port}")

        self._msg_id += 1
        msg = {
            "id": self._msg_id,
            "method": method,
            "params": params or {}
        }
        
        try:
            async with websockets.connect(self.ws_url, max_size=10_000_000) as ws:
                await ws.send(json.dumps(msg))
                while True:
                    resp = await ws.recv()
                    data = json.loads(resp)
                    if "id" in data and data["id"] == self._msg_id:
                        if "error" in data:
                            raise Exception(f"CDP Error: {data['error'].get('message')}")
                        return data.get("result", {})
        except Exception as e:
            self.ws_url = None
            raise e

    async def execute(self, action: str, **kwargs: Any) -> str:
        try:
            if action == "navigate":
                url = kwargs.get("url")
                if not url:
                    return "Error: navigate requires 'url'."
                is_valid, error_msg = validate_url_target(url)
                if not is_valid:
                    return f"Error: SSRF validation failed - {error_msg}"
                    
                await self._send_cdp("Page.navigate", {"url": url})
                await asyncio.sleep(2)  # Simple wait for load
                return f"Successfully navigated to {url}"

            elif action == "evaluate_js":
                js = kwargs.get("text")
                if not js:
                    return "Error: evaluate_js requires 'text' parameter with JS code."
                res = await self._send_cdp("Runtime.evaluate", {"expression": js, "returnByValue": True})
                val = res.get("result", {}).get("value")
                return f"JS Result: {val}"

            elif action == "get_dom":
                selector = kwargs.get("selector", "body")
                js = f"document.querySelector('{selector}') ? document.querySelector('{selector}').innerText : 'Element not found'"
                res = await self._send_cdp("Runtime.evaluate", {"expression": js, "returnByValue": True})
                return str(res.get("result", {}).get("value", ""))

            elif action == "click":
                selector = kwargs.get("selector")
                if not selector:
                    return "Error: click requires 'selector'."
                js = f"document.querySelector('{selector}') ? (document.querySelector('{selector}').click(), 'Clicked') : 'Element not found';"
                res = await self._send_cdp("Runtime.evaluate", {"expression": js, "returnByValue": True})
                val = res.get("result", {}).get("value", "")
                if "Element not found" in val:
                     return f"Error: Element not found '{selector}'."
                return f"Clicked element matching '{selector}'"

            elif action == "type":
                selector = kwargs.get("selector")
                text = kwargs.get("text")
                if not selector or not text:
                    return "Error: type requires 'selector' and 'text'."
                
                js_escape = text.replace("'", "\\'")
                js = f"document.querySelector('{selector}') ? (document.querySelector('{selector}').value = '{js_escape}', 'Typed') : 'Element not found';"
                res = await self._send_cdp("Runtime.evaluate", {"expression": js, "returnByValue": True})
                val = res.get("result", {}).get("value", "")
                if "Element not found" in val:
                     return f"Error: Element not found '{selector}'."
                return f"Typed text into '{selector}'"

            elif action == "screenshot":
                res = await self._send_cdp("Page.captureScreenshot", {"format": "png"})
                b64 = res.get("data", "")
                if b64:
                    return f"Screenshot captured successfully. Base64 length: {len(b64)} bytes."
                return "Error: Could not capture screenshot."

            else:
                return f"Error: Unknown action '{action}'"
                
        except Exception as e:
            return f"Browser error: {str(e)}"
