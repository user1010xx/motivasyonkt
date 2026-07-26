from __future__ import annotations

import logging
import sys
from datetime import time as dt_time
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.constants import ChatAction, ChatType, ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from bot.config import Settings, load_settings
from bot.dates import DateParseError, parse_day_arg
from bot.gonder_args import parse_gonder_args
from bot.models import Period
from bot.service import MotivationService
from bot.toniva_client import TonivaClient

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("motivasyon")


def _parse_hhmm(value: str) -> dt_time:
    hour, minute = value.strip().split(":")
    return dt_time(hour=int(hour), minute=int(minute))


def _is_admin(settings: Settings, user_id: int | None) -> bool:
    """Sadece TELEGRAM_ADMIN_IDS listesindeki kullanıcılar yetkili."""
    if not settings.telegram_admin_ids:
        return False
    return user_id is not None and user_id in settings.telegram_admin_ids


async def _reject_if_not_admin(update: Update, settings: Settings) -> bool:
    """
    Yetkisiz kullanıcıyı engelle.
    - Özel sohbet: sessizce yok say (yanıt yok).
    - Grup: sessizce yok say (spam olmasın).
    Returns True if rejected.
    """
    user = update.effective_user
    chat = update.effective_chat
    uid = user.id if user else None
    if _is_admin(settings, uid):
        return False

    chat_type = chat.type if chat else "?"
    logger.info(
        "Yetkisiz komut yok sayıldı: user=%s chat=%s type=%s",
        uid,
        chat.id if chat else None,
        chat_type,
    )
    return True


async def _send_period(
    context: ContextTypes.DEFAULT_TYPE,
    period: Period,
    *,
    chat_id: str | int,
    reply_to: int | None = None,
    day=None,
    until_now: bool = False,
) -> None:
    from datetime import date as date_cls

    service: MotivationService = context.application.bot_data["service"]
    settings: Settings = context.application.bot_data["settings"]
    target_day: date_cls | None = day

    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_PHOTO)
    try:
        _board, caption, image = await service.build(
            period, day=target_day, until_now=until_now
        )
    except Exception as exc:
        logger.exception("Motivasyon üretilemedi: %s", exc)
        detail = str(exc).replace("<", "&lt;").replace(">", "&gt;")
        if len(detail) > 800:
            detail = detail[:797] + "…"
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"⚠️ <b>{'Canlı' if until_now else period.label}</b> mesajı üretilemedi.\n\n"
                f"{detail}\n\n"
                "<i>Toniva 403 ise: API key scope (reports:read) veya "
                "IP whitelist (Railway IP) kontrol et.</i>"
            ),
            parse_mode=ParseMode.HTML,
            reply_to_message_id=reply_to,
        )
        return

    if len(caption) > 1000:
        caption = caption[:997] + "…"

    await context.bot.send_photo(
        chat_id=chat_id,
        photo=image,
        caption=caption,
        parse_mode=ParseMode.HTML,
        reply_to_message_id=reply_to,
    )
    logger.info(
        "Gönderildi: period=%s until_now=%s chat=%s mock=%s",
        period.value,
        until_now,
        chat_id,
        settings.mock_mode,
    )


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.application.bot_data["settings"]
    if not update.effective_message:
        return
    if await _reject_if_not_admin(update, settings):
        return

    chat = update.effective_chat
    where = "özel sohbet" if chat and chat.type == ChatType.PRIVATE else "bu grup"
    await update.effective_message.reply_text(
        "Merhaba! 🎯 Toniva motivasyon botu hazır.\n\n"
        f"Komutlar ({where}):\n"
        "/gonder — canlı (bugün 00:00–şimdi) → gruba\n"
        "/gonder 26.07.2026 sabah\n"
        "/gonder 26.07.2026 oglen\n"
        "/gonder 26.07.2026 aksam\n"
        "/gonder dün aksam\n"
        "/sabah · /oglen · /aksam  (dilimler: 12:00 / 16:00 / 18:10)\n"
        "/sabah 26.07.2026 · /aksam dün\n"
        "/debug · /durum · /test\n\n"
        "• /gonder → TELEGRAM_CHAT_ID(S) gruplarına gider.\n"
        "• Akşam dilimi varsayılan: 00:00–18:10 (CUTOFF_AKSAM)."
    )


