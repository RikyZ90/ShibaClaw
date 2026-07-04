from shibaclaw.config.loader import _migrate_config

def test_migrate_config_web_proxy_empty_dict():
    """Ensure that tools.web.proxy saved as {} is migrated to null (None)."""
    data = {
        "tools": {
            "web": {
                "proxy": {}
            }
        }
    }
    migrated = _migrate_config(data)
    assert migrated["tools"]["web"]["proxy"] is None

def test_migrate_config_web_proxy_valid():
    """Ensure that tools.web.proxy with a valid URL remains untouched."""
    data = {
        "tools": {
            "web": {
                "proxy": "http://127.0.0.1:8080"
            }
        }
    }
    migrated = _migrate_config(data)
    assert migrated["tools"]["web"]["proxy"] == "http://127.0.0.1:8080"

def test_migrate_config_web_proxy_none():
    """Ensure that tools.web.proxy saved as null (None) remains None."""
    data = {
        "tools": {
            "web": {
                "proxy": None
            }
        }
    }
    migrated = _migrate_config(data)
    assert migrated["tools"]["web"]["proxy"] is None
