import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from .. import database as db
from .commands import myprofile_command, help_command
from .registration import register_start

logger = logging.getLogger(__name__)

class _MockUpdate:
    def __init__(self, query: Update.callback_query):
        self.effective_user = query.from_user
        self.message = query.message

async def main_menu_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    command = query.data
    mock_update = _MockUpdate(query)
    action_text = {
        "main_profile": "Menampilkan profil...",
        "main_help": "Menampilkan bantuan...",
        "main_register": "Memulai registrasi..."
    }.get(command, "Tindakan tidak diketahui...")

    try:
        await query.edit_message_text(text=action_text)
    except Exception:
        pass

    if command == "main_profile":
        await myprofile_command(mock_update, context)
    elif command == "main_help":
        await help_command(mock_update, context)
    elif command == "main_register":
        await register_start(mock_update, context)

async def handle_block_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    search_again_keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Cari Partner Lagi", callback_data="main_search")]]
    )
    try:
        partner_id = int(query.data.split('_')[-1])
        user_id = query.from_user.id
    except (ValueError, IndexError):
        await query.edit_message_text("Error: Gagal memproses data blokir.")
        return

    block_success = await db.block_user(user_id, partner_id)
    if block_success:
        await query.edit_message_text(
            "Pengguna ini telah diblokir. Anda tidak akan dipasangkan lagi dengannya.",
            reply_markup=search_again_keyboard
        )
        logger.info(f"User {user_id} memblokir partner {partner_id} via tombol.")
    else:
        await query.edit_message_text(
            "Gagal memblokir partner. Mungkin Anda mencoba memblokir dummy user, atau pengguna ini sudah diblokir.",
            reply_markup=search_again_keyboard
        )