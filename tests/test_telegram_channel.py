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
        update.effective_message = message
        update.guest_message = None

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


@pytest.mark.asyncio
async def test_telegram_channel_progress_network_error_re_raises():
    from telegram.error import NetworkError, RetryAfter, TimedOut

    bus = MagicMock(spec=MessageBus)
    config = TelegramConfig(enabled=True, token="fake_token")
    channel = TelegramChannel(config, bus)

    channel._app = MagicMock()
    channel._app.bot = MagicMock()

    channel._call_with_retry = AsyncMock(side_effect=NetworkError("Network timeout"))
    with pytest.raises(NetworkError):
        await channel._edit_progress_message(chat_id=123, message_id=456, text="Hello...")

    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=Warning)
        channel._call_with_retry = AsyncMock(side_effect=RetryAfter(10))
    with pytest.raises(RetryAfter):
        await channel._send_or_edit_progress(chat_id=123, text="Hello...")

    channel._call_with_retry = AsyncMock(side_effect=TimedOut())
    with pytest.raises(TimedOut):
        await channel._edit_progress_message(chat_id=123, message_id=456, text="Hello...")


@pytest.mark.asyncio
async def test_send_guest_query_uses_answer_guest_query():
    bus = MagicMock(spec=MessageBus)
    config = TelegramConfig(enabled=True, token="fake_token", guest_mode=True)
    channel = TelegramChannel(config, bus)
    channel._app = MagicMock()
    channel._app.bot = MagicMock()
    channel._call_with_retry = AsyncMock()
    channel._stop_typing = MagicMock()

    from shibaclaw.bus.events import OutboundMessage

    msg = OutboundMessage(
        channel="telegram",
        chat_id="1",
        content="hello guest",
        metadata={"guest_query_id": "gq-123"},
    )
    await channel.send(msg)
    channel._call_with_retry.assert_awaited()
    assert channel._call_with_retry.await_args.args[0] == channel._app.bot.answer_guest_query


@pytest.mark.asyncio
async def test_private_progress_uses_send_message_draft():
    bus = MagicMock(spec=MessageBus)
    config = TelegramConfig(enabled=True, token="fake_token", streaming=True)
    channel = TelegramChannel(config, bus)
    channel._app = MagicMock()
    channel._app.bot = MagicMock()
    channel._call_with_retry = AsyncMock(return_value=True)
    channel._stop_typing = MagicMock()

    from shibaclaw.bus.events import OutboundMessage

    msg = OutboundMessage(
        channel="telegram",
        chat_id="42",
        content="partial…",
        metadata={"_progress": True, "message_id": 7},
    )
    await channel.send(msg)
    assert channel._call_with_retry.await_args.args[0] == channel._app.bot.send_message_draft


@pytest.mark.asyncio
async def test_ignores_bot_sender_when_disallowed():
    bus = MagicMock(spec=MessageBus)
    config = TelegramConfig(enabled=True, token="fake_token", allow_bot_messages=False)
    channel = TelegramChannel(config, bus)
    channel._handle_message = AsyncMock()
    channel.is_allowed = MagicMock(return_value=True)

    update = MagicMock()
    user = MagicMock()
    user.id = 99
    user.first_name = "OtherBot"
    user.username = "otherbot"
    user.is_bot = True
    update.effective_user = user
    message = MagicMock()
    message.chat.id = 99
    message.chat_id = 99
    message.chat.type = "private"
    message.text = "hi"
    message.caption = None
    message.reply_to_message = None
    message.media_group_id = None
    message.message_id = 1
    message.message_thread_id = None
    message.guest_query_id = None
    message.business_connection_id = None
    update.effective_message = message
    update.guest_message = None
    update.message = message
    update.edited_message = None

    await channel._on_message(update, MagicMock())
    channel._handle_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_guest_message_sets_guest_metadata():
    bus = MagicMock(spec=MessageBus)
    config = TelegramConfig(enabled=True, token="fake_token", guest_mode=True, allow_from=["*"])
    channel = TelegramChannel(config, bus)
    channel._download_message_media = AsyncMock(return_value=([], []))
    channel._handle_message = AsyncMock()
    channel.is_allowed = MagicMock(return_value=True)

    update = MagicMock()
    user = MagicMock()
    user.id = 7
    user.first_name = "Rinat"
    user.username = "rinat"
    user.is_bot = False
    update.effective_user = user
    message = MagicMock()
    message.chat.id = -100
    message.chat_id = -100
    message.chat.type = "supergroup"
    message.text = "@shiba help"
    message.caption = None
    message.reply_to_message = None
    message.media_group_id = None
    message.message_id = 5
    message.message_thread_id = None
    message.guest_query_id = "guest-abc"
    message.business_connection_id = None
    message.photo = None
    message.voice = None
    message.audio = None
    message.document = None
    update.effective_message = message
    update.guest_message = message
    update.message = None
    update.edited_message = None

    await channel._on_message(update, MagicMock())
    assert channel._handle_message.await_count == 1
    kwargs = channel._handle_message.await_args.kwargs
    assert kwargs["metadata"]["guest_query_id"] == "guest-abc"
    assert kwargs["session_key"].startswith("telegram:guest:")


def test_telegram_config_ai_defaults():
    cfg = TelegramConfig()
    assert cfg.streaming is True
    assert cfg.guest_mode is True
    assert cfg.allow_bot_messages is True
    assert cfg.business_enabled is True
    assert cfg.managed_bots_enabled is True
