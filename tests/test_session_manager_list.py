import time
from shibaclaw.brain.manager import PackManager

def test_list_sessions_updated_at(tmp_path):
    manager = PackManager(tmp_path)

    s1 = manager.get_or_create("webui:test1")
    s1.add_message("user", "Hello first")
    manager.save(s1)

    time.sleep(0.1)

    s2 = manager.get_or_create("webui:test2")
    s2.add_message("user", "Hello second")
    manager.save(s2)

    sessions = manager.list_sessions()
    assert sessions[0]["key"] == "webui:test2"
    assert sessions[1]["key"] == "webui:test1"

    # Now append to s1
    time.sleep(0.1)
    s1.add_message("user", "Appending to first")
    manager.save(s1)

    sessions = manager.list_sessions()
    # If list_sessions correctly uses mtime, test1 should be at the top
    assert sessions[0]["key"] == "webui:test1", "Session 1 should be most recent"
    assert sessions[1]["key"] == "webui:test2"