async def cmd_durum(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.application.bot_data["settings"]
    if not update.effective_message:
        return
    if await _reject_if_not_admin(update, settings):
        return

    chats = ", ".join(settings.telegram_chat_ids) or "(yok)"
    admins = ", ".join(str(i) for i in settings.telegram_admin_ids) or "(yok)"
    text = (
        "<b>Bot durumu</b>\n"
        f"• Zamanlanan grup(lar): <code>{chats}</code>\n"
        f"• Admin id(ler): <code>{admins}</code>\n"
        f"• Mock: <b>{'evet' if settings.mock_mode else 'hayır'}</b>\n"
        f"• Toniva key: <b>{'var' if settings.has_toniva else 'yok'}</b>\n"
        f"• Zamanlayıcı: <b>{'açık' if settings.enable_schedule else 'kapalı'}</b>\n"
        f"• TZ: {settings.timezone}\n"
        f"• Gönderim: {settings.schedule_sabah} / {settings.schedule_oglen} / {settings.schedule_aksam}\n"
        f"• Dilim (veri): {settings.cutoff_sabah} / {settings.cutoff_oglen} / {settings.cutoff_aksam}\n"
    )
    await update.effective_message.reply_html(text)


async def _period_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE, period: Period
) -> None:
    settings: Settings = context.application.bot_data["settings"]
    if not update.effective_message or not update.effective_chat:
        return
    if await _reject_if_not_admin(update, settings):
        return

    try:
        day = parse_day_arg(context.args, timezone=settings.timezone)
    except DateParseError as exc:
        await update.effective_message.reply_text(str(exc))
        return

    target_chat = update.effective_chat.id
    status = await update.effective_message.reply_text(
        f"⏳ {period.label} · {day.strftime('%d.%m.%Y')} hazırlanıyor…"
    )
    try:
        await _send_period(
            context,
            period,
            chat_id=target_chat,
            reply_to=update.effective_message.message_id,
            day=day,
        )
    finally:
        try:
            await status.delete()
        except Exception:
            pass


