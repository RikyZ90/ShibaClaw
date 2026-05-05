import asyncio
from shibaclaw.webui.routers.onboard import api_onboard_submit

class MockRequest:
    async def json(self):
        return {
            "provider": "openai",
            "model": "gpt-4o",
            "overwrite_templates": ["AGENTS.md"]
        }

from shibaclaw.webui.agent_manager import agent_manager
from shibaclaw.config.loader import load_config
from pathlib import Path
agent_manager.config = load_config(workspace_path=Path("."))
print(agent_manager.config.workspace_path.absolute())

async def run():
    r = await api_onboard_submit(MockRequest())
    print("Done")

asyncio.run(run())