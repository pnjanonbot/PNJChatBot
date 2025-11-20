import logging
import asyncio
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction, ParseMode
from telegram.error import Forbidden, BadRequest
from telegram.ext import ContextTypes, ConversationHandler

from .. import database as db
from .. import config
from ..utils import format_profile_for_admin, is_spamming

logger = logging.getLogger(__name__)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message = update.message

    if is_spamming(user_id, limit=1.0):
        return 

    user = await db.get_user(user_id)
    if user and user['report_count'] >= config.BAN_THRESHOLD:
        return
    if not user:
        await message.reply_text("Silakan tekan /start terlebih dahulu.")
        return
    if user['status'] == "chatting":
        await db.increment_user_stats(user_id, message_count=1)
        partner_id = user['partner_id']
        if not partner_id:
            await message.reply_text("Error: Terhubung tanpa pasangan. Mengakhiri sesi.")
            await db.update_user_status(user_id, 'idle')
            return

        if message.text:
            text_lower = message.text.lower()
            if any(bad_word in text_lower for bad_word in config.BAD_WORDS):
                await message.reply_text("⚠️ Pesan tidak terkirim. Harap jaga kesopanan (Bad Word Detected).")
                return

        try:
            await context.bot.send_chat_action(chat_id=partner_id, action=ChatAction.TYPING)
            await asyncio.sleep(random.uniform(0.5, 1.5))

            if message.text:
                await context.bot.send_message(chat_id=partner_id, text=message.text)

            elif message.photo or message.video or message.animation:
                partner_data = await db.get_user(partner_id)
                if partner_data and partner_data.get('auto_accept_media', False):
                    try:
                        file_id = None
                        caption = message.caption

                        if message.photo:
                            file_id = message.photo[-1].file_id
                            await context.bot.send_chat_action(chat_id=partner_id, action=ChatAction.UPLOAD_PHOTO)
                            await context.bot.send_photo(chat_id=partner_id, photo=file_id, caption=caption)
                        elif message.video:
                            file_id = message.video.file_id
                            await context.bot.send_chat_action(chat_id=partner_id, action=ChatAction.UPLOAD_VIDEO)
                            await context.bot.send_video(chat_id=partner_id, video=file_id, caption=caption)
                        elif message.animation:
                            file_id = message.animation.file_id
                            await context.bot.send_chat_action(chat_id=partner_id, action=ChatAction.UPLOAD_DOCUMENT)
                            await context.bot.send_animation(chat_id=partner_id, animation=file_id, caption=caption)

                        await message.reply_text("Media Anda telah otomatis diterima oleh partner.")
                        return
                    except Forbidden:
                        raise 
                    except Exception as e:
                        logger.warning(f"Gagal kirim auto-accept media ke {partner_id}: {e}")

                file_id = None
                file_type = None
                media_name = None
                if message.photo:
                    file_id = message.photo[-1].file_id
                    file_type = 'photo'
                    media_name = 'foto'
                elif message.video:
                    file_id = message.video.file_id
                    file_type = 'video'
                    media_name = 'video'
                elif message.animation:
                    file_id = message.animation.file_id
                    file_type = 'animation'
                    media_name = 'animasi (GIF)'

                pending_id = await db.create_pending_media(
                    sender_id=user_id,
                    receiver_id=partner_id,
                    file_id=file_id,
                    file_type=file_type,
                    caption=message.caption
                )
                if not pending_id:
                    await message.reply_text("Gagal mengirim media, coba lagi nanti.")
                    return

                keyboard = [
                    [
                        InlineKeyboardButton("Ya, Tampilkan", callback_data=f"media_accept_{pending_id}"),
                        InlineKeyboardButton("Tidak", callback_data=f"media_decline_{pending_id}")
                    ]
                ]

                await context.bot.send_message(
                    chat_id=partner_id,
                    text=f"Partner Anda mengirim sebuah {media_name}. Apakah Anda ingin menerimanya?",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )

                await message.reply_text("Media Anda telah dikirim, menunggu persetujuan partner...")

            elif message.sticker:
                await context.bot.send_message(chat_id=partner_id, text="[Partner mengirim stiker]")
            elif message.voice:
                await context.bot.send_chat_action(chat_id=partner_id, action=ChatAction.UPLOAD_VOICE)
                await context.bot.send_voice(chat_id=partner_id, voice=message.voice.file_id, caption=message.caption)
            elif message.document:
                await context.bot.send_message(chat_id=partner_id, text="[Partner mengirim file]")
        
        except Forbidden:
            logger.info(f"Partner {partner_id} memblokir bot.")
            await db.set_user_inactive(partner_id)
            await db.update_user_status(user_id, 'idle')
            await db.update_user_status(partner_id, 'idle')
            await message.reply_text("Partner Anda telah memblokir bot. Obrolan diakhiri.")
            return
        except Exception as e:
            logger.error(f"Gagal mengirim pesan ke {partner_id} dari {user_id}: {e}")
            await message.reply_text("Gagal mengirim pesan. Mungkin pasangan Anda memblokir bot.")

    elif user['status'] == "idle" or user['status'] == 'unregistered':
        if not await db.check_profile_complete(user_id):
            await message.reply_text("Anda belum terdaftar. Silakan gunakan /register.")
        else:
            await message.reply_text("Anda tidak sedang dalam obrolan. Gunakan /search untuk memulai.")

