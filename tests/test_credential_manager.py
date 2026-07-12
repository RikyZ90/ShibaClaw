# ruff: noqa: E402
import threading
import pytest
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

# Add plugin to path dynamically
plugin_dir = Path(__file__).parent.parent / "plugins" / "shibaclaw-channel-whatsapp"
sys.path.insert(0, str(plugin_dir))

from shibaclaw.security.credential_manager import CredentialManager, _FERNET_CACHE
from shibaclaw.config.loader import _migrate_secrets_from_raw_dict, _scrub_secrets_from_dump
from shibaclaw.integrations.discord import DiscordConfig
from shibaclaw.integrations.dingtalk import DingTalkConfig
from shibaclaw.integrations.feishu import FeishuConfig
from shibaclaw.integrations.qq import QQConfig
from shibaclaw.integrations.mochat import MochatConfig
from shibaclaw_channel_whatsapp.channel import WhatsAppConfig

def test_fernet_cache_is_path_aware():
    """Ensure different vault directories generate different Fernet objects/keys."""
    with TemporaryDirectory() as tmp1, TemporaryDirectory() as tmp2:
        path1 = Path(tmp1)
        path2 = Path(tmp2)
        
        cm1 = CredentialManager(store_dir=path1)
        cm2 = CredentialManager(store_dir=path2)
        
        assert cm1._key_path != cm2._key_path
        assert cm1._fernet is not cm2._fernet
        assert cm1._key_path in _FERNET_CACHE
        assert cm2._key_path in _FERNET_CACHE

def test_load_all_raises_on_corruption():
    """Ensure _load_all raises RuntimeError on corrupted store rather than silently returning {}."""
    with TemporaryDirectory() as tmp:
        path = Path(tmp)
        cm = CredentialManager(store_dir=path)
        
        # Save a secret first
        cm.set_secret("test", "key", "val")
        
        # Corrupt the file
        cm._store_path.write_bytes(b"invalid_encrypted_data_corruption_here")
        
        # Force cache reload by resetting cache_mtime
        cm._cache_mtime = None
        
        with pytest.raises(RuntimeError, match="Credential vault corrupted"):
            cm._load_all()

def test_credential_manager_thread_safety():
    """Test concurrent writes to CredentialManager to ensure thread safety."""
    with TemporaryDirectory() as tmp:
        path = Path(tmp)
        cm = CredentialManager(store_dir=path)
        
        errors = []
        def writer_task(tid):
            try:
                for i in range(50):
                    cm.set_secret("threads", f"key_{tid}_{i}", f"val_{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer_task, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
            
        assert not errors, f"Threading errors occurred: {errors}"
        
        # Verify all keys were written
        data = cm._load_all()
        for i in range(5):
            for j in range(50):
                assert data["secrets"]["threads"][f"key_{i}_{j}"] == f"val_{j}"

def test_channel_resolvers(monkeypatch):
    """Verify that all channel config classes correctly resolve vault-based secrets."""
    with TemporaryDirectory() as tmp:
        path = Path(tmp)
        cm = CredentialManager(store_dir=path)
        
        # Mock get_credential_manager to return our temporary manager
        monkeypatch.setattr(
            "shibaclaw.security.credential_manager.get_credential_manager",
            lambda: cm
        )
        
        # Setup secrets in vault
        cm.set_secret("channels", "discord.token", "vault_discord_token")
        cm.set_secret("channels", "dingtalk.client_secret", "vault_dingtalk_secret")
        cm.set_secret("channels", "feishu.app_secret", "vault_feishu_app_secret")
        cm.set_secret("channels", "feishu.encrypt_key", "vault_feishu_encrypt_key")
        cm.set_secret("channels", "feishu.verification_token", "vault_feishu_verification")
        cm.set_secret("channels", "qq.secret", "vault_qq_secret")
        cm.set_secret("channels", "mochat.claw_token", "vault_mochat_token")
        cm.set_secret("channels", "whatsapp.bridge_token", "vault_whatsapp_token")

        # 1. Discord Config
        d_cfg = DiscordConfig(token="plain_discord_token")
        assert d_cfg.resolve_token() == "vault_discord_token"
        
        # 2. DingTalk Config
        dt_cfg = DingTalkConfig(client_secret="plain_dt_secret")
        assert dt_cfg.resolve_client_secret() == "vault_dingtalk_secret"
        
        # 3. Feishu Config
        fs_cfg = FeishuConfig(
            app_secret="plain_fs_secret",
            encrypt_key="plain_fs_encrypt",
            verification_token="plain_fs_verify"
        )
        assert fs_cfg.resolve_app_secret() == "vault_feishu_app_secret"
        assert fs_cfg.resolve_encrypt_key() == "vault_feishu_encrypt_key"
        assert fs_cfg.resolve_verification_token() == "vault_feishu_verification"
        
        # 4. QQ Config
        qq_cfg = QQConfig(secret="plain_qq_secret")
        assert qq_cfg.resolve_secret() == "vault_qq_secret"
        
        # 5. MoChat Config
        mc_cfg = MochatConfig(claw_token="plain_mochat_token")
        assert mc_cfg.resolve_claw_token() == "vault_mochat_token"
        
        # 6. WhatsApp Plugin Config
        wa_cfg = WhatsAppConfig(bridge_token="plain_whatsapp_token")
        assert wa_cfg.resolve_bridge_token() == "vault_whatsapp_token"

def test_migration_explicit_matching_and_scrub(monkeypatch):
    """Test that explicit allowlist matches and scrubs correct secrets while ignoring non-secret keys."""
    with TemporaryDirectory() as tmp:
        path = Path(tmp)
        cm = CredentialManager(store_dir=path)
        cm.setup_user("admin", "password123")
        
        monkeypatch.setattr(
            "shibaclaw.security.credential_manager.get_credential_manager",
            lambda: cm
        )
        
        raw_config = {
            "channels": {
                "feishu": {
                    "app_secret": "my_feishu_secret",
                    "encrypt_key": "my_encrypt_key",
                    "non_secret_field": "keep_me"
                },
                "telegram": {
                    "token": "my_telegram_token"
                }
            }
        }
        
        # Migrate
        migrated = _migrate_secrets_from_raw_dict(raw_config, cm)
        assert migrated is True
        
        # Check that secrets were extracted from dict and saved to vault
        assert "app_secret" not in raw_config["channels"]["feishu"]
        assert "encrypt_key" in raw_config["channels"]["feishu"]
        assert raw_config["channels"]["feishu"]["non_secret_field"] == "keep_me"
        assert "token" not in raw_config["channels"]["telegram"]
        
        assert cm.get_secret("channels", "feishu.app_secret") == "my_feishu_secret"
        assert cm.get_secret("channels", "feishu.encrypt_key") is None
        assert cm.get_secret("channels", "telegram.token") == "my_telegram_token"

        # Check scrub
        dump_data = {
            "channels": {
                "feishu": {
                    "app_secret": "my_feishu_secret",
                    "encrypt_key": "my_encrypt_key",
                    "non_secret_field": "keep_me"
                }
            }
        }
        scrubbed = _scrub_secrets_from_dump(dump_data, cm)
        assert scrubbed["channels"]["feishu"]["app_secret"] == ""
        assert scrubbed["channels"]["feishu"]["encrypt_key"] == "my_encrypt_key"
        assert scrubbed["channels"]["feishu"]["non_secret_field"] == "keep_me"
