import asyncio
from shibaclaw.webui.agent_manager import agent_manager

async def get_cfg():
    agent_manager.load_latest_config()
    cfg = agent_manager.config
    print("FIELDS:", list(cfg.model_dump().keys()))
    
if __name__ == "__main__":
    asyncio.run(get_cfg())
