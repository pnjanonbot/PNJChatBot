import logging
import asyncio
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from .. import database as db
from .. import config
from ..utils import format_profile_for_admin

logger = logging.getLogger(__name__)

async def admin_unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != config.ADMIN_CHAT_ID:
        return
    try:
        target_user_id = int(context.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /admin_unban <user_id>")
        return

    await db.set_report_count(target_user_id, 0)
    await update.message.reply_text(f"User {target_user_id} telah di-unban (report count di-set ke 0).")

    try:
        await context.bot.send_message(chat_id=target_user_id, text="Kabar baik! Akun Anda telah di-unban oleh admin.")
    except Exception as e:
        logger.warning(f"Gagal notif unban ke {target_user_id}: {e}")

async def admin_ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != config.ADMIN_CHAT_ID:
        return
    try:
        target_user_id = int(context.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /admin_ban <user_id>")
        return

    user = await db.get_user(target_user_id)
    if not user:
        await update.message.reply_text(f"User {target_user_id} tidak ditemukan.")
        return
    await db.set_report_count(target_user_id, config.BAN_THRESHOLD)

    if user['status'] == 'chatting':
        partner_id = user['partner_id']
        await db.update_user_status(target_user_id, 'idle')
        if partner_id:
            await db.update_user_status(partner_id, 'idle')
            try:
                await context.bot.send_message(chat_id=partner_id, text="Partner Anda telah di-ban oleh admin. Sesi diakhiri.")
            except Exception as e:
                logger.warning(f"Gagal notif ban ke partner {partner_id}: {e}")
    await update.message.reply_text(f"User {target_user_id} telah di-ban (report count di-set ke {config.BAN_THRESHOLD}).")

    try:
        await context.bot.send_message(chat_id=target_user_id, text="Akun Anda telah ditangguhkan oleh admin. Jika Anda merasa ini adalah kesalahan atau ingin mengajukan banding, silakan hubungi @helperpnjbot.")
    except Exception as e:
        logger.warning(f"Gagal notif ban ke {target_user_id}: {e}")

async def admin_check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != config.ADMIN_CHAT_ID:
        return
    try:
        target_user_id = int(context.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /admin_check <user_id>")
        return

    user_data = await db.get_user(target_user_id)
    if not user_data:
        await update.message.reply_text(f"User {target_user_id} tidak ditemukan di database.")
        return

    profile_text = format_profile_for_admin(user_data)
    await update.message.reply_text(f"Detail untuk User ID {target_user_id}:\n\n{profile_text}")

async def admin_broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != config.ADMIN_CHAT_ID:
        return

    message_text = " ".join(context.args)
    if not message_text and update.message.reply_to_message:
        message_text = update.message.reply_to_message.text
    if not message_text:
        await update.message.reply_text("Usage: /admin_broadcast <pesan> atau balas pesan yang ingin di-broadcast.")
        return

    user_ids = await db.get_active_user_ids()
    if not user_ids:
        await update.message.reply_text("Tidak ada user aktif untuk dikirimi pesan.")
        return

    await update.message.reply_text(f"Memulai broadcast ke {len(user_ids)} user AKTIF...")

    success_count = 0
    fail_count = 0
    blocked_count = 0

    for user_id in user_ids:
        try:
            sent_message = await context.bot.send_message(chat_id=user_id, text=message_text)
            try:
                await context.bot.pin_chat_message(chat_id=user_id, message_id=sent_message.message_id)
            except:
                pass 
            success_count += 1
            
            await asyncio.sleep(0.05) 

        except Forbidden:
            await db.set_user_inactive(user_id)
            blocked_count += 1
            fail_count += 1
        except Exception as e:
            logger.warning(f"Gagal broadcast ke {user_id}: {e}")
            fail_count += 1

    await update.message.reply_text(
        f"Broadcast selesai.\n"
        f"✅ Berhasil: {success_count}\n"
        f"❌ Gagal: {fail_count}\n"
        f"🚫 User Inaktif (Auto-marked): {blocked_count}"
    )

async def admin_broadcast_dummy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != config.ADMIN_CHAT_ID:
        return
    message_text = " ".join(context.args)

    if not message_text and update.message.reply_to_message:
        message_text = update.message.reply_to_message.text
    if not message_text:
        await update.message.reply_text("Usage: /admin_broadcast_dummy <pesan yang akan dikirim> atau balas pesan.")
        return
    dummy_id = config.DUMMY_USER_ID
    if not dummy_id:
        await update.message.reply_text("DUMMY_USER_ID tidak terdefinisi di config.")
        return

    try:
        dummy_id_int = int(dummy_id)
    except ValueError:
        await update.message.reply_text("DUMMY_USER_ID di config tidak valid.")
        return
    await update.message.reply_text(f"Memulai broadcast ke DUMMY user: {dummy_id}...")
    try:
        sent_message = await context.bot.send_message(chat_id=dummy_id_int, text=message_text)
        await context.bot.pin_chat_message(chat_id=dummy_id_int, message_id=sent_message.message_id)
        await update.message.reply_text(f"Broadcast berhasil dikirim dan di-pin ke DUMMY user {dummy_id}.")
        logger.info(f"Broadcast ke DUMMY user {dummy_id} berhasil.")
    except Exception as e:
        logger.warning(f"Gagal kirim atau pin broadcast ke DUMMY user {dummy_id}: {e}")
        await update.message.reply_text(f"Gagal kirim broadcast ke DUMMY user {dummy_id}: {e}")

async def admin_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != config.ADMIN_CHAT_ID:
        return
    await update.message.reply_text("Mengambil daftar user... Ini mungkin butuh waktu.")

    all_users = await db.get_all_users_details()

    if not all_users:
        await update.message.reply_text("Tidak ada user terdaftar di database.")
        return
    user_list_parts = []
    current_part = "<b>Daftar User Terdaftar:</b>\n\n"

    for user in all_users:
        user_info = (
            f"ID: <code>{user.get('user_id')}</code>\n"
            f"Nama: {user.get('nama', 'N/A')}\n"
            f"Email: {user.get('email', 'N/A')}\n"
            f"Status: {user.get('status', 'N/A')}\n"
            f"Reports: {user.get('report_count', 0)}\n"
            f"----------------------------------\n"
        )

        if len(current_part) + len(user_info) > 4000:
            user_list_parts.append(current_part)
            current_part = ""
        current_part += user_info

    if current_part:
        user_list_parts.append(current_part)
    for part in user_list_parts:
        try:
            await update.message.reply_text(part, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.error(f"Gagal mengirim bagian daftar user: {e}")
            await update.message.reply_text("Gagal mengirim daftar user karena masalah format atau ukuran.")