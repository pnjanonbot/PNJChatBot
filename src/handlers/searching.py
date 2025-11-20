import logging
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, ConversationHandler

from .. import database as db
from .. import config
from ..utils import check_is_banned, is_profile_complete, format_profile

logger = logging.getLogger(__name__)

async def connect_users(context: ContextTypes.DEFAULT_TYPE, user_id_a: int, user_id_b: int):
    user_a_data = await db.get_user(user_id_a)
    user_b_data = await db.get_user(user_id_b)
    if not user_a_data or not user_b_data:
        logger.warning("Gagal connect_users, salah satu user tidak ditemukan.")
        return
    profile_for_a = format_profile(user_b_data)
    profile_for_b = format_profile(user_a_data)
    for user_id in [user_id_a, user_id_b]:
        jobs = context.job_queue.get_jobs_by_name(f"match_{user_id}")
        for job in jobs:
            job.schedule_removal()
            logger.info(f"Membatalkan job fallback untuk user {user_id} karena match ditemukan.")
    await db.update_user_status(user_id_a, 'chatting', user_id_b)
    await db.update_user_status(user_id_b, 'chatting', user_id_a)

    await db.add_match_history(user_id_a, user_id_b)

    await db.increment_user_stats(user_id_a, chat_count=1)
    await db.increment_user_stats(user_id_b, chat_count=1)
    logger.info(f"Memasangkan {user_id_a} dengan {user_id_b} (via matchmaking)")
    try:
        await context.bot.send_message(chat_id=user_id_a, text=profile_for_a, parse_mode=ParseMode.HTML)
        await context.bot.send_message(chat_id=user_id_a, text="Pasangan ditemukan! Selamat mengobrol.")

        await context.bot.send_message(chat_id=user_id_b, text=profile_for_b, parse_mode=ParseMode.HTML)
        await context.bot.send_message(chat_id=user_id_b, text="Pasangan ditemukan! Selamat mengobrol.")
        if config.ICEBREAKER_QUESTIONS:
            icebreaker = random.choice(config.ICEBREAKER_QUESTIONS)
            icebreaker_text = f"<b>Icebreaker:</b>\n<i>{icebreaker}</i>"
            await context.bot.send_message(chat_id=user_id_a, text=icebreaker_text, parse_mode=ParseMode.HTML)
            await context.bot.send_message(chat_id=user_id_b, text=icebreaker_text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Gagal mengirim pesan match ke {user_id_a} or {user_id_b}: {e}")

async def fallback_match_job(context: ContextTypes.DEFAULT_TYPE):
    user_id = context.job.data['user_id']
    logger.info(f"Menjalankan job fallback match untuk {user_id}...")

    user = await db.get_user(user_id)
    if not user or user['status'] != 'waiting':
        logger.info(f"Job fallback untuk {user_id} dibatalkan (user tidak lagi menunggu).")
        return
    partner = await db.find_waiting_partner(user_id, user, strict_prefs=False)

    if partner:
        await connect_users(context, user_id, partner['user_id'])
    else:
        logger.info(f"Job fallback untuk {user_id} tidak menemukan partner non-strict. Menjadwalkan ulang...")
        
        user_check_again = await db.get_user(user_id)
        if user_check_again and user_check_again['status'] == 'waiting':
            context.job_queue.run_once(
                fallback_match_job,
                20,
                data={'user_id': user_id},
                name=f"match_{user_id}"
            )
        else:
            logger.info(f"User {user_id} tidak lagi menunggu, job fallback tidak dijadwalkan ulang.")

async def schedule_match_attempt(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    my_profile_data = await db.get_user(user_id)
    if not my_profile_data:
        return
    partner = await db.find_waiting_partner(user_id, my_profile_data, strict_prefs=True)

    if partner:
        await connect_users(context, user_id, partner['user_id'])
        return
    context.job_queue.run_once(
        fallback_match_job,
        20,
        data={'user_id': user_id},
        name=f"match_{user_id}"
    )
    logger.info(f"Job fallback match dijadwalkan untuk {user_id} dalam 20 detik.")

async def search_command_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    reply_func = None
    if update.message:
        reply_func = update.message.reply_text
    elif update.callback_query:
        await update.callback_query.answer()
        reply_func = update.callback_query.edit_message_text
    else:
        return ConversationHandler.END
    if await check_is_banned(user_id, update):
        return ConversationHandler.END

    mock_update = update if update.message else type('MockUpdate', (object,), {'message': update.callback_query.message})
    if not await is_profile_complete(user_id, mock_update):
        return ConversationHandler.END
    user = await db.get_user(user_id)
    if user['status'] == "chatting":
        await reply_func("Anda sudah dalam obrolan. Gunakan /stop untuk mengakhiri.")
        return ConversationHandler.END
    if user['status'] == "waiting":
        await reply_func("Anda sudah dalam antrian. Mohon tunggu atau /stop untuk batal.")
        return ConversationHandler.END

    logger.info(f"User {user_id} memulai filter pencarian.")
    keyboard = [
        [InlineKeyboardButton("Cari Lawan Jenis 💞", callback_data="search_lawan_jenis")],
        [InlineKeyboardButton("Quick Match (Apa Saja) ⚡", callback_data="search_apa_saja")]
    ]
    await reply_func(
        "<b>Filter Pencarian:</b> Anda ingin mencari partner...",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )
    return config.SEARCH_PREF_GENDER

async def handle_search_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    choice = query.data
    
    pref_gender = "apa_saja"

    if choice == "search_lawan_jenis":
        user_data = await db.get_user(user_id)
        my_gender = user_data.get('gender')
        
        if my_gender == 'cowo':
            pref_gender = 'cewe'
        elif my_gender == 'cewe':
            pref_gender = 'cowo'
        else:
            pref_gender = 'apa_saja'
            await query.message.reply_text("Gender Anda belum diatur dengan benar. Menggunakan Quick Match (Apa Saja).")

    await query.edit_message_text(
        "Preferensi disimpan... Mencari pasangan...\n\n"
        "Anda akan diprioritaskan sesuai preferensi selama 20 detik. "
        "Setelah itu, Anda akan dicarikan partner mana saja yang tersedia.\n\n"
        "Tekan /stop untuk membatalkan."
    )

    try:
        await db.update_user_profile(user_id, 'pref_gender', pref_gender)
    except Exception as e:
        logger.error(f"Gagal simpan preferensi user {user_id}: {e}")
        await query.edit_message_text("Gagal menyimpan preferensi. Coba lagi /search.")
        return ConversationHandler.END

    await db.update_user_status(user_id, 'waiting')

    await schedule_match_attempt(context, user_id)

    return ConversationHandler.END

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = await db.get_user(user_id)
    if not user or user['status'] == "idle":
        await update.message.reply_text("Anda tidak sedang dalam obrolan atau pencarian.")
        return ConversationHandler.END
    if user['status'] == "waiting":
        await db.update_user_status(user_id, 'idle')
        logger.info(f"User {user_id} membatalkan pencarian.")

        job_name = f"match_{user_id}"
        jobs = context.job_queue.get_jobs_by_name(job_name)
        for job in jobs:
            job.schedule_removal()
        logger.info(f"Job fallback untuk {user_id} dibatalkan karena /stop.")
        await update.message.reply_text("Pencarian dibatalkan.")
        return ConversationHandler.END
    if user['status'] == "chatting":
        partner_id = user['partner_id']
        logger.info(f"User {user_id} mengakhiri obrolan dengan {partner_id}.")
        await db.update_user_status(user_id, 'idle')
        if partner_id:
            await db.update_user_status(partner_id, 'idle')
        await update.message.reply_text("Obrolan diakhiri. Gunakan /search untuk mencari lagi.")
        if partner_id:
            try:
                await context.bot.send_message(
                    chat_id=partner_id,
                    text="Partner Anda telah mengakhiri obrolan. Gunakan /search."
                )
            except Exception as e:
                logger.error(f"Gagal notif stop ke partner {partner_id}: {e}")
        if partner_id:
            feedback_text = "Bagaimana pengalaman ngobrolmu dengan partner tadi?"
            user_feedback_keyboard = [
                [
                    InlineKeyboardButton("👍 Suka", callback_data=f"feedback_like_{partner_id}"),
                    InlineKeyboardButton("🚫 Blokir", callback_data=f"feedback_block_{partner_id}"),
                    InlineKeyboardButton("🚩 Laporkan", callback_data=f"feedback_report_{partner_id}")
                ]
            ]
            partner_feedback_keyboard = [
                [
                    InlineKeyboardButton("👍 Suka", callback_data=f"feedback_like_{user_id}"),
                    InlineKeyboardButton("🚫 Blokir", callback_data=f"feedback_block_{user_id}"),
                    InlineKeyboardButton("🚩 Laporkan", callback_data=f"feedback_report_{user_id}")
                ]
            ]
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=feedback_text,
                    reply_markup=InlineKeyboardMarkup(user_feedback_keyboard)
                )
                await context.bot.send_message(
                    chat_id=partner_id,
                    text=feedback_text,
                    reply_markup=InlineKeyboardMarkup(partner_feedback_keyboard)
                )
            except Exception as e:
                logger.error(f"Gagal mengirim feedback keyboard: {e}")

    return ConversationHandler.END

async def search_in_progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Anda sedang dalam proses pencarian. Silakan pilih salah satu opsi di atas atau /stop untuk batal."
    )
    return None