async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = await db.get_user(user_id)
    context.user_data.pop('report_context_message', None)
    if not user or user['status'] != 'chatting':
        await update.message.reply_text("Perintah /report hanya bisa digunakan saat Anda sedang dalam obrolan.")
        return
    if update.message.reply_to_message:
        context.user_data['report_context_message'] = update.message.reply_to_message.text
    partner_id = user['partner_id']
    keyboard = [
        [
            InlineKeyboardButton("Ya, Laporkan User Ini", callback_data=f"report_yes_{partner_id}"),
            InlineKeyboardButton("Batal", callback_data="report_no")
        ]
    ]
    await update.message.reply_text(
        "Apakah Anda yakin ingin melaporkan partner chat Anda?\n\n"
        "Ini akan segera mengakhiri obrolan dan mengirim laporan ke admin.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def cancel_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.pop('report_context_message', None)
    await query.edit_message_text("Laporan dibatalkan. Anda masih dalam obrolan.")

async def confirm_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        reported_user_id = int(query.data.split('_')[-1])
        context.user_data['reported_user_id'] = reported_user_id
    except (ValueError, IndexError):
        await query.edit_message_text("Error: Gagal memproses ID laporan.")
        return ConversationHandler.END

    keyboard = []
    for i, reason in enumerate(config.REPORT_REASONS):
        keyboard.append([InlineKeyboardButton(reason, callback_data=f"report_reason_{i}")])

    await query.edit_message_text(
        "Silakan pilih alasan laporan Anda:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    return config.REPORT_REASON_SELECT

async def _process_report(query_or_update: Update, context: ContextTypes.DEFAULT_TYPE, reason: str, reported_user_id: int, reporter_user_id: int, detail_text: str = None):
    search_again_keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Cari Partner Lagi", callback_data="main_search")]]
    )

    await db.update_user_status(reporter_user_id, 'idle')
    await db.update_user_status(reported_user_id, 'idle')
    await db.increment_report_count(reported_user_id)
    user_confirm_text = (
        f"Laporan Anda untuk alasan '{reason}' telah dikirim. Obrolan diakhiri.\n\n"
        "<b>Penting:</b> Jika laporan Anda bersifat mendesak atau berbahaya (misalnya ancaman), "
        "mohon hubungi admin secara langsung di <b>@helperpnjbot</b> untuk penanganan segera."
    )
    if isinstance(query_or_update, Update) and query_or_update.callback_query:
        await query_or_update.callback_query.edit_message_text(
            user_confirm_text,
            parse_mode=ParseMode.HTML,
            reply_markup=search_again_keyboard
        )
    else:
        await query_or_update.message.reply_text(
            user_confirm_text,
            parse_mode=ParseMode.HTML,
            reply_markup=search_again_keyboard
        )

    try:
        await context.bot.send_message(
            chat_id=reported_user_id,
            text="Partner Anda telah melaporkan obrolan ini. Sesi diakhiri."
        )
    except Exception as e:
        logger.warning(f"Gagal notif laporan ke user {reported_user_id}: {e}")

    reporter_data = await db.get_user(reporter_user_id)
    reported_data = await db.get_user(reported_user_id)

    new_report_count = reported_data.get('report_count', 0)

    if new_report_count < config.BAN_THRESHOLD:
        try:
            await context.bot.send_message(
                chat_id=reported_user_id,
                text=f"<b>PERINGATAN RESMI</b>\n\n"
                     f"Anda telah menerima laporan dari pengguna lain (Total laporan saat ini: {new_report_count}). "
                     f"Harap jaga etika dan kenyamanan berkomunikasi.\n\n"
                     f"Jika Anda mencapai {config.BAN_THRESHOLD} laporan, akun Anda akan ditangguhkan secara otomatis.",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.warning(f"Gagal kirim peringatan report ke user {reported_user_id}: {e}")

    report_context_message = context.user_data.pop('report_context_message', None)
    context_text = ""
    if report_context_message:
        context_text = f"\n<b>Konteks Pesan (di-reply saat /report):</b>\n<i>\"{report_context_message}\"</i>\n"

    detail_str = f"\n<b>Detail (dari 'Lainnya'):</b>\n<i>{detail_text}</i>\n" if detail_text else ""
    admin_message = (
        f"<b>‼️ LAPORAN BARU ‼️</b>\n\n"
        f"<b>Alasan:</b> {reason}\n{detail_str}{context_text}\n"
        f"<b>PELAPOR (REPORTER):</b>\n{format_profile_for_admin(reporter_data)}\n\n"
        f"<b>TERLAPOR (REPORTED):</b>\n{format_profile_for_admin(reported_data)}\n\n"
        f"Tindakan: Obrolan dihentikan, report_count +1 untuk terlapor."
    )

    try:
        await context.bot.send_message(chat_id=config.ADMIN_CHAT_ID, text=admin_message, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Gagal mengirim notifikasi admin: {e}")

    if reported_data and new_report_count >= config.BAN_THRESHOLD:
        await context.bot.send_message(
            chat_id=config.ADMIN_CHAT_ID,
            text=f"<b>🚫 AUTO-BAN 🚫</b>\nUser {reported_user_id} ({reported_data.get('nama')}) telah mencapai {config.BAN_THRESHOLD} laporan dan ditangguhkan.",
            parse_mode=ParseMode.HTML
        )
        await context.bot.send_message(
            chat_id=reported_user_id,
            text="Akun Anda telah ditangguhkan secara otomatis karena telah menerima beberapa laporan. Jika Anda merasa ini adalah kesalahan atau ingin mengajukan banding, silakan hubungi @helperpnjbot."
        )

async def report_reason_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        reported_user_id = context.user_data['reported_user_id']
        reason_index = int(query.data.split('_')[-1])
        reason = config.REPORT_REASONS[reason_index]
        reporter_user_id = query.from_user.id
    except (ValueError, IndexError, KeyError):
        await query.edit_message_text("Error: Gagal memproses alasan laporan. Sesi dibatalkan.")
        context.user_data.clear()
        return ConversationHandler.END

    if reason == "Lainnya":
        context.user_data['report_reason'] = reason
        await query.edit_message_text(
            "Anda memilih 'Lainnya'. Mohon jelaskan detail laporan Anda dalam satu pesan singkat.\n\nKetik /cancel untuk membatalkan laporan."
        )
        return config.REPORT_OTHER_DETAIL
    else:
        await query.edit_message_text("Memproses laporan Anda...")
        await _process_report(update, context, reason, reported_user_id, reporter_user_id)
        context.user_data.clear()
        return ConversationHandler.END

async def report_other_detail_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    detail_text = update.message.text
    reporter_user_id = update.effective_user.id

    try:
        reported_user_id = context.user_data['reported_user_id']
        reason = context.user_data.get('report_reason', 'Lainnya')
    except KeyError:
        await update.message.reply_text("Error: Sesi laporan Anda telah berakhir. Silakan coba lagi.")
        context.user_data.clear()
        return ConversationHandler.END

    await update.message.reply_text("Memproses laporan Anda...")

    await _process_report(update, context, reason, reported_user_id, reporter_user_id, detail_text=detail_text)

    context.user_data.clear()
    return ConversationHandler.END

async def cancel_report_conv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Proses laporan dibatalkan. Anda masih dalam obrolan (jika belum dihentikan).")
    context.user_data.pop('reported_user_id', None)
    context.user_data.pop('report_reason', None)
    context.user_data.pop('report_context_message', None)
    return ConversationHandler.END

async def handle_media_accept(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        media_id = int(query.data.split('_')[-1])
    except (ValueError, IndexError):
        await query.edit_message_text("Error: Gagal memproses media.")
        return

    media_data = await db.get_pending_media(media_id)
    if not media_data:
        await query.edit_message_text("Media ini sudah tidak valid atau kedaluwarsa.")
        return
    if query.from_user.id != media_data['receiver_id']:
        await query.answer("Ini bukan untuk Anda.", show_alert=True)
        return

    await query.delete_message()
    file_id = media_data['file_id']
    caption = media_data['caption']
    receiver_id = media_data['receiver_id']
    try:
        if media_data['file_type'] == 'photo':
            await context.bot.send_chat_action(chat_id=receiver_id, action=ChatAction.UPLOAD_PHOTO)
            await context.bot.send_photo(chat_id=receiver_id, photo=file_id, caption=caption)
        elif media_data['file_type'] == 'video':
            await context.bot.send_chat_action(chat_id=receiver_id, action=ChatAction.UPLOAD_VIDEO)
            await context.bot.send_video(chat_id=receiver_id, video=file_id, caption=caption)
        elif media_data['file_type'] == 'animation':
            await context.bot.send_chat_action(chat_id=receiver_id, action=ChatAction.UPLOAD_DOCUMENT)
            await context.bot.send_animation(chat_id=receiver_id, animation=file_id, caption=caption)

        await context.bot.send_message(chat_id=media_data['sender_id'], text="Partner Anda menerima media Anda.")

    except Exception as e:
        logger.error(f"Gagal mengirim media {media_id} yang disetujui: {e}")
        await context.bot.send_message(chat_id=receiver_id, text="Gagal memuat media.")

    await db.delete_pending_media(media_id)

async def handle_media_decline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        media_id = int(query.data.split('_')[-1])
    except (ValueError, IndexError):
        await query.edit_message_text("Error: Gagal memproses media.")
        return

    media_data = await db.get_pending_media(media_id)
    if not media_data:
        await query.edit_message_text("Media ini sudah tidak valid atau kedaluwarsa.")
        return
    if query.from_user.id != media_data['receiver_id']:
        await query.answer("Ini bukan untuk Anda.", show_alert=True)
        return

    await db.delete_pending_media(media_id)

    await query.edit_message_text("Media ditolak.")

    try:
        await context.bot.send_message(
            chat_id=media_data['sender_id'],
            text="Partner Anda menolak untuk menerima media yang Anda kirim."
        )
    except Exception as e:
        logger.warning(f"Gagal notif media ditolak ke sender {media_data['sender_id']}: {e}")