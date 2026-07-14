import pytest
from unittest.mock import AsyncMock, MagicMock
from shibaclaw.integrations.telegram import TelegramChannel, TelegramConfig
from shibaclaw.bus.queue import MessageBus
from loguru import logger

logger.remove()



@pytest.mark.asyncio
async def test_telegram_channel_chat_ids_eviction():
    bus = MagicMock(spec=MessageBus)
    config = TelegramConfig(enabled=True, token="fake_token")
    channel = TelegramChannel(config, bus)

    channel._download_message_media = AsyncMock(return_value=([], []))
    channel._handle_message = AsyncMock()
    channel._is_group_message_for_bot = AsyncMock(return_value=True)
    channel._build_message_metadata = MagicMock(return_value={})
    channel._derive_topic_session_key = MagicMock(return_value="session_key")
    channel.is_allowed = MagicMock(return_value=True)

    for i in range(505):
        update = MagicMock()
        user = MagicMock()
        user.id = i
        user.first_name = f"User{i}"
        user.username = f"user{i}"
        user.is_bot = False
        update.effective_user = user

        message = MagicMock()
        message.chat.id = 1000 + i
        message.chat.type = "private"
        message.from_user = user
        message.text = "hello"
        message.caption = None
        message.reply_to_message = None
        message.media_group_id = None
        message.message_id = i
        message.message_thread_id = None
        update.message = message
        update.edited_message = None

        await channel._on_message(update, MagicMock())

    assert len(channel._chat_ids) == 500
    assert "0|user0" not in channel._chat_ids
    assert "4|user4" not in channel._chat_ids
    assert "5|user5" in channel._chat_ids
    assert "504|user504" in channel._chat_ids


def test_telegram_channel_threads_eviction():
    bus = MagicMock(spec=MessageBus)
    config = TelegramConfig(enabled=True, token="fake_token")
    channel = TelegramChannel(config, bus)

    for i in range(1010):
        message = MagicMock()
        message.chat_id = "chat_abc"
        message.message_id = i
        message.message_thread_id = 9999
        channel._remember_thread_context(message)

    assert len(channel._message_threads) == 1000
    assert ("chat_abc", 0) not in channel._message_threads
    assert ("chat_abc", 9) not in channel._message_threads
    assert ("chat_abc", 10) in channel._message_threads
    assert ("chat_abc", 1009) in channel._message_threads


@pytest.mark.asyncio
async def test_telegram_channel_network_error_re_raises():
    from telegram.error import NetworkError

    bus = MagicMock(spec=MessageBus)
    config = TelegramConfig(enabled=True, token="fake_token")
    channel = TelegramChannel(config, bus)

    channel._app = MagicMock()
    channel._app.bot = MagicMock()

    channel._call_with_retry = AsyncMock(side_effect=NetworkError("Network timeout"))

    with pytest.raises(NetworkError):
        await channel._send_text(chat_id=123, text="Hello...")
