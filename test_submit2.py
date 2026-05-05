import asyncio
from starlette.requests import Request
from shibaclaw.webui.routers.onboard import api_onboard_submit
from shibaclaw.webui.agent_manager import agent_manager
from shibaclaw.config.schema import Config
import pathlib

class MockRequest:
    async def json(self):
        return {
            "provider": "openai",
            "model": "gpt-4o",
            "overwrite_templates": ["AGENTS.md"]
        }

agent_manager.config = Config()
agent_manager.config.workspace_path = pathlib.Path(".")

async def run():
    print("Initial AGENTS.md length:", len(pathlib.Path("AGENTS.md").read_text(encoding="utf-8")) if pathlib.Path("AGENTS.md").exists() else 0)
    r = await api_onboard_submit(MockRequest())
    print("After AGENTS.md length:", len(pathlib.Path("AGENTS.md").read_text(encoding="utf-8")))

asyncio.run(run())