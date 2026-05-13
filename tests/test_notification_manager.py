from shibaclaw.helpers.notification_manager import NotificationManager


def test_notification_manager_dedupes_update_notifications():
    manager = NotificationManager()

    first = manager.create_from_event(
        content="Version 0.3.8 is available.",
        source="update",
        metadata={
            "category": "update",
            "title": "Update available",
            "install_method": "pip",
            "latest": "0.3.8",
        },
        msg_type="notification",
    )
    second = manager.create_from_event(
        content="Version 0.3.8 is available.",
        source="update",
        metadata={
            "category": "update",
            "title": "Update available",
            "install_method": "pip",
            "latest": "0.3.8",
        },
        msg_type="notification",
    )

    assert first["id"] == second["id"]
    assert manager.list_notifications()["total_count"] == 1
    assert second["action"]["kind"] == "settings-tab"


def test_notification_manager_marks_and_deletes_notifications():
    manager = NotificationManager()
    created = manager.create_notification(
        message="A background task finished.",
        kind="agent_response",
        source="background",
        session_key="webui:123",
    )

    assert manager.list_notifications()["unread_count"] == 1
    assert manager.mark_read(created["id"]) == 1
    assert manager.list_notifications()["unread_count"] == 0
    assert manager.delete(created["id"]) == 1
    assert manager.list_notifications()["total_count"] == 0


def test_notification_manager_uses_completion_titles_for_heartbeat_and_cron():
    manager = NotificationManager()

    heartbeat = manager.create_from_event(
        content="Completed the scheduled heartbeat task.",
        source="heartbeat",
        session_key="webui:heartbeat-session",
    )
    cron = manager.create_from_event(
        content="Cron job completed successfully.",
        source="cron",
        session_key="webui:cron-session",
    )

    assert heartbeat["kind"] == "heartbeat"
    assert heartbeat["title"] == "Heartbeat task completed"
    assert heartbeat["action"]["kind"] == "session"
    assert heartbeat["action"]["target"] == "webui:heartbeat-session"
    assert cron["kind"] == "cron"
    assert cron["title"] == "Cron job completed"
    assert cron["action"]["kind"] == "session"
    assert cron["action"]["target"] == "webui:cron-session"
