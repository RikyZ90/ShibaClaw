"""Telegram channel implementation using python-telegram-bot."""

from __future__ import annotations

import asyncio
import itertools
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from loguru import logger
from pydantic import Field, field_validator
from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InputTextMessageContent,
    MenuButtonWebApp,
    ReplyParameters,
    Update,
    WebAppInfo,
)
from telegram.error import NetworkError, RetryAfter, TimedOut
from telegram.ext import (
    Application,
    BusinessConnectionHandler,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ManagedBotUpdatedHandler,
    MessageHandler,
    filters,
)
from telegram.request import HTTPXRequest

from shibaclaw.bus.events import OutboundMessage
from shibaclaw.bus.queue import MessageBus
from shibaclaw.config.paths import get_media_dir
from shibaclaw.config.schema import Base
from shibaclaw.helpers.helpers import split_message
from shibaclaw.integrations.base import BaseChannel
from shibaclaw.integrations.telegram_rich import (
    _markdown_to_telegram_html,
    build_rich_message_body,
)
from shibaclaw.security.network import validate_url_target

_PTB_LOGGERS = (
    "telegram",
    "telegram.ext",
    "telegram._bot",
    "telegram._update",
    "telegram._telegramobject",
    "telegram.ext._application",
    "telegram.ext.Application",
    "telegram.ext._extbot",
    "telegram.ext._updater",
    "telegram.ext._utils",
)
_PREVIOUS_LEVELS: dict[str, int] = {}


def _suppress_ptb_shutdown_logs() -> None:
    """Temporarily raise PTB log levels to suppress CancelledError tracebacks on shutdown."""
    for name in _PTB_LOGGERS:
        try:
            lgr = logging.getLogger(name)
            _PREVIOUS_LEVELS[name] = lgr.level
            lgr.setLevel(logging.CRITICAL + 1)
        except Exception:
            pass


def _restore_ptb_shutdown_logs() -> None:
    """Restore PTB log levels after shutdown."""
    for name, level in _PREVIOUS_LEVELS.items():
        try:
            logging.getLogger(name).setLevel(level)
        except Exception:
            pass
    _PREVIOUS_LEVELS.clear()


TELEGRAM_MAX_MESSAGE_LEN = 4000
TELEGRAM_REPLY_CONTEXT_MAX_LEN = TELEGRAM_MAX_MESSAGE_LEN

_SEND_MAX_RETRIES = 3
_SEND_RETRY_BASE_DELAY = 0.5


def _is_message_not_modified_error(error: Exception) -> bool:
    """Return whether Telegram rejected an edit because the content is unchanged."""
    return "message is not modified" in str(error).lower()


class TelegramConfig(Base):
    """Telegram channel configuration."""

    enabled: bool = False
    token: str = ""
    allow_from: list[str] = Field(default_factory=list)

    def resolve_token(self) -> str | None:
        """Return the bot token from the encrypted vault (vault-first), falling back
        to the plain ``token`` field for backwards compatibility.

        Resolution order:
        1. Encrypted vault lookup under ``channels/telegram.token``.
        2. Plain ``token`` field (legacy / not-yet-migrated configs).
        """
        try:
            from shibaclaw.security.credential_manager import get_credential_manager

            vault_key = get_credential_manager().get_secret("channels", "telegram.token")
            if vault_key and isinstance(vault_key, str):
                return vault_key
        except Exception:
            pass
        return self.token or None

    proxy: str | None = None
    reply_to_message: bool = False
    group_policy: Literal["open", "mention", "trigger", "mention_or_trigger"] = "mention"
    trigger_words: list[str] = Field(default_factory=list)
    group_context_buffer_size: int = 10
    connection_pool_size: int = 32
    pool_timeout: float = 5.0
    # Bot API 9.3–10.x AI / agent features (require BotFather toggles where noted).
    # Security-sensitive flags default to False (opt-in). streaming is UX-only.
    streaming: bool = True
    guest_mode: bool = False
    allow_bot_messages: bool = False
    business_enabled: bool = False
    managed_bots_enabled: bool = False
    # Bot API 10.1+ Rich Messages via do_api_request (PTB 22.8 has no wrappers).
    # Opt-in: some clients still render unsupported placeholders.
    rich_messages: bool = False
    # Secretary / Chat Automation: archive inbound by default; do not auto-reply in DMs.
    business_auto_reply: bool = False
    history_max_age_hours: float = 24.0
    # When True: groups accept any member (groupPolicy still gates replies).
    # Private bot DMs stay locked to allowFrom. Chat Automation peer DMs are
    # always accepted when business_enabled (otherwise owner-only allowFrom
    # blocks the archive). Non-allowlisted senders get metadata.is_allowlisted=False.
    open_groups: bool = False
    # Public HTTPS URL for Telegram Mini App (Menu Button / BotFather).
    mini_app_url: str = ""
    # Local Bot API base, e.g. http://127.0.0.1:8081 (empty uses api.telegram.org).
    local_api_url: str = ""
    # Soft inbound media cap; Local Bot API supports files beyond the cloud 20 MiB limit.
    max_media_bytes: int = 524288000

    @field_validator("proxy", mode="before")
    @classmethod
    def _coerce_proxy(cls, v: Any) -> str | None:
        if isinstance(v, dict) or v == "":
            return None
        return v


