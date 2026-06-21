from abc import ABC, abstractmethod
from pathlib import Path

class BaseTTS(ABC):
    name: str = ""
    display_name: str = ""

    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    async def synthesize(self, text: str, output_path: Path) -> Path:
        pass
