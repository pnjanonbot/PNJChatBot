import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, ConversationHandler

from .. import database as db
from .. import config
from .. import text as txt
from ..utils import check_is_banned, is_profile_complete, format_my_profile

logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if await check_is_banned(user_id, update):
        return
    await db.create_user(user_id)
    
    if not await db.check_profile_complete(user_id):
        domains_str = ', '.join(config.VALID_EMAIL_DOMAINS)
        await update.message.reply_text(txt.START_REGISTER_MESSAGE.format(domains=domains_str))
        return config.ASK_EMAIL
    else:
        keyboard = [
            [InlineKeyboardButton("Cari Partner", callback_data="main_search")],
            [InlineKeyboardButton("Profil Saya", callback_data="main_profile")],
            [InlineKeyboardButton("Edit Profil", callback_data="main_edit")],
            [InlineKeyboardButton("Bantuan", callback_data="main_help")],
        ]
        await update.message.reply_text(txt.START_MESSAGE, reply_markup=InlineKeyboardMarkup(keyboard))
        return ConversationHandler.END

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    message_text = txt.HELP_USER
    
    if str(user_id) == config.ADMIN_CHAT_ID:
        message_text += txt.HELP_ADMIN
        
    await update.message.reply_text(message_text, parse_mode=ParseMode.HTML)

async def feedback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    search_again_keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Cari Partner Lagi", callback_data="main_search")]]
    )
    data = query.data.split('_')
    action = data[1]
    if action == "like":
        try:
            partner_id = int(data[2])
            await db.increment_like_count(partner_id)
            await query.edit_message_text(
                "Terima kasih atas feedback-nya!",
                reply_markup=search_again_keyboard
            )
        except (ValueError, IndexError):
            await query.edit_message_text("Error: Gagal memproses feedback.")
    elif action == "report":
        try:
            partner_id = int(data[2])
            keyboard = [
                [
                    InlineKeyboardButton("Ya, Laporkan", callback_data=f"report_yes_{partner_id}"),
                    InlineKeyboardButton("Batal", callback_data="report_no")
                ]
            ]
            await query.edit_message_text(
                "Apakah Anda yakin ingin melaporkan partner chat Anda?\n\n"
                "Ini akan mengirim laporan ke admin.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except (ValueError, IndexError):
            await query.edit_message_text("Error: Gagal memproses laporan.")

async def myprofile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if await check_is_banned(user_id, update):
        return
    if not await is_profile_complete(user_id, update):
        return
    user_data = await db.get_user(user_id)
    if not user_data:
        await update.message.reply_text("Terjadi kesalahan saat mengambil profil Anda.")
        return
    profile_text = format_my_profile(user_data)
    await update.message.reply_text(profile_text + "\n\nGunakan /editprofile untuk mengubah data Anda.", parse_mode=ParseMode.HTML)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = await db.get_stats()
    chatting_users = stats['chatting']
    if chatting_users % 2 != 0:
        logger.warning(f"Statistik aneh: jumlah user chatting ganjil ({chatting_users})")
    
    stats_text = txt.STATS_TEMPLATE.format(
        total=stats['total'],
        chatting=chatting_users,
        pairs=chatting_users // 2,
        waiting=stats['waiting']
    )
    
    await update.message.reply_text(stats_text, parse_mode=ParseMode.HTML)