class TelegramChannel(BaseChannel):
    """
    Telegram channel using long polling.
    Simple and reliable - no webhook/public IP needed.
    """

    name = "telegram"
    display_name = "Telegram"
    BOT_COMMANDS = [
        BotCommand("start", "Start the bot"),
        BotCommand("new", "Start a new conversation"),
        BotCommand("stop", "Stop the current task"),
        BotCommand("help", "Show available commands"),
        BotCommand("restart", "Restart the bot"),
    ]

    @classmethod
    def default_config(cls) -> dict[str, Any]:
        return TelegramConfig().model_dump(by_alias=True)

    def __init__(self, config: Any, bus: MessageBus):
        if isinstance(config, dict):
            config = TelegramConfig.model_validate(config)
        super().__init__(config, bus)
        self.config: TelegramConfig = config
        self._app: Application | None = None
        self._chat_ids: dict[str, int] = {}
        self._CHAT_IDS_CAP = 500
        self._typing_tasks: dict[str, asyncio.Task] = {}
        self._media_group_buffers: dict[str, dict] = {}
        # (chat_id, inbound_message_id) -> our outbound reply id (edit-on-user-edit)
        self._inbound_reply_map: dict[tuple[int, int], int] = {}
        self._INBOUND_REPLY_MAP_CAP = 500
        self._secretary_outbound: dict[int, set[int]] = {}
        self._SECRETARY_OUTBOUND_CAP = 40
        self._media_group_tasks: dict[str, asyncio.Task] = {}
        self._message_threads: dict[tuple[str, int], int] = {}
        self._THREADS_CAP = 1000
        self._progress_messages: dict[tuple[str, int | None], int] = {}
        self._PROGRESS_CAP = 500
        self._bot_user_id: int | None = None
        self._bot_username: str | None = None
        self._draft_ids: dict[tuple[int, int | None], int] = {}
        self._draft_id_seq = itertools.count(1)
        self._business_connections: dict[str, dict[str, Any]] = {}
        self._BUSINESS_CONNECTIONS_CAP = 200
        self._managed_bots: dict[int, dict[str, Any]] = {}
        self._MANAGED_BOTS_CAP = 200

    def _is_allowlisted(self, sender_id: str, *other_ids: str) -> bool:
        """True if sender matches allowFrom (id, username, or id|username)."""
        if super().is_allowed(sender_id, *other_ids):
            return True
        allow_list = getattr(self.config, "allow_from", [])
        if not allow_list or "*" in allow_list:
            return False
        sender_str = str(sender_id)
        if sender_str.count("|") == 1:
            sid, username = sender_str.split("|", 1)
            if sid.lstrip("-").isdigit() and username:
                if sid in allow_list or username in allow_list:
                    return True
        return False
    def is_allowed(self, sender_id: str, *other_ids: str) -> bool:
        """Ingress gate for the bus.

        When ``open_groups`` is enabled (or Chat Automation is on), handlers
        decide private vs group/business access; the bus must not re-deny.
        Otherwise preserve classic allowFrom for all chats.
        """
        if self.config.open_groups or self.config.business_enabled:
            return True
        return self._is_allowlisted(sender_id, *other_ids)
    def _sender_is_allowlisted(self, sender_id: str, username: str | None = None) -> bool:
        extras = (username,) if username else ()
        return self._is_allowlisted(sender_id, *extras)
    def _ingress_allowed(
        self,
        *,
        is_group: bool,
        has_business: bool,
        sender_id: str,
        username: str | None,
        is_guest: bool = False,
    ) -> bool:
        """Private bot DMs: allowFrom only. Groups/business: opt-in open + allowFrom.

        Guest Mode always requires allowFrom (never open to arbitrary users).
        """
        if self._is_allowlisted(sender_id, username):
            return True
        if is_guest:
            return False
        if has_business and self.config.business_enabled:
            return True
        if is_group and self.config.open_groups:
            return True
        return False

    def _build_app(self, proxy: str | None = None) -> None:
        """Build the Telegram Application with separate HTTP pools."""
        local_api_url = self.config.local_api_url.strip().rstrip("/")
        api_request = HTTPXRequest(
            connection_pool_size=self.config.connection_pool_size,
            pool_timeout=self.config.pool_timeout,
            connect_timeout=30.0,
            read_timeout=600.0 if local_api_url else 30.0,
            proxy=proxy,
        )
        poll_request = HTTPXRequest(
            connection_pool_size=4,
            pool_timeout=self.config.pool_timeout,
            connect_timeout=30.0,
            read_timeout=30.0,
            proxy=proxy,
        )
        builder = (
            Application.builder()
            .token(self.config.resolve_token() or "")
            .request(api_request)
            .get_updates_request(poll_request)
        )
        if local_api_url:
            builder = (
                builder.base_url(f"{local_api_url}/bot")
                .base_file_url(f"{local_api_url}/file/bot")
                .local_mode(True)
            )
            logger.info("Telegram using Local Bot API at {}", local_api_url)
        self._app = builder.build()

    async def start_for_sending(self) -> None:
        """Initialize the bot for outbound-only sending without starting inbound polling.
        Calls Application.initialize() so HTTP requests work, but never calls
        start_polling() so only one instance (the gateway) polls Telegram.
        """
        if not self.config.resolve_token():
            logger.warning("Telegram token not configured — outbound sending unavailable")
            return
        self._build_app(proxy=self.config.proxy or None)
        self._app.add_error_handler(self._on_error)
        await self._app.initialize()
        bot_info = await self._app.bot.get_me()
        self._bot_username = getattr(bot_info, "username", None)
        logger.info("Telegram bot @{} ready for sending (outbound-only)", self._bot_username)

    async def start(self) -> None:
        """Start the Telegram bot with long polling."""
        if not self.config.resolve_token():
            logger.error("Telegram bot token not configured")
            return
        self._running = True
        proxy = self.config.proxy or None
        self._build_app(proxy=proxy)
        self._app.add_error_handler(self._on_error)
        self._app.add_handler(CommandHandler("start", self._on_start))
        self._app.add_handler(CommandHandler("new", self._forward_command))
        self._app.add_handler(CommandHandler("stop", self._forward_command))
        self._app.add_handler(CommandHandler("restart", self._forward_command))
        self._app.add_handler(CommandHandler("help", self._on_help))
        _content_filter = (
            filters.TEXT
            | filters.PHOTO
            | filters.VOICE
            | filters.AUDIO
            | filters.Document.ALL
            | filters.VIDEO
            | filters.VIDEO_NOTE
            | filters.ANIMATION
        ) & ~filters.COMMAND
        self._app.add_handler(MessageHandler(_content_filter, self._on_message))
        self._app.add_handler(
            MessageHandler(filters.UpdateType.EDITED_MESSAGE & _content_filter, self._on_message)
        )
        if self.config.guest_mode:
            self._app.add_handler(
                MessageHandler(
                    filters.UpdateType.GUEST_MESSAGE & _content_filter, self._on_message
                )
            )
        if self.config.business_enabled:
            self._app.add_handler(
                MessageHandler(
                    filters.UpdateType.BUSINESS_MESSAGE & _content_filter, self._on_message
                )
            )
            self._app.add_handler(
                MessageHandler(
                    filters.UpdateType.EDITED_BUSINESS_MESSAGE & _content_filter,
                    self._on_message,
                )
            )
            self._app.add_handler(BusinessConnectionHandler(self._on_business_connection))
        if self.config.managed_bots_enabled:
            self._app.add_handler(ManagedBotUpdatedHandler(self._on_managed_bot))
        self._app.add_handler(CallbackQueryHandler(self._on_callback_query))
        logger.info("Starting Telegram bot (polling mode)...")
        await self._app.initialize()
        await self._app.start()
        bot_info = await self._app.bot.get_me()
        self._bot_user_id = getattr(bot_info, "id", None)
        self._bot_username = getattr(bot_info, "username", None)
        logger.info("Telegram bot @{} connected", bot_info.username)
        try:
            await self._app.bot.set_my_commands(self.BOT_COMMANDS)
            logger.debug("Telegram bot commands registered")
        except Exception as e:
            logger.warning("Failed to register bot commands: {}", e)
        await self._maybe_set_mini_app_menu_button()
        # callback_query required for inline keyboards (e.g. profile pickers).
        allowed_updates = ["message", "edited_message", "callback_query"]
        if self.config.guest_mode:
            allowed_updates.append("guest_message")
        if self.config.business_enabled:
            allowed_updates.extend(
                ["business_connection", "business_message", "edited_business_message"]
            )
        if self.config.managed_bots_enabled:
            allowed_updates.append("managed_bot")
        await self._app.updater.start_polling(
            allowed_updates=allowed_updates,
            drop_pending_updates=True,
        )
        while self._running:
            await asyncio.sleep(1)

    async def _maybe_set_mini_app_menu_button(self) -> None:
        """Point the chat menu button at channels.telegram.miniAppUrl when set."""
        url = (getattr(self.config, "mini_app_url", None) or "").strip()
        if not url or not self._app:
            return
        try:
            await self._app.bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="ShibaClaw",
                    web_app=WebAppInfo(url=url),
                )
            )
            logger.info("Telegram Mini App menu button set → {}", url)
        except Exception as e:
            logger.warning("Failed to set Telegram Mini App menu button: {}", e)

    async def stop(self) -> None:
        """Stop the Telegram bot."""
        self._running = False
        for chat_id in list(self._typing_tasks):
            self._stop_typing(chat_id)
        for task in self._media_group_tasks.values():
            task.cancel()
        self._media_group_tasks.clear()
        self._media_group_buffers.clear()
        if self._app:
            logger.info("Stopping Telegram bot...")
            _suppress_ptb_shutdown_logs()
            try:
                if self._app.updater and self._app.updater.running:
                    await self._app.updater.stop()
                await self._app.stop()
                await self._app.shutdown()
            finally:
                _restore_ptb_shutdown_logs()
            self._app = None

    @staticmethod
    def _get_media_type(path: str) -> str:
        """Guess media type from file extension."""
        ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
        if ext in ("jpg", "jpeg", "png", "gif", "webp"):
            return "photo"
        if ext == "ogg":
            return "voice"
        if ext in ("mp3", "m4a", "wav", "aac"):
            return "audio"
        return "document"

    @staticmethod
    def _is_remote_media_url(path: str) -> bool:
        return path.startswith(("http://", "https://"))

    async def send(self, msg: OutboundMessage) -> None:
        """Send a message through Telegram."""
        if not self._app:
            raise RuntimeError("Telegram bot not running")
        metadata = msg.metadata or {}
        if not metadata.get("_progress", False):
            self._stop_typing(msg.chat_id)
        # Guest Mode replies must go through answerGuestQuery (not sendMessage).
        if guest_query_id := metadata.get("guest_query_id"):
            if metadata.get("_progress"):
                return
            await self._answer_guest_query(str(guest_query_id), msg.content or "")
            return
        original_chat_id = str(msg.chat_id)
        if original_chat_id == "auto" or not original_chat_id.lstrip("-").isdigit():
            allow_list = getattr(self.config, "allow_from", [])
            valid_ids = []

            # 1. Try to extract valid chat_ids from allow_from list
            for uid in allow_list:
                uid_str = str(uid).strip()
                if "|" in uid_str:
                    part = uid_str.split("|")[0]
                    if part.lstrip("-").isdigit():
                        valid_ids.append(part)
                elif uid_str.lstrip("-").isdigit():
                    valid_ids.append(uid_str)

            # 2. Try to fallback to known active users cache
            if not valid_ids and self._chat_ids:
                known_chat_ids = list({str(v) for v in self._chat_ids.values()})
                if len(known_chat_ids) == 1:
                    valid_ids = known_chat_ids
                    logger.debug(
                        "Auto-resolving Telegram chat_id from last active user {}",
                        known_chat_ids[0],
                    )

            if len(valid_ids) == 1:
                chat_id = int(valid_ids[0])
                logger.debug(
                    "Invalid chat_id '%s', falling back to resolved user %s",
                    original_chat_id,
                    chat_id,
                )
            elif len(valid_ids) > 1:
                raise ValueError(
                    f"Cannot auto-resolve Telegram chat_id: "
                    f"multiple allowed users ({len(valid_ids)}). "
                    f"Specify a numeric chat_id explicitly."
                )
            else:
                raise ValueError(
                    f"Cannot auto-resolve Telegram chat_id from '{original_chat_id}'. "
                    f"No numeric user IDs found in allow_from. "
                    f"Ensure allow_from contains numeric Telegram user IDs, "
                    f"or send a message to the bot first so it can learn the chat_id."
                )
        else:
            try:
                chat_id = int(original_chat_id)
            except ValueError:
                logger.error("Invalid chat_id: %s", original_chat_id)
                return
        reply_to_message_id = metadata.get("message_id")
        message_thread_id = metadata.get("message_thread_id")
        if message_thread_id is None and reply_to_message_id is not None:
            message_thread_id = self._message_threads.get((msg.chat_id, reply_to_message_id))
        thread_kwargs: dict[str, Any] = {}
        if message_thread_id is not None:
            thread_kwargs["message_thread_id"] = message_thread_id
        if business_connection_id := metadata.get("business_connection_id"):
            thread_kwargs["business_connection_id"] = business_connection_id
        reply_params = None
        if self.config.reply_to_message:
            if reply_to_message_id:
                reply_params = ReplyParameters(
                    message_id=reply_to_message_id, allow_sending_without_reply=True
                )
        ask_markup = self._build_ask_inline_keyboard(metadata)
        for media_path in msg.media or []:
            try:
                media_type = self._get_media_type(media_path)
                sender = {
                    "photo": self._app.bot.send_photo,
                    "voice": self._app.bot.send_voice,
                    "audio": self._app.bot.send_audio,
                }.get(media_type, self._app.bot.send_document)
                param = (
                    "photo"
                    if media_type == "photo"
                    else media_type
                    if media_type in ("voice", "audio")
                    else "document"
                )
                if self._is_remote_media_url(media_path):
                    ok, error = validate_url_target(media_path)
                    if not ok:
                        raise ValueError(f"unsafe media URL: {error}")
                    await self._call_with_retry(
                        sender,
                        chat_id=chat_id,
                        **{param: media_path},
                        reply_parameters=reply_params,
                        **thread_kwargs,
                    )
                    continue
                from pathlib import Path

                await self._call_with_retry(
                    sender,
                    chat_id=chat_id,
                    **{param: Path(media_path)},
                    reply_parameters=reply_params,
                    **thread_kwargs,
                )
            except Exception as e:
                filename = media_path.rsplit("/", 1)[-1]
                logger.error("Failed to send media {}: {}", media_path, e)
                await self._app.bot.send_message(
                    chat_id=chat_id,
                    text=f"[Failed to send: {filename}]",
                    reply_parameters=reply_params,
                    **thread_kwargs,
                )
        if msg.content and msg.content != "[empty message]":
            is_progress = bool(metadata.get("_progress", False))
            # Structured ask: plain send with inline keyboard (skip rich/streaming).
            if ask_markup is not None and not is_progress:
                chunk = next(iter(split_message(msg.content, TELEGRAM_MAX_MESSAGE_LEN)), msg.content)
                last_mid = await self._send_text(
                    chat_id,
                    chunk,
                    reply_params,
                    thread_kwargs,
                    reply_markup=ask_markup,
                )
                inbound_mid = metadata.get("message_id")
                if last_mid is not None:
                    self._remember_inbound_reply(chat_id, inbound_mid, last_mid)
                    if metadata.get("business_connection_id"):
                        self._remember_secretary_outbound(chat_id, last_mid)
                thread_id = thread_kwargs.get("message_thread_id") if thread_kwargs else None
                await self._clear_progress_message(chat_id, thread_id)
                self._clear_draft_id(chat_id, thread_id)
                return
            use_draft = (
                self.config.streaming
                and self._is_private_chat_id(chat_id)
                and not metadata.get("business_connection_id")
            )
            use_rich = bool(self.config.rich_messages)
            edit_mid = None if is_progress else metadata.get("edit_message_id")
            last_mid = None
            thread_id_pre = thread_kwargs.get("message_thread_id") if thread_kwargs else None
            progress_id = (
                None
                if is_progress
                else self._progress_messages.get(self._progress_key(chat_id, thread_id_pre))
            )
            finalize_edit = None
            if not is_progress:
                if edit_mid is not None:
                    finalize_edit = int(edit_mid)
                elif progress_id is not None and not use_draft:
                    finalize_edit = int(progress_id)
            if finalize_edit is not None and not is_progress:
                chunks = list(split_message(msg.content, TELEGRAM_MAX_MESSAGE_LEN))
                text_body, *remaining_chunks = chunks
                if use_rich and await self._edit_rich_message(
                    chat_id, finalize_edit, text_body, thread_kwargs
                ):
                    last_mid = finalize_edit
                else:
                    last_mid = await self._send_with_streaming(
                        chat_id,
                        text_body,
                        reply_params,
                        thread_kwargs,
                        use_draft=False,
                        edit_message_id=finalize_edit,
                    )
                for chunk in remaining_chunks:
                    last_mid = await self._send_with_streaming(
                        chat_id, chunk, reply_params, thread_kwargs, use_draft=use_draft
                    )
            elif use_rich and not is_progress:
                last_mid = await self._send_rich_message(
                    chat_id, msg.content, reply_params, thread_kwargs
                )
                if last_mid is None:
                    for chunk in split_message(msg.content, TELEGRAM_MAX_MESSAGE_LEN):
                        last_mid = await self._send_with_streaming(
                            chat_id, chunk, reply_params, thread_kwargs, use_draft=use_draft
                        )
            else:
                for chunk in split_message(msg.content, TELEGRAM_MAX_MESSAGE_LEN):
                    if is_progress and use_draft:
                        if use_rich and await self._send_rich_message_draft(
                            chat_id, chunk, thread_kwargs, metadata
                        ):
                            continue
                        await self._send_message_draft(
                            chat_id, chunk, thread_kwargs, metadata
                        )
                    elif is_progress:
                        await self._send_or_edit_progress(
                            chat_id, chunk, reply_params, thread_kwargs, metadata
                        )
                    else:
                        last_mid = await self._send_with_streaming(
                            chat_id, chunk, reply_params, thread_kwargs, use_draft=use_draft
                        )
            if not is_progress:
                inbound_mid = metadata.get("message_id")
                if last_mid is not None:
                    self._remember_inbound_reply(chat_id, inbound_mid, last_mid)
                    if metadata.get("business_connection_id"):
                        self._remember_secretary_outbound(chat_id, last_mid)
                thread_id = thread_kwargs.get("message_thread_id") if thread_kwargs else None
                await self._clear_progress_message(chat_id, thread_id)
                self._clear_draft_id(chat_id, thread_id)

    async def _call_with_retry(self, fn, *args, **kwargs):
        """Call an async Telegram API function with retry on pool/network timeout."""
        for attempt in range(1, _SEND_MAX_RETRIES + 1):
            try:
                return await fn(*args, **kwargs)
            except RetryAfter as e:
                if attempt == _SEND_MAX_RETRIES:
                    raise
                delay = getattr(e, "retry_after", _SEND_RETRY_BASE_DELAY)
                logger.warning(
                    "Telegram rate limit (attempt {}/{}), retrying in {:.1f}s",
                    attempt,
                    _SEND_MAX_RETRIES,
                    delay,
                )
                await asyncio.sleep(delay)
            except (TimedOut, NetworkError) as e:
                if attempt == _SEND_MAX_RETRIES:
                    raise
                delay = _SEND_RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.warning(
                    "Telegram network error: {} (attempt {}/{}), retrying in {:.1f}s",
                    e,
                    attempt,
                    _SEND_MAX_RETRIES,
                    delay,
                )
                await asyncio.sleep(delay)

    def _progress_key(self, chat_id: int, thread_id: int | None) -> tuple[int, int | None]:
        return (chat_id, thread_id)

    def _cap_progress_messages(self) -> None:
        while len(self._progress_messages) > self._PROGRESS_CAP:
            self._progress_messages.pop(next(iter(self._progress_messages)))

    async def _edit_progress_message(
        self,
        chat_id: int,
        message_id: int,
        text: str,
    ) -> bool:
        """Edit an existing progress message. Returns True on success."""
        try:
            html = _markdown_to_telegram_html(text)
            await self._call_with_retry(
                self._app.bot.edit_message_text,
                chat_id=chat_id,
                message_id=message_id,
                text=html,
                parse_mode="HTML",
            )
            return True
        except (NetworkError, RetryAfter, TimedOut) as e:
            if _is_message_not_modified_error(e):
                return True
            raise
        except Exception as e:
            if _is_message_not_modified_error(e):
                return True
            err_str = str(e).lower()
            if "parse" not in err_str and "entit" not in err_str:
                logger.warning("Failed to edit progress message {}: {}", message_id, e)
                return False
            logger.debug("HTML parse failed for editing progress message {}, falling back to plain text: {}", message_id, e)
        try:
            await self._call_with_retry(
                self._app.bot.edit_message_text,
                chat_id=chat_id,
                message_id=message_id,
                text=text,
            )
            return True
        except (NetworkError, RetryAfter, TimedOut) as e:
            if _is_message_not_modified_error(e):
                return True
            raise
        except Exception as e:
            if _is_message_not_modified_error(e):
                return True
            logger.warning("Failed to edit progress message {} with plain text: {}", message_id, e)
            return False

    async def _send_or_edit_progress(
        self,
        chat_id: int,
        text: str,
        reply_params=None,
        thread_kwargs: dict | None = None,
        metadata: dict | None = None,
    ) -> None:
        """Send the first progress message or edit an existing one."""
        thread_id = thread_kwargs.get("message_thread_id") if thread_kwargs else None
        key = self._progress_key(chat_id, thread_id)
        # User-edit path: stream into the prior reply instead of a new bubble.
        seed = (metadata or {}).get("edit_message_id")
        if seed is not None and key not in self._progress_messages:
            self._progress_messages[key] = int(seed)
        existing_id = self._progress_messages.get(key)
        if existing_id is not None:
            success = await self._edit_progress_message(chat_id, existing_id, text)
            if success:
                return
            self._progress_messages.pop(key, None)
        try:
            html = _markdown_to_telegram_html(text)
            msg_obj = await self._call_with_retry(
                self._app.bot.send_message,
                chat_id=chat_id,
                text=html,
                parse_mode="HTML",
                reply_parameters=reply_params,
                **(thread_kwargs or {}),
            )
        except (NetworkError, RetryAfter, TimedOut):
            raise
        except Exception as e:
            err_str = str(e).lower()
            if "parse" not in err_str and "entit" not in err_str:
                logger.error("Error sending Telegram progress message: {}", e)
                return
            logger.warning("HTML parse failed for progress, falling back to plain text: {}", e)
            try:
                msg_obj = await self._call_with_retry(
                    self._app.bot.send_message,
                    chat_id=chat_id,
                    text=text,
                    reply_parameters=reply_params,
                    **(thread_kwargs or {}),
                )
            except (NetworkError, RetryAfter, TimedOut):
                raise
            except Exception as e2:
                logger.error("Error sending Telegram progress message (plain text): {}", e2)
                return
        if msg_obj and getattr(msg_obj, "message_id", None) is not None:
            self._progress_messages[key] = msg_obj.message_id
            self._cap_progress_messages()

    async def _clear_progress_message(self, chat_id: int, thread_id: int | None) -> None:
        self._progress_messages.pop(self._progress_key(chat_id, thread_id), None)

    async def _send_text(
        self,
        chat_id: int,
        text: str,
        reply_params=None,
        thread_kwargs: dict | None = None,
        *,
        edit_message_id: int | None = None,
        reply_markup=None,
    ) -> int | None:
        """Send or edit a plain text message with HTML fallback. Returns message_id."""
        tk = dict(thread_kwargs or {})
        biz = tk.get("business_connection_id")
        if edit_message_id is not None:
            edit_kw: dict[str, Any] = {}
            if biz:
                edit_kw["business_connection_id"] = biz
            try:
                html = _markdown_to_telegram_html(text)
                await self._call_with_retry(
                    self._app.bot.edit_message_text,
                    chat_id=chat_id,
                    message_id=edit_message_id,
                    text=html,
                    parse_mode="HTML",
                    **edit_kw,
                )
                return int(edit_message_id)
            except (NetworkError, RetryAfter, TimedOut) as e:
                if _is_message_not_modified_error(e):
                    return int(edit_message_id)
                raise
            except Exception as e:
                if _is_message_not_modified_error(e):
                    return int(edit_message_id)
                err_str = str(e).lower()
                if "parse" in err_str or "entit" in err_str:
                    try:
                        await self._call_with_retry(
                            self._app.bot.edit_message_text,
                            chat_id=chat_id,
                            message_id=edit_message_id,
                            text=text,
                            **edit_kw,
                        )
                        return int(edit_message_id)
                    except (NetworkError, RetryAfter, TimedOut) as e2:
                        if _is_message_not_modified_error(e2):
                            return int(edit_message_id)
                        raise
                    except Exception as e2:
                        if _is_message_not_modified_error(e2):
                            return int(edit_message_id)
                        logger.warning(
                            "Failed to edit message {} (plain), falling back to send: {}",
                            edit_message_id,
                            e2,
                        )
                else:
                    logger.warning(
                        "Failed to edit message {}, falling back to send: {}",
                        edit_message_id,
                        e,
                    )
        send_extra: dict[str, Any] = {}
        if reply_markup is not None:
            send_extra["reply_markup"] = reply_markup
        try:
            html = _markdown_to_telegram_html(text)
            sent = await self._call_with_retry(
                self._app.bot.send_message,
                chat_id=chat_id,
                text=html,
                parse_mode="HTML",
                reply_parameters=reply_params,
                **tk,
                **send_extra,
            )
            return getattr(sent, "message_id", None)
        except (NetworkError, RetryAfter, TimedOut):
            raise
        except Exception as e:
            err_str = str(e).lower()
            if "parse" not in err_str and "entit" not in err_str:
                raise
            logger.warning("HTML parse failed, falling back to plain text: {}", e)
        try:
            sent = await self._call_with_retry(
                self._app.bot.send_message,
                chat_id=chat_id,
                text=text,
                reply_parameters=reply_params,
                **tk,
                **send_extra,
            )
            return getattr(sent, "message_id", None)
        except (NetworkError, RetryAfter, TimedOut):
            raise
        except Exception as e2:
            logger.error("Error sending Telegram message: {}", e2)
            raise

    @staticmethod
    def _build_ask_inline_keyboard(metadata: dict[str, Any]) -> InlineKeyboardMarkup | None:
        """Build InlineKeyboardMarkup from ask metadata, or None.

        Uses compact ``ask:{request_id}:{index}`` callback_data to stay under
        Telegram's 64-byte limit (option ids are resolved from hub meta).
        """
        rid = str(metadata.get("ask_request_id") or "").strip()
        options = metadata.get("inline_keyboard")
        if not rid or not isinstance(options, list) or not options:
            return None
        # Keep request_id short enough: ask: + rid + : + idx ≤ 64
        if len(f"ask:{rid}:99".encode("utf-8")) > 64:
            rid = rid[:12]
        rows: list[list[InlineKeyboardButton]] = []
        row: list[InlineKeyboardButton] = []
        for idx, opt in enumerate(options):
            if not isinstance(opt, dict):
                continue
            oid = str(opt.get("id") or "").strip()
            label = str(opt.get("label") or oid).strip()
            if not oid or not label:
                continue
            cb = f"ask:{rid}:{idx}"
            row.append(InlineKeyboardButton(text=label[:64], callback_data=cb))
            if len(row) >= 2:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
        if not rows:
            return None
        return InlineKeyboardMarkup(rows)

    async def _on_callback_query(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Resolve structured ask_user choices from inline keyboard taps."""
        cq = update.callback_query
        if not cq or not cq.data:
            return
        data = cq.data
        if not data.startswith("ask:"):
            try:
                await cq.answer()
            except Exception:
                pass
            return
        parts = data.split(":", 2)
        if len(parts) < 3:
            try:
                await cq.answer()
            except Exception:
                pass
            return
        _, request_id, option_ref = parts

        from shibaclaw.agent.interactive import get_interactive_hub

        hub = get_interactive_hub()
        pending = hub.get_pending_meta(request_id) or {}

        user = cq.from_user
        uid = str(user.id) if user else ""
        uname = getattr(user, "username", None) if user else None
        allowed_ids = {
            str(x)
            for x in (pending.get("allowed_user_ids") or [])
            if x is not None and str(x).strip()
        }
        initiator = str(pending.get("initiator_user_id") or "").strip()
        if initiator:
            allowed_ids.add(initiator)

        authorized = False
        if uid and self._sender_is_allowlisted(uid, uname):
            authorized = True
        elif uid and uid in allowed_ids:
            authorized = True

        if not authorized:
            try:
                await cq.answer(text="Not allowed to answer this prompt.", show_alert=True)
            except Exception:
                pass
            logger.warning(
                "Telegram ask callback denied for user {} on request {}",
                uid,
                request_id,
            )
            return

        response: dict[str, Any] = {"ok": True}
        # Prefer index form; fall back to option_id for older messages.
        if option_ref.isdigit():
            response["option_index"] = int(option_ref)
            opts = pending.get("options") if isinstance(pending.get("options"), list) else []
            try:
                opt = opts[int(option_ref)]
                if isinstance(opt, dict):
                    response["option_id"] = opt.get("id")
                    response["label"] = opt.get("label") or opt.get("id")
            except (IndexError, TypeError, ValueError):
                response["option_id"] = option_ref
                response["label"] = option_ref
        else:
            response["option_id"] = option_ref
            response["label"] = option_ref
            try:
                markup = getattr(cq.message, "reply_markup", None) if cq.message else None
                for brow in getattr(markup, "inline_keyboard", None) or []:
                    for btn in brow:
                        if getattr(btn, "callback_data", None) == data:
                            response["label"] = getattr(btn, "text", None) or option_ref
                            break
            except Exception:
                pass

        try:
            await cq.answer(text=f"Selected: {response.get('label', '')}"[:200])
        except Exception:
            pass
        try:
            hub.resolve(request_id, response)
        except Exception as e:
            logger.warning("ask callback resolve failed: {}", e)

    @staticmethod
    def _is_private_chat_id(chat_id: int) -> bool:
        """Telegram private chats use positive user ids; groups/channels are negative."""
        return chat_id > 0

    def _draft_id_for(
        self, chat_id: int, thread_id: int | None, metadata: dict[str, Any] | None = None
    ) -> int:
        """Stable draft id for sendMessageDraft (must survive process restart).

        Prefer inbound ``message_id`` (deterministic). Fall back to a process-local
        counter only when metadata has no message id.
        """
        key = (chat_id, thread_id)
        if key not in self._draft_ids:
            seed = metadata.get("message_id") if metadata else None
            if seed is not None:
                # message_id is unique per chat; keep in positive 31-bit range.
                raw = int(seed) & 0x7FFFFFFF
                self._draft_ids[key] = raw or 1
            else:
                self._draft_ids[key] = next(self._draft_id_seq)
        return self._draft_ids[key]

    def _clear_draft_id(self, chat_id: int, thread_id: int | None) -> None:
        self._draft_ids.pop((chat_id, thread_id), None)

    async def _send_message_draft(
        self,
        chat_id: int,
        text: str,
        thread_kwargs: dict | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Stream a partial reply via Bot API sendMessageDraft (private chats only)."""
        thread_id = (thread_kwargs or {}).get("message_thread_id")
        draft_id = self._draft_id_for(chat_id, thread_id, metadata)
        kwargs: dict[str, Any] = {
            "chat_id": chat_id,
            "draft_id": draft_id,
            "text": text or "",
        }
        if thread_id is not None:
            kwargs["message_thread_id"] = thread_id
        try:
            await self._call_with_retry(self._app.bot.send_message_draft, **kwargs)
        except Exception as e:
            logger.debug("Telegram sendMessageDraft failed (falling back): {}", e)

    def _rich_api_kwargs(
        self,
        chat_id: int,
        text: str,
        thread_kwargs: dict | None = None,
        reply_params=None,
        *,
        message_id: int | None = None,
        draft_id: int | None = None,
        rich_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build kwargs for sendRichMessage / sendRichMessageDraft / editMessageText."""
        body = rich_body if rich_body is not None else build_rich_message_body(text or "")
        kwargs: dict[str, Any] = {
            "chat_id": chat_id,
            "rich_message": body,
        }
        tk = thread_kwargs or {}
        if tk.get("message_thread_id") is not None:
            kwargs["message_thread_id"] = tk["message_thread_id"]
        if tk.get("business_connection_id"):
            kwargs["business_connection_id"] = tk["business_connection_id"]
        if message_id is not None:
            kwargs["message_id"] = message_id
        if draft_id is not None:
            kwargs["draft_id"] = draft_id
        if reply_params is not None and message_id is None and draft_id is None:
            # ReplyParameters serializes via PTB; dict also works for raw API.
            kwargs["reply_parameters"] = reply_params
        return kwargs

    async def _send_rich_message(
        self,
        chat_id: int,
        markdown: str,
        reply_params=None,
        thread_kwargs: dict | None = None,
    ) -> int | None:
        """Bot API 10.1 sendRichMessage via do_api_request. Returns message_id or None."""
        if not self._app:
            return None
        body = build_rich_message_body(markdown or "")
        attempts: list[dict[str, Any]] = [body]
        # If auto-blocks fail, retry plain markdown once.
        if "blocks" in body:
            attempts.append({"markdown": markdown or ""})
        last_err: Exception | None = None
        for attempt_body in attempts:
            try:
                result = await self._call_with_retry(
                    self._app.bot.do_api_request,
                    "sendRichMessage",
                    api_kwargs=self._rich_api_kwargs(
                        chat_id,
                        markdown,
                        thread_kwargs,
                        reply_params,
                        rich_body=attempt_body,
                    ),
                )
                if isinstance(result, dict) and result.get("message_id") is not None:
                    return int(result["message_id"])
                mid = getattr(result, "message_id", None)
                return int(mid) if mid is not None else None
            except (NetworkError, RetryAfter, TimedOut):
                raise
            except Exception as e:
                last_err = e
                continue
        logger.warning("Telegram sendRichMessage failed, falling back: {}", last_err)
        return None

    async def _send_rich_message_draft(
        self,
        chat_id: int,
        markdown: str,
        thread_kwargs: dict | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Bot API 10.1 sendRichMessageDraft (private chats). True on success."""
        if not self._app:
            return False
        thread_id = (thread_kwargs or {}).get("message_thread_id")
        draft_id = self._draft_id_for(chat_id, thread_id, metadata)
        body = build_rich_message_body(markdown or "")
        attempts: list[dict[str, Any]] = [body]
        if "blocks" in body:
            attempts.append({"markdown": markdown or ""})
        for attempt_body in attempts:
            try:
                await self._call_with_retry(
                    self._app.bot.do_api_request,
                    "sendRichMessageDraft",
                    api_kwargs=self._rich_api_kwargs(
                        chat_id,
                        markdown,
                        thread_kwargs,
                        draft_id=draft_id,
                        rich_body=attempt_body,
                    ),
                )
                return True
            except (NetworkError, RetryAfter, TimedOut):
                raise
            except Exception as e:
                logger.debug("Telegram sendRichMessageDraft failed (falling back): {}", e)
        return False

    async def _edit_rich_message(
        self,
        chat_id: int,
        message_id: int,
        markdown: str,
        thread_kwargs: dict | None = None,
    ) -> bool:
        """editMessageText with rich_message. True on success."""
        if not self._app:
            return False
        body = build_rich_message_body(markdown or "")
        attempts: list[dict[str, Any]] = [body]
        if "blocks" in body:
            attempts.append({"markdown": markdown or ""})
        last_err: Exception | None = None
        for attempt_body in attempts:
            try:
                await self._call_with_retry(
                    self._app.bot.do_api_request,
                    "editMessageText",
                    api_kwargs=self._rich_api_kwargs(
                        chat_id,
                        markdown,
                        thread_kwargs,
                        message_id=message_id,
                        rich_body=attempt_body,
                    ),
                )
                return True
            except (NetworkError, RetryAfter, TimedOut) as e:
                if _is_message_not_modified_error(e):
                    return True
                raise
            except Exception as e:
                if _is_message_not_modified_error(e):
                    return True
                last_err = e
                continue
        logger.warning("Telegram editMessageText(rich) failed, falling back: {}", last_err)
        return False

    def _guest_result_title(self) -> str:
        """InlineQueryResultArticle title for Guest Mode answers."""
        if self._bot_username:
            return f"@{self._bot_username}"
        return "ShibaClaw"

    async def _answer_guest_query(self, guest_query_id: str, text: str) -> None:
        """Reply to a Guest Mode mention via answerGuestQuery."""
        body = (text or "").strip() or "…"
        # Inline result title is required; keep body in the message content.
        result = InlineQueryResultArticle(
            id=guest_query_id[:64] or "guest",
            title=self._guest_result_title(),
            description=body[:120],
            input_message_content=InputTextMessageContent(message_text=body[:TELEGRAM_MAX_MESSAGE_LEN]),
        )
        try:
            await self._call_with_retry(
                self._app.bot.answer_guest_query,
                guest_query_id=guest_query_id,
                result=result,
            )
        except Exception as e:
            logger.error("Telegram answerGuestQuery failed: {}", e)
            raise

    def _store_capped(self, store: dict, key: Any, value: Any, cap: int) -> None:
        """Insert into an insertion-ordered dict, evicting oldest entries past *cap*."""
        store.pop(key, None)
        store[key] = value
        while len(store) > cap:
            store.pop(next(iter(store)))

    async def _on_business_connection(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Track Chat Automation / Business account connections."""
        conn = update.business_connection
        if not conn:
            return
        self._store_capped(
            self._business_connections,
            conn.id,
            {
                "user_id": getattr(conn.user, "id", None),
                "user_chat_id": getattr(conn, "user_chat_id", None),
                "is_enabled": getattr(conn, "is_enabled", None),
                "rights": str(getattr(conn, "rights", None)),
            },
            self._BUSINESS_CONNECTIONS_CAP,
        )
        logger.info(
            "Telegram business connection {} enabled={} user={}",
            conn.id,
            getattr(conn, "is_enabled", None),
            getattr(conn.user, "id", None),
        )

    async def _on_managed_bot(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle ManagedBotUpdated (bot created/token rotated by a manager bot)."""
        mb = update.managed_bot
        if not mb:
            return
        bot_user = getattr(mb, "bot", None) or getattr(mb, "user", None)
        bot_id = getattr(bot_user, "id", None) if bot_user else getattr(mb, "bot_id", None)
        info = {
            "bot_id": bot_id,
            "username": getattr(bot_user, "username", None) if bot_user else None,
            "can_join_groups": getattr(mb, "can_join_groups", None),
            "raw": str(mb),
        }
        if bot_id is not None:
            self._store_capped(self._managed_bots, int(bot_id), info, self._MANAGED_BOTS_CAP)
        logger.info("Telegram managed bot update: {}", info)

    async def _send_with_streaming(
        self,
        chat_id: int,
        text: str,
        reply_params=None,
        thread_kwargs: dict | None = None,
        *,
        use_draft: bool = False,
        edit_message_id: int | None = None,
    ) -> int | None:
        """Send or edit final message text. Optional last draft flash for private chats."""
        if use_draft and text and edit_message_id is None:
            # Final animated draft, then persist with sendMessage (API contract).
            await self._send_message_draft(chat_id, text, thread_kwargs)
        return await self._send_text(
            chat_id,
            text,
            reply_params,
            thread_kwargs,
            edit_message_id=edit_message_id,
        )


    def _remember_inbound_reply(
        self, chat_id: int, inbound_mid: int | None, outbound_mid: int | None
    ) -> None:
        """Map user message -> our reply so user edits can update in place."""
        if inbound_mid is None or outbound_mid is None:
            return
        key = (int(chat_id), int(inbound_mid))
        self._inbound_reply_map[key] = int(outbound_mid)
        while len(self._inbound_reply_map) > self._INBOUND_REPLY_MAP_CAP:
            self._inbound_reply_map.pop(next(iter(self._inbound_reply_map)))

    def _lookup_inbound_reply(self, chat_id: int, inbound_mid: int | None) -> int | None:
        if inbound_mid is None:
            return None
        return self._inbound_reply_map.get((int(chat_id), int(inbound_mid)))

    async def _on_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        if not update.message or not update.effective_user:
            return
        user = update.effective_user
        sender_id = self._sender_id(user)
        is_group = update.message.chat.type in ("group", "supergroup")
        if not self._ingress_allowed(
            is_group=is_group,
            has_business=False,
            sender_id=sender_id,
            username=user.username,
        ):
            return
        await update.message.reply_text(
            f"👋 Hi {user.first_name}! I'm shibaclaw.\n\n"
            "Send me a message and I'll respond!\n"
            "Type /help to see available commands."
        )

    async def _on_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command."""
        if not update.message or not update.effective_user:
            return
        user = update.effective_user
        sender_id = self._sender_id(user)
        is_group = update.message.chat.type in ("group", "supergroup")
        if not self._ingress_allowed(
            is_group=is_group,
            has_business=False,
            sender_id=sender_id,
            username=user.username,
        ):
            return
        await update.message.reply_text(
            "🐕 shibaclaw commands:\n"
            "/new — Start a new conversation\n"
            "/stop — Stop the current task\n"
            "/restart — Restart the bot\n"
            "/help — Show available commands"
        )

    def _remember_secretary_outbound(self, chat_id: int, message_id: int | None) -> None:
        """Keep a bounded set of business replies that can be replied-to to summon."""
        if message_id is None:
            return
        outbound = self._secretary_outbound.setdefault(chat_id, set())
        outbound.add(message_id)
        while len(outbound) > self._SECRETARY_OUTBOUND_CAP:
            outbound.pop()
        while len(self._secretary_outbound) > self._CHAT_IDS_CAP:
            self._secretary_outbound.pop(next(iter(self._secretary_outbound)))
    async def _message_has_bot_mention(self, message) -> bool:
        """Whether this message is a Guest Mode @mention."""
        bot_id, username = await self._ensure_bot_identity()
        if not username:
            return False
        return self._has_mention_entity(
            message.text or "", getattr(message, "entities", None), username, bot_id
        ) or self._has_mention_entity(
            message.caption or "", getattr(message, "caption_entities", None), username, bot_id
        )
    async def _is_secretary_summon(self, message) -> bool:
        """Return true for a trigger word or reply to bot/secretary output."""
        combined = f"{message.text or ''} {message.caption or ''}".lower()
        for word in self.config.trigger_words:
            trigger = str(word).strip().lower()
            if trigger and trigger in combined:
                return True
        reply = getattr(message, "reply_to_message", None)
        if reply is None:
            return False
        bot_id, _ = await self._ensure_bot_identity()
        reply_user = getattr(reply, "from_user", None)
        if bot_id and reply_user and getattr(reply_user, "id", None) == bot_id:
            return True
        reply_id = getattr(reply, "message_id", None)
        return reply_id in self._secretary_outbound.get(int(message.chat_id), set())

    @staticmethod
    def _sender_id(user) -> str:
        """Build sender_id with username for allowlist matching."""
        sid = str(user.id)
        return f"{sid}|{user.username}" if user.username else sid

    @staticmethod
    def _derive_topic_session_key(message) -> str | None:
        """Derive topic-scoped session key for forum topics (groups and private DMs).

        Bot API 9.3+ supports topics in private chats with bots. When
        ``message_thread_id`` is present, isolate history/profile from the
        unscoped ``telegram:{chat_id}`` session — same as group forums.
        """
        message_thread_id = getattr(message, "message_thread_id", None)
        if message_thread_id is None:
            return None
        return f"telegram:{message.chat_id}:topic:{message_thread_id}"

    @staticmethod
    def _build_message_metadata(message, user, *, guest: bool = False) -> dict:
        """Build common Telegram inbound metadata payload."""
        reply_to = getattr(message, "reply_to_message", None)
        meta: dict[str, Any] = {
            "message_id": message.message_id,
            "user_id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "is_group": message.chat.type != "private",
            "chat_title": getattr(message.chat, "title", None),
            "message_thread_id": getattr(message, "message_thread_id", None),
            "is_forum": bool(getattr(message.chat, "is_forum", False)),
            "reply_to_message_id": getattr(reply_to, "message_id", None) if reply_to else None,
            "is_bot_sender": bool(getattr(user, "is_bot", False)),
        }
        if guest or getattr(message, "guest_query_id", None):
            meta["guest_query_id"] = getattr(message, "guest_query_id", None)
            meta["is_guest"] = True
        if business_connection_id := getattr(message, "business_connection_id", None):
            meta["business_connection_id"] = business_connection_id
        if fwd := TelegramChannel._extract_forward_info(message):
            meta.update(fwd)
        return meta

    @staticmethod
    def _extract_forward_info(message) -> dict | None:
        """Parse Message.forward_origin into a small metadata dict + label."""
        origin = getattr(message, "forward_origin", None)
        if origin is None and not getattr(message, "is_automatic_forward", False):
            return None
        info: dict[str, Any] = {"is_forward": True}
        label = "unknown"
        otype = getattr(origin, "type", None) or type(origin).__name__
        info["forward_type"] = str(otype)
        sender_user = getattr(origin, "sender_user", None)
        if sender_user is not None:
            name = (
                getattr(sender_user, "full_name", None)
                or getattr(sender_user, "first_name", None)
                or getattr(sender_user, "username", None)
                or str(getattr(sender_user, "id", "user"))
            )
            info["forward_from_user_id"] = getattr(sender_user, "id", None)
            info["forward_from_username"] = getattr(sender_user, "username", None)
            info["forward_from_name"] = name
            uname = getattr(sender_user, "username", None)
            label = f"{name} (@{uname})" if uname else str(name)
        elif getattr(origin, "sender_user_name", None):
            info["forward_from_name"] = origin.sender_user_name
            label = str(origin.sender_user_name)
        else:
            chat = getattr(origin, "sender_chat", None) or getattr(origin, "chat", None)
            if chat is not None:
                title = (
                    getattr(chat, "title", None)
                    or getattr(chat, "full_name", None)
                    or getattr(chat, "username", None)
                    or str(getattr(chat, "id", "chat"))
                )
                info["forward_from_chat_id"] = getattr(chat, "id", None)
                info["forward_from_chat_title"] = title
                sig = getattr(origin, "author_signature", None)
                info["forward_author_signature"] = sig
                label = f"{title}" + (f" / {sig}" if sig else "")
            elif getattr(message, "is_automatic_forward", False):
                label = "linked channel"
        info["forward_label"] = label
        return info

    @staticmethod
    def _extract_reply_context(message) -> str | None:
        """Extract text from the message being replied to, if any."""
        reply = getattr(message, "reply_to_message", None)
        if not reply:
            return None
        text = getattr(reply, "text", None) or getattr(reply, "caption", None) or ""
        if len(text) > TELEGRAM_REPLY_CONTEXT_MAX_LEN:
            text = text[:TELEGRAM_REPLY_CONTEXT_MAX_LEN] + "..."
        return f"[Reply to: {text}]" if text else None

    def _resolve_local_bot_api_path(self, file_path: str) -> Path | None:
        """Map a Local Bot API path to a host file inside the bot data directory.

        Only paths that resolve inside ``~/.shibaclaw/telegram-bot-api/data`` are
        accepted — never arbitrary host files from a Local Bot API response.
        """
        if not file_path or not str(file_path).strip():
            return None

        data_root = (Path.home() / ".shibaclaw/telegram-bot-api/data").resolve()
        container_root = Path("/var/lib/telegram-bot-api")
        path = Path(file_path)

        candidates: list[Path] = []
        try:
            candidates.append(data_root / path.relative_to(container_root))
        except ValueError:
            pass
        if path.is_absolute():
            candidates.append(path)
        else:
            candidates.append(data_root / path)

        for candidate in candidates:
            try:
                resolved = candidate.resolve()
                resolved.relative_to(data_root)
            except (OSError, ValueError):
                continue
            if resolved.is_file():
                return resolved
        return None

    async def _download_message_media(
        self, msg, *, add_failure_content: bool = False
    ) -> tuple[list[str], list[str]]:
        """Download media from a message (current or reply). Returns (media_paths, content_parts)."""
        media_file = None
        media_type = None
        if getattr(msg, "photo", None):
            media_file = msg.photo[-1]
            media_type = "image"
        elif getattr(msg, "voice", None):
            media_file = msg.voice
            media_type = "voice"
        elif getattr(msg, "audio", None):
            media_file = msg.audio
            media_type = "audio"
        elif getattr(msg, "document", None):
            media_file = msg.document
            media_type = "file"
        elif getattr(msg, "video", None):
            media_file = msg.video
            media_type = "video"
        elif getattr(msg, "video_note", None):
            media_file = msg.video_note
            media_type = "video"
        elif getattr(msg, "animation", None):
            media_file = msg.animation
            media_type = "animation"
        if not media_file or not self._app:
            return [], []

        file_size = int(getattr(media_file, "file_size", 0) or 0)
        original_name = getattr(media_file, "file_name", None)
        local_api = bool(self.config.local_api_url.strip())
        cloud_limit = 20 * 1024 * 1024
        configured_limit = max(0, self.config.max_media_bytes)
        max_download_bytes = configured_limit or (500 * 1024 * 1024 if local_api else cloud_limit)
        if not local_api:
            max_download_bytes = min(max_download_bytes, cloud_limit)

        size_mib = file_size / (1024 * 1024) if file_size else 0
        size_label = f" ({size_mib:.1f} MiB)" if size_mib else ""
        limit_mib = max_download_bytes / (1024 * 1024)
        limit_kind = "configured Local Bot API" if local_api else "Telegram cloud Bot API"
        limit_hint = (
            "raise channels.telegram.maxMediaBytes"
            if local_api
            else "configure channels.telegram.localApiUrl or send a smaller file"
        )
        too_large_content = (
            f"[{media_type}: too large{size_label} — {limit_kind} limit "
            f"{limit_mib:g} MiB; {limit_hint}]"
        )
        if max_download_bytes and file_size > max_download_bytes:
            logger.warning(
                "Skipping Telegram media above download limit (size={} limit={} name={})",
                file_size,
                max_download_bytes,
                original_name,
            )
            return ([], [too_large_content]) if add_failure_content else ([], [])

        try:
            request_timeout = 600 if local_api else 300
            file = await self._app.bot.get_file(
                media_file.file_id,
                read_timeout=request_timeout,
                write_timeout=request_timeout,
                connect_timeout=60,
            )
            ext = self._get_extension(
                media_type,
                getattr(media_file, "mime_type", None),
                original_name,
            )
            media_dir = get_media_dir("telegram")
            unique_id = getattr(media_file, "file_unique_id", media_file.file_id)
            filename = f"{unique_id}{ext}"
            if original_name:
                original_basename = Path(original_name).name
                safe_name = "".join(
                    char if char.isalnum() or char in "-_." else "_" for char in original_basename
                )[:120]
                if safe_name:
                    if not Path(safe_name).suffix and ext:
                        safe_name += ext
                    filename = f"{unique_id}_{safe_name}"
            file_path = media_dir / filename

            copied = False
            remote_path = getattr(file, "file_path", None)
            if local_api and remote_path:
                host_path = self._resolve_local_bot_api_path(remote_path)
                if host_path is not None:
                    if host_path.resolve() != file_path.resolve():
                        await asyncio.to_thread(shutil.copy2, host_path, file_path)
                    copied = True
            if not copied:
                await file.download_to_drive(
                    str(file_path),
                    read_timeout=request_timeout,
                    write_timeout=request_timeout,
                )

            path_str = str(file_path)
            if media_type in ("voice", "audio"):
                transcription = await self.transcribe_audio(file_path)
                if transcription:
                    logger.info("Transcribed {}: {}...", media_type, transcription[:50])
                    return [path_str], [f"[transcription: {transcription}]"]
                return [path_str], [f"[{media_type}: {path_str}]"]
            if media_type == "file" and original_name:
                return [path_str], [f"[file: {original_name} → {path_str}]"]
            return [path_str], [f"[{media_type}: {path_str}]"]
        except Exception as e:
            error = str(e)
            error_lower = error.lower()
            too_large = file_size > max_download_bytes or any(
                marker in error_lower for marker in ("too big", "file_too_big")
            )
            logger.warning(
                "Failed to download Telegram media (size={} name={}): {}",
                file_size,
                original_name,
                e,
            )
            if not add_failure_content:
                return [], []
            if too_large:
                return [], [too_large_content]
            return [], [f"[{media_type}: download failed: {error[:120]}]"]

    async def _ensure_bot_identity(self) -> tuple[int | None, str | None]:
        """Load bot identity once and reuse it for mention/reply checks."""
        if self._bot_user_id is not None or self._bot_username is not None:
            return self._bot_user_id, self._bot_username
        if not self._app:
            return None, None
        bot_info = await self._app.bot.get_me()
        self._bot_user_id = getattr(bot_info, "id", None)
        self._bot_username = getattr(bot_info, "username", None)
        return self._bot_user_id, self._bot_username

    @staticmethod
    def _has_mention_entity(
        text: str,
        entities,
        bot_username: str,
        bot_id: int | None,
    ) -> bool:
        """Check Telegram mention entities against the bot username."""
        handle = f"@{bot_username}".lower()
        for entity in entities or []:
            entity_type = getattr(entity, "type", None)
            if entity_type == "text_mention":
                user = getattr(entity, "user", None)
                if user is not None and bot_id is not None and getattr(user, "id", None) == bot_id:
                    return True
                continue
            if entity_type != "mention":
                continue
            offset = getattr(entity, "offset", None)
            length = getattr(entity, "length", None)
            if offset is None or length is None:
                continue
            if text[offset : offset + length].lower() == handle:
                return True
        return handle in text.lower()

    async def _is_group_message_for_bot(self, message) -> bool:
        """Allow group messages based on the configured group_policy."""
        if message.chat.type == "private" or self.config.group_policy == "open":
            return True
        text = message.text or ""
        caption = message.caption or ""
        combined_text = f"{text} {caption}".lower()
        policy = self.config.group_policy
        if policy in ("trigger", "mention_or_trigger"):
            for word in self.config.trigger_words:
                if word.lower() in combined_text:
                    return True
        if policy in ("mention", "mention_or_trigger"):
            bot_id, bot_username = await self._ensure_bot_identity()
            if bot_username:
                if self._has_mention_entity(
                    text,
                    getattr(message, "entities", None),
                    bot_username,
                    bot_id,
                ):
                    return True
                if self._has_mention_entity(
                    caption,
                    getattr(message, "caption_entities", None),
                    bot_username,
                    bot_id,
                ):
                    return True
            reply_msg = getattr(message, "reply_to_message", None)
            reply_user = getattr(reply_msg, "from_user", None)
            return bool(bot_id and reply_user and reply_user.id == bot_id)
        return False

    def _remember_thread_context(self, message) -> None:
        """Cache topic thread id by chat/message id for follow-up replies."""
        message_thread_id = getattr(message, "message_thread_id", None)
        if message_thread_id is not None:
            key = (message.chat_id, message.message_id)
            self._message_threads[key] = message_thread_id
            while len(self._message_threads) > self._THREADS_CAP:
                self._message_threads.pop(next(iter(self._message_threads)))

    async def _forward_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Forward slash commands to the bus for unified handling in ShibaBrain."""
        if not update.message or not update.effective_user:
            return
        message = update.message
        user = update.effective_user
        sender_id = self._sender_id(user)
        is_group = message.chat.type in ("group", "supergroup")
        has_business = bool(getattr(message, "business_connection_id", None))
        if not self._ingress_allowed(
            is_group=is_group,
            has_business=has_business,
            sender_id=sender_id,
            username=user.username,
        ):
            return
        cmd = (message.text or "").strip().split()[0].lower().split("@", 1)[0]
        if is_group and cmd in ("/new", "/stop", "/restart") and not self._is_allowlisted(
            sender_id, user.username
        ):
            await message.reply_text("These commands are owner-only.")
            return
        self._remember_thread_context(message)
        metadata = self._build_message_metadata(message, user)
        metadata["is_allowlisted"] = self._sender_is_allowlisted(sender_id, user.username)
        await self._handle_message(
            sender_id=sender_id,
            chat_id=str(message.chat_id),
            content=message.text or "",
            metadata=metadata,
            session_key=self._derive_topic_session_key(message),
        )

    async def _on_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle incoming messages (text, photos, voice, documents)."""
        message = update.effective_message
        if not message or not update.effective_user:
            return
        user = update.effective_user
        if getattr(user, "is_bot", False) and not self.config.allow_bot_messages:
            logger.debug("Telegram: ignoring bot-to-bot message from {}", user.id)
            return
        is_guest = update.guest_message is not None
        chat_id = str(message.chat_id)
        sender_id = self._sender_id(user)
        is_group = message.chat.type in ("group", "supergroup")
        has_business = bool(getattr(message, "business_connection_id", None))
        # Guest Mode always requires allowFrom. Private bot DMs: allowFrom only.
        # Groups need openGroups; Chat Automation peers need businessEnabled.
        if not self._ingress_allowed(
            is_group=is_group,
            has_business=has_business,
            sender_id=sender_id,
            username=user.username,
            is_guest=is_guest,
        ):
            logger.debug(
                "Telegram: ignoring {} from unauthorised sender {}",
                "guest message" if is_guest else ("DM" if not is_group and not has_business else "message"),
                sender_id,
            )
            return
        self._remember_thread_context(message)
        self._chat_ids[sender_id] = chat_id
        if len(self._chat_ids) > self._CHAT_IDS_CAP:
            oldest = next(iter(self._chat_ids))
            del self._chat_ids[oldest]
        content_parts = []
        media_paths = []
        if message.text:
            content_parts.append(message.text)
        if message.caption:
            content_parts.append(message.caption)
        current_media_paths, current_media_parts = await self._download_message_media(
            message, add_failure_content=True
        )
        media_paths.extend(current_media_paths)
        content_parts.extend(current_media_parts)
        if current_media_paths:
            logger.debug("Downloaded message media to {}", current_media_paths[0])
        reply = getattr(message, "reply_to_message", None)
        if reply is not None:
            reply_ctx = self._extract_reply_context(message)
            reply_media, reply_media_parts = await self._download_message_media(reply)
            if reply_media:
                media_paths = reply_media + media_paths
                logger.debug("Attached replied-to media: {}", reply_media[0])
            tag = reply_ctx or (
                f"[Reply to: {reply_media_parts[0]}]" if reply_media_parts else None
            )
            if tag:
                content_parts.insert(0, tag)
        content = "\n".join(content_parts) if content_parts else "[empty message]"
        str_chat_id = str(chat_id)
        sender_name = user.first_name or user.username or sender_id
        if is_group and not is_guest:
            content = f"{sender_name}: {content}"
        metadata = self._build_message_metadata(message, user, guest=is_guest)
        metadata["is_allowlisted"] = self._sender_is_allowlisted(sender_id, user.username)
        if is_guest:
            session_key = f"telegram:guest:{metadata.get('guest_query_id') or chat_id}"
        else:
            session_key = self._derive_topic_session_key(message)
        should_respond = True if is_guest else await self._is_group_message_for_bot(message)
        if is_group and not should_respond and not is_guest:
            metadata["no_reply"] = True
        # Secretary mode: archive Chat Automation traffic; do not auto-answer peers.
        if metadata.get("business_connection_id") and not getattr(
            self.config, "business_auto_reply", False
        ):
            # Owner↔bot DM also arrives as a normal Message update. Drop the
            # Chat Automation echo — demoting it caused duplicate agent turns.
            if self._bot_user_id is not None and int(chat_id) == int(self._bot_user_id):
                logger.info(
                    "Telegram: drop business echo of owner↔bot chat {}",
                    chat_id,
                )
                return
            metadata["no_reply"] = True
            if not await self._message_has_bot_mention(message) and await self._is_secretary_summon(
                message
            ):
                metadata.pop("no_reply")
                metadata["secretary_summon"] = True
                logger.info(
                    "Telegram secretary summon from {} chat={}: {}...",
                    sender_id,
                    chat_id,
                    content[:50],
                )
            else:
                logger.info(
                    "Telegram business archive from {} chat={}: {}...",
                    sender_id,
                    chat_id,
                    content[:50],
                )
        if metadata.get("no_reply") and self.config.history_max_age_hours > 0:
            date = getattr(message, "date", None)
            if date is not None:
                date = date.replace(tzinfo=timezone.utc) if date.tzinfo is None else date
                age_hours = (
                    datetime.now(timezone.utc) - date.astimezone(timezone.utc)
                ).total_seconds() / 3600
                if age_hours > self.config.history_max_age_hours:
                    logger.debug(
                        "Telegram: skipping stale no_reply message ({:.1f}h)",
                        age_hours,
                    )
                    return
        # User edited their message: if we already replied, edit that reply in place.
        if not metadata.get("no_reply") and getattr(message, "edit_date", None) is not None:
            prior = self._lookup_inbound_reply(int(message.chat_id), getattr(message, "message_id", None))
            if prior is not None:
                metadata["edit_message_id"] = prior
                logger.info(
                    "Telegram: edit prior reply {} for inbound {} chat={}",
                    prior,
                    message.message_id,
                    chat_id,
                )
        logger.debug(
            "Telegram message from {} guest={}: {}...",
            sender_id,
            is_guest,
            content[:50],
        )
        if media_group_id := getattr(message, "media_group_id", None):
            key = f"{str_chat_id}:{media_group_id}"
            if key not in self._media_group_buffers:
                if len(self._media_group_buffers) > 500:
                    logger.warning("Telegram media group buffer full, ignoring new group")
                    return
                self._media_group_buffers[key] = {
                    "sender_id": sender_id,
                    "chat_id": str_chat_id,
                    "contents": [],
                    "media": [],
                    "metadata": metadata,
                    "session_key": session_key,
                }
                if not metadata.get("no_reply") and not metadata.get("secretary_summon"):
                    self._start_typing(str_chat_id)
            buf = self._media_group_buffers[key]
            if content and content != "[empty message]":
                buf["contents"].append(content)
            buf["media"].extend(media_paths)
            if key not in self._media_group_tasks:
                self._media_group_tasks[key] = asyncio.create_task(self._flush_media_group(key))
            return
        if not metadata.get("no_reply") and not is_guest and not metadata.get("secretary_summon"):
            self._start_typing(str_chat_id)
        await self._handle_message(
            sender_id=sender_id,
            chat_id=str_chat_id,
            content=content,
            media=media_paths,
            metadata=metadata,
            session_key=session_key,
        )

    async def _flush_media_group(self, key: str) -> None:
        """Wait briefly, then forward buffered media-group as one turn."""
        try:
            await asyncio.sleep(0.6)
            if not (buf := self._media_group_buffers.pop(key, None)):
                return
            content = "\n".join(buf["contents"]) or "[empty message]"
            await self._handle_message(
                sender_id=buf["sender_id"],
                chat_id=buf["chat_id"],
                content=content,
                media=list(dict.fromkeys(buf["media"])),
                metadata=buf["metadata"],
                session_key=buf.get("session_key"),
            )
        finally:
            self._media_group_tasks.pop(key, None)

    def _start_typing(self, chat_id: str) -> None:
        """Start sending 'typing...' indicator for a chat."""
        self._stop_typing(chat_id)
        self._typing_tasks[chat_id] = asyncio.create_task(self._typing_loop(chat_id))

    def _stop_typing(self, chat_id: str) -> None:
        """Stop the typing indicator for a chat."""
        task = self._typing_tasks.pop(chat_id, None)
        if task and not task.done():
            task.cancel()

    async def _typing_loop(self, chat_id: str) -> None:
        """Repeatedly send 'typing' action until cancelled."""
        try:
            numeric_id = int(chat_id)
        except (ValueError, TypeError):
            return
        try:
            for _ in range(60):
                if not self._app:
                    break
                await self._app.bot.send_chat_action(chat_id=numeric_id, action="typing")
                await asyncio.sleep(4)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.debug("Typing indicator stopped for {}: {}", chat_id, e)
        finally:
            task = self._typing_tasks.get(chat_id)
            if task and task == asyncio.current_task():
                self._typing_tasks.pop(chat_id, None)

    async def _on_error(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Log polling / handler errors; auto-stop on Conflict.
        A Conflict error means another bot instance is already polling,
        so continuing would just produce an infinite error loop.
        Stop polling and keep the bot available for outbound sending only.
        """
        from telegram.error import Conflict

        if isinstance(context.error, Conflict):
            logger.warning(
                "Telegram Conflict detected (another instance is polling). "
                "Stopping inbound polling — this instance will remain available for sending only."
            )
            self._running = False
            if self._app and self._app.updater and self._app.updater.running:
                try:
                    await self._app.updater.stop()
                except Exception as e:
                    logger.debug("Error stopping updater after Conflict: {}", e)
            return
        logger.error("Telegram error: {}", context.error)

    def _get_extension(
        self,
        media_type: str,
        mime_type: str | None,
        filename: str | None = None,
    ) -> str:
        """Get file extension based on media type or original filename."""
        if mime_type:
            ext_map = {
                "image/jpeg": ".jpg",
                "image/png": ".png",
                "image/gif": ".gif",
                "audio/ogg": ".ogg",
                "audio/mpeg": ".mp3",
                "audio/mp4": ".m4a",
                "video/mp4": ".mp4",
                "video/webm": ".webm",
            }
            if mime_type in ext_map:
                return ext_map[mime_type]
        type_map = {
            "image": ".jpg",
            "voice": ".ogg",
            "audio": ".mp3",
            "video": ".mp4",
            "animation": ".mp4",
            "file": "",
        }
        if ext := type_map.get(media_type, ""):
            return ext
        if filename:
            from pathlib import Path

            return "".join(Path(filename).suffixes)
        return ""