async def cmd_sabah(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _period_command(update, context, Period.SABAH)


async def cmd_oglen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _period_command(update, context, Period.OGLEN)


async def cmd_aksam(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _period_command(update, context, Period.AKSAM)


async def cmd_test(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Öğlen şablonu ile hızlı deneme."""
    await _period_command(update, context, Period.OGLEN)


async def cmd_gonder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gruba zirve gönder.

    /gonder                         → bugün 00:00–şimdi (canlı)
    /gonder 26.07.2026 sabah        → o gün 00:00–12:00
    /gonder 26.07.2026 oglen
    /gonder 26.07.2026 aksam        → o gün 00:00–18:10 (tam akşam dilimi)
    /gonder dün aksam
    """
    settings: Settings = context.application.bot_data["settings"]
    if not update.effective_message or not update.effective_chat:
        return
    if await _reject_if_not_admin(update, settings):
        return

    if not settings.telegram_chat_ids:
        await update.effective_message.reply_text(
            "TELEGRAM_CHAT_ID / TELEGRAM_CHAT_IDS tanımlı değil. "
            "Railway env'e grup id ekle."
        )
        return

    try:
        req = parse_gonder_args(context.args, timezone=settings.timezone)
    except DateParseError as exc:
        await update.effective_message.reply_text(
            f"{exc}\n\n"
            "Örnekler:\n"
            "/gonder\n"
            "/gonder 26.07.2026 sabah\n"
            "/gonder 26.07.2026 oglen\n"
            "/gonder 26.07.2026 aksam\n"
            "/gonder dün aksam"
        )
        return

    status = await update.effective_message.reply_text(
        f"⏳ Gruba hazırlanıyor…\n{req.label}"
    )

    ok, fail = 0, 0
    errors: list[str] = []

    try:
        service: MotivationService = context.application.bot_data["service"]
        board, caption, image = await service.build(
            req.period,
            day=req.day,
            until_now=req.until_now,
        )
        if len(caption) > 1000:
            caption = caption[:997] + "…"

        photo_bytes = image if isinstance(image, (bytes, bytearray)) else bytes(image)

        for chat_id in settings.telegram_chat_ids:
            try:
                cid = str(chat_id).strip()
                await context.bot.send_photo(
                    chat_id=cid,
                    photo=photo_bytes,
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                    read_timeout=120,
                    write_timeout=120,
                    connect_timeout=60,
                )
                ok += 1
            except Exception as exc:
                fail += 1
                err = str(exc)
                hint = ""
                if "timed out" in err.lower() or "timeout" in err.lower():
                    hint = " (timeout — bot grupta mı? id -100… mi?)"
                if "chat not found" in err.lower() or "forbidden" in err.lower():
                    hint = " (botu gruba ekle / id kontrol)"
                if cid.startswith("-") and not cid.startswith("-100") and len(cid) > 10:
                    hint += f" | Denenebilir: -100{cid.lstrip('-')}"
                errors.append(f"{cid}: {err}{hint}")
                logger.exception("/gonder grup fail: %s", chat_id)

        call = board.call_leader
        talk = board.talk_leader

        if ok and not fail:
            head = "✅ <b>Gruba gönderildi</b>"
        elif ok and fail:
            head = "⚠️ <b>Kısmen gönderildi</b>"
        else:
            head = "❌ <b>Gruba gönderilemedi</b> (kart üretildi)"

        summary = (
            f"{head}\n"
            f"📋 {req.label}\n"
            f"⏱ Dilim: <b>{board.window_label}</b>\n"
            f"📤 Grup: {ok} ok"
            + (f", {fail} hata" if fail else "")
            + "\n\n"
        )
        if not call and not talk:
            summary += "📭 Bu dilimde skor yok.\n\n"
        if call:
            summary += f"📞 Çağrı: <b>{call.name}</b> ({call.call_count})\n"
        if talk:
            summary += f"🎧 Süre: <b>{talk.name}</b> ({talk.talk_label})\n"
        if errors:
            summary += "\n<code>" + "\n".join(errors)[:700] + "</code>"

        if fail and update.effective_chat:
            try:
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=photo_bytes,
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                    read_timeout=120,
                    write_timeout=120,
                )
                summary += "\n\n📎 Önizleme özel sohbete iletildi."
            except Exception:
                logger.exception("/gonder private preview fail")

        await update.effective_message.reply_html(summary)
    except Exception as exc:
        logger.exception("/gonder hata: %s", exc)
        detail = str(exc).replace("<", "&lt;").replace(">", "&gt;")
        await update.effective_message.reply_html(
            f"⚠️ Gönderim üretilemedi.\n<code>{detail[:800]}</code>"
        )
    finally:
        try:
            await status.delete()
        except Exception:
            pass


async def cmd_debug(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Toniva rapor yapısını PII'siz özetle (alan eşleştirme için)."""
    settings: Settings = context.application.bot_data["settings"]
    service: MotivationService = context.application.bot_data["service"]
    if not update.effective_message:
        return
    if await _reject_if_not_admin(update, settings):
        return

    period_for_debug = Period.SABAH
    date_args = list(context.args or [])
    if date_args and date_args[0].lower() in {"sabah", "oglen", "aksam"}:
        period_for_debug = Period(date_args[0].lower())
        date_args = date_args[1:]
    try:
        day = parse_day_arg(date_args, timezone=settings.timezone)
    except DateParseError as exc:
        await update.effective_message.reply_text(str(exc))
        return

    status = await update.effective_message.reply_text(
        f"🔍 Toniva özeti · {day.strftime('%d.%m.%Y')} · {period_for_debug.window_label}…"
    )
    try:
        text = await service.toniva.debug_reports(day, period_for_debug)
        if len(text) > 3500:
            text = text[:3490] + "\n…"
        await update.effective_message.reply_text(
            f"<pre>{text}</pre>", parse_mode=ParseMode.HTML
        )
    except Exception as exc:
        await update.effective_message.reply_text(f"Debug hata: {exc}")
    finally:
        try:
            await status.delete()
        except Exception:
            pass


async def scheduled_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    period: Period = context.job.data["period"]  # type: ignore[index]
    settings: Settings = context.application.bot_data["settings"]
    logger.info("Zamanlanmış iş tetiklendi: %s", period.value)
    if not settings.telegram_chat_ids:
        logger.error("TELEGRAM_CHAT_ID(S) boş — zamanlanmış gönderim atlandı.")
        return
    for chat_id in settings.telegram_chat_ids:
        try:
            await _send_period(context, period, chat_id=chat_id)
        except Exception:
            logger.exception("Zamanlanmış gönderim başarısız: chat=%s", chat_id)


def _setup_jobs(app: Application, settings: Settings) -> None:
    if not settings.enable_schedule:
        logger.info("Zamanlayıcı kapalı (ENABLE_SCHEDULE=false).")
        return

    tz = ZoneInfo(settings.timezone)
    jq = app.job_queue
    if jq is None:
        logger.error("JobQueue yok — APScheduler/job-queue extra eksik olabilir.")
        return

    mapping = [
        (Period.SABAH, settings.schedule_sabah),
        (Period.OGLEN, settings.schedule_oglen),
        (Period.AKSAM, settings.schedule_aksam),
    ]
    for period, hhmm in mapping:
        t = _parse_hhmm(hhmm)
        jq.run_daily(
            scheduled_job,
            time=t.replace(tzinfo=tz),
            data={"period": period},
            name=f"motivasyon_{period.value}",
        )
        logger.info("Planlandı: %s @ %s (%s)", period.value, hhmm, settings.timezone)


def build_app(settings: Settings) -> Application:
    toniva = TonivaClient(
        base_url=settings.toniva_base_url,
        api_key=settings.toniva_api_key,
        mock_mode=settings.mock_mode or not settings.has_toniva,
        timezone=settings.timezone,
    )
    service = MotivationService(toniva=toniva, timezone=settings.timezone)

    app = Application.builder().token(settings.telegram_bot_token).build()
    app.bot_data["settings"] = settings
    app.bot_data["service"] = service

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_start))
    app.add_handler(CommandHandler("durum", cmd_durum))
    app.add_handler(CommandHandler("sabah", cmd_sabah))
    app.add_handler(CommandHandler("oglen", cmd_oglen))
    app.add_handler(CommandHandler("aksam", cmd_aksam))
    app.add_handler(CommandHandler("test", cmd_test))
    app.add_handler(CommandHandler("gonder", cmd_gonder))
    app.add_handler(CommandHandler("debug", cmd_debug))

    return app


def main() -> None:
    settings = load_settings()
    errors = settings.validate()
    # Mock ile denemede toniva zorunlu değil
    if settings.mock_mode or not settings.has_toniva:
        errors = [e for e in errors if "TONIVA_API_KEY" not in e]
    if errors:
        for e in errors:
            logger.error(e)
        sys.exit(1)

    if not settings.has_toniva and not settings.mock_mode:
        logger.warning("Toniva API key yok — client MOCK veri kullanacak.")

    app = build_app(settings)

    async def post_init(application: Application) -> None:
        # Polling ile webhook çakışmasın (Railway / eski webhook kalıntısı)
        await application.bot.delete_webhook(drop_pending_updates=False)
        _setup_jobs(application, settings)
        me = await application.bot.get_me()
        logger.info(
            "Bot online: @%s | admins=%s | schedule_chats=%s",
            me.username,
            settings.telegram_admin_ids,
            settings.telegram_chat_ids,
        )
        logger.info(
            "Komutlar SADECE şu user id'lere yanıt verir: %s — "
            "Id yanlışsa bot sessiz kalır (özelde de).",
            settings.telegram_admin_ids,
        )

    app.post_init = post_init

    logger.info(
        "Başlatılıyor… mock=%s schedule=%s chats=%s admins=%s",
        settings.mock_mode or not settings.has_toniva,
        settings.enable_schedule,
        settings.telegram_chat_ids,
        settings.telegram_admin_ids,
    )
    # drop_pending_updates=False: kuyruktaki /start vs. işlensin
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=False,
    )


if __name__ == "__main__":
    main()
