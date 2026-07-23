import pytest
from pathlib import Path
from shibaclaw.agent.subagent import SubagentManager

def test_subagent_manager_none_provider_bug():
    manager = SubagentManager(
        provider=None,
        workspace=Path("."),
        bus=None,  # type: ignore
    )
    assert manager.provider is None
    assert manager.model is None
