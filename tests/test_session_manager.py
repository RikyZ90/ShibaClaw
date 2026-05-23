import json
import time

from shibaclaw.brain.manager import PackManager, Session


def test_pack_manager_reloads_cached_session_when_file_changes(tmp_path):
    manager = PackManager(tmp_path)
    session = Session(key="webui:test")
    session.metadata["model"] = "openrouter/google/gemma-4-31b-it"
    manager.save(session)

    cached = manager.get_or_create("webui:test")
    assert cached.metadata["model"] == "openrouter/google/gemma-4-31b-it"

    path = manager._get_session_path("webui:test")
    lines = path.read_text(encoding="utf-8").splitlines()
    metadata = json.loads(lines[0])
    metadata["metadata"]["model"] = "github_copilot/gpt-4.1"
    time.sleep(0.05)
    path.write_text("\n".join([json.dumps(metadata, ensure_ascii=False), *lines[1:]]) + "\n", encoding="utf-8")

    reloaded = manager.get_or_create("webui:test")

    assert reloaded.metadata["model"] == "github_copilot/gpt-4.1"
