import logging
import re
import random
import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, ConversationHandler

from .. import database as db
from .. import config
from ..utils import (
    check_is_banned, send_verification_email,
    build_jurusan_keyboard, build_prodi_keyboard, build_gender_keyboard,
    build_avatar_keyboard, format_my_profile, is_valid_pnj_email
)

logger = logging.getLogger(__name__)

async def register_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if str(user_id) == config.DUMMY_USER_ID:
        await db.create_user(user_id)
        await update.message.reply_text("Dummy user profile is active. Ready for testing. シ")
        return ConversationHandler.END
    if await check_is_banned(user_id, update):
        return ConversationHandler.END
    if await db.check_profile_complete(user_id):
        await update.message.reply_text("Anda sudah teregister シ\n\nGunakan /search untuk mencari teman atau lihat menu di /help.")
        return ConversationHandler.END
    await db.create_user(user_id)
    await update.message.reply_text(
        f"Selamat datang!\nBot ini butuh verifikasi email PNJ untuk memastikan kamu adalah mahasiswa PNJ.\n\n"
        f"Silakan masukkan email PNJ Anda (harus berakhiran salah satu dari: {', '.join(config.VALID_EMAIL_DOMAINS)}).\n\n"
        "Ketik /cancel untuk batal."
    )
    return config.ASK_EMAIL

async def handle_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    email = re.sub(r'\s+', '', update.message.text).lower()
    
    if not is_valid_pnj_email(email):
        domains_str = ', '.join(config.VALID_EMAIL_DOMAINS)
        await update.message.reply_text(
            f"⚠️ <b>Email tidak valid.</b>\n\n"
            f"Harus menggunakan email resmi PNJ dengan akhiran persis:\n"
            f"<code>{domains_str}</code>\n\n"
            f"Contoh: <code>namamu@stu.pnj.ac.id</code>\n"
            "Silakan masukkan lagi atau /cancel.",
            parse_mode=ParseMode.HTML
        )
        return config.ASK_EMAIL

    context.user_data['register_email'] = email
    
    keyboard = [
        [
            InlineKeyboardButton("👍 Ya, Benar", callback_data="reg_email_confirm"),
            InlineKeyboardButton("✏️ Edit", callback_data="reg_email_edit")
        ]
    ]
    
    await update.message.reply_text(
        f"Apakah email Anda sudah benar?\n\n<b>{email}</b>\n\nKetik /cancel untuk batal.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )
    
    return config.CONFIRM_EMAIL

async def handle_email_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    choice = query.data

    if choice == "reg_email_edit":
        await query.edit_message_text("Oke, silakan masukkan ulang email Anda:")
        return config.ASK_EMAIL

    if choice == "reg_email_confirm":
        email = context.user_data.get('register_email')
        if not email:
            await query.edit_message_text("Sesi berakhir. Silakan /register ulang.")
            return ConversationHandler.END

        code = str(random.randint(100000, 999999))
        await db.create_verification_state(user_id, email, code)
        
        await query.edit_message_text("Memproses email...")
        
        if send_verification_email(email, code):
            await query.edit_message_text(f"Kode verifikasi 6 digit telah dikirim ke {email}.\nSilakan cek inbox (atau spam) Anda dan masukkan kodenya.\n\nKetik /cancel untuk batal.")
            return config.VERIFY_CODE
        else:
            await query.edit_message_text("Gagal mengirim email. Coba lagi, atau hubungi admin jika masalah berlanjut.")
            return config.ASK_EMAIL

async def handle_verification(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_code = update.message.text.strip()
    state = await db.get_verification_state(user_id)
    if not state:
        await update.message.reply_text("Sesi Anda telah berakhir. Silakan /register ulang.")
        return ConversationHandler.END
    correct_code = state.get("verify_code")
    email = state.get("email")
    if user_code == correct_code:
        success = await db.update_user_profile(user_id, 'email', email)
        if success:
            await db.delete_verification_state(user_id)
            await update.message.reply_text("Email berhasil diverifikasi!\n\nLanjut ke profil. Siapa nama lengkap Anda?")
            return config.REGISTER_NAMA
        else:
            keyboard = [
                [InlineKeyboardButton("Ya, Cabut & Transfer Akun", callback_data="transfer_start")],
                [InlineKeyboardButton("Batal (Gunakan email lain)", callback_data="transfer_cancel")]
            ]
            await update.message.reply_text(
                "Email ini sudah terdaftar di akun lain.\n\n"
                "Apakah Anda ingin 'mencabut' email tersebut dari akun lama dan mentransfernya ke akun ini?",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return config.VERIFY_CODE
    else:
        await update.message.reply_text("Kode salah. Coba lagi, atau /cancel.")
        return config.VERIFY_CODE

async def handle_transfer_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if query.data == "transfer_cancel":
        await query.edit_message_text("Dibatalkan. Silakan masukkan email PNJ lain.")
        return config.ASK_EMAIL
    elif query.data == "transfer_start":
        state = await db.get_verification_state(user_id)
        if not state:
            await query.edit_message_text("Terjadi error. Silakan /cancel dan /register ulang.")
            return ConversationHandler.END
        email = state.get("email")
        code = str(random.randint(100000, 999999))
        await db.update_verification_revoke_code(user_id, code)
        if send_verification_email(email, code):
            await query.edit_message_text(
                f"Sebuah kode <b>TRANSFER</b> baru telah dikirim ke {email}.\n"
                "Ini akan mencabut email dari akun lama.\n\n"
                "Masukkan kode 6 digit tersebut untuk konfirmasi.",
                parse_mode=ParseMode.HTML
            )
            return config.VERIFY_REVOKE_CODE
        else:
            await query.edit_message_text("Gagal mengirim email transfer. Silakan /cancel dan coba lagi.")
            return ConversationHandler.END

async def handle_revoke_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_code = update.message.text.strip()
    user_id = update.effective_user.id
    state = await db.get_verification_state(user_id)
    if not state:
        await update.message.reply_text("Terjadi error. Sesi Anda berakhir. Silakan /cancel dan /register ulang.")
        return ConversationHandler.END
    correct_code = state.get("revoke_code")
    email = state.get("email")
    if user_code != correct_code:
        await update.message.reply_text("Kode transfer salah. Coba lagi, atau /cancel.")
        return config.VERIFY_REVOKE_CODE
    old_user_data = await db.get_user_by_email(email)
    if old_user_data:
        old_user_id = old_user_data['user_id']
        await db.clear_user_field(old_user_id, 'email')
        try:
            await context.bot.send_message(
                chat_id=old_user_id,
                text=f"<b>PEMBERITAHUAN KEAMANAN</b>\nEmail Anda ({email}) telah dicabut dan ditransfer ke akun Telegram lain.",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.warning(f"Gagal notif user lama {old_user_id} soal pencabutan email: {e}")
    await db.update_user_profile(user_id, 'email', email)
    await db.delete_verification_state(user_id)
    await update.message.reply_text(
        "Transfer email berhasil! Akun Anda sekarang terverifikasi.\n\n"
        "Lanjut ke profil. Siapa nama lengkap Anda?"
    )
    return config.REGISTER_NAMA

async def register_nama(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await db.update_user_profile(user_id, 'nama', update.message.text)
    await update.message.reply_text(
        "Oke, dicatat!\nSekarang, pilih Jurusan Anda:",
        reply_markup=build_jurusan_keyboard()
    )
    return config.REGISTER_JURUSAN

async def register_jurusan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    jurusan = query.data
    await db.update_user_profile(user_id, 'jurusan', jurusan)
    keyboard = build_prodi_keyboard(jurusan, back_button_callback="back_to_jurusan_reg")
    if not keyboard:
        await query.edit_message_text("Error: Jurusan tidak ditemukan. Silakan /cancel dan coba lagi.")
        return ConversationHandler.END
    await query.edit_message_text(
        f"Jurusan: {jurusan}\n\nSekarang, pilih Program Studi Anda:",
        reply_markup=keyboard
    )
    return config.REGISTER_PRODI

async def back_to_jurusan_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "Pilih Jurusan Anda:",
        reply_markup=build_jurusan_keyboard()
    )
    return config.REGISTER_JURUSAN

async def register_prodi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    prodi = query.data
    await db.update_user_profile(user_id, 'prodi', prodi)
    user_data = await db.get_user(user_id)
    jurusan = user_data.get('jurusan', 'N/A')
    await query.edit_message_text(f"Jurusan: {jurusan}\nProdi: {prodi}\n\nSip, dicatat!")
    await context.bot.send_message(
        chat_id=user_id,
        text="Hampir selesai.\nAngkatan tahun berapa Anda? (Contoh: 2023)"
    )
    return config.REGISTER_ANGKATAN

async def register_angkatan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    angkatan = update.message.text.strip()
    try:
        year = int(angkatan)
        current_year = datetime.datetime.now().year
        if 2015 <= year <= current_year:
            await db.update_user_profile(user_id, 'angkatan', angkatan)
            await update.message.reply_text("Oke! Lanjut, pilih gender Anda:", reply_markup=build_gender_keyboard())
            return config.REGISTER_GENDER
        else:
            await update.message.reply_text(f"Angkatan tidak valid. Harap masukkan tahun antara 2015 dan {current_year}.")
            return config.REGISTER_ANGKATAN
    except ValueError:
        await update.message.reply_text("Format angkatan tidak valid. Harap masukkan 4 digit tahun (Contoh: 2023).")
        return config.REGISTER_ANGKATAN

async def register_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    gender = query.data
    await db.update_user_profile(user_id, 'gender', gender)
    gender_text = "♂️ Cowo" if gender == "cowo" else "♀️ Cewe"
    await query.edit_message_text(text=f"Anda memilih: {gender_text}")
    await context.bot.send_message(
        chat_id=user_id,
        text="Pilih 'Avatar' anonim Anda.\nIni akan dilihat oleh partner chat Anda.",
        reply_markup=build_avatar_keyboard()
    )
    return config.REGISTER_AVATAR

async def register_avatar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    avatar = query.data
    if avatar not in config.AVATAR_LIST:
        await query.message.reply_text("Pilihan avatar tidak valid, coba lagi.")
        return config.REGISTER_AVATAR
    await db.update_user_profile(user_id, 'avatar', avatar)
    await query.edit_message_text(text=f"Anda memilih avatar: {avatar}")
    await context.bot.send_message(
        chat_id=user_id,
        text="Terakhir, tulis bio singkat/hobi Anda (maks 150 karakter).\nIni akan dilihat oleh partner chat Anda."
    )
    return config.REGISTER_BIO

async def register_bio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bio_text = update.message.text[:150]
    await db.update_user_profile(user_id, 'bio', bio_text)
    await db.update_user_status(user_id, 'idle')
    user_data = await db.get_user(user_id)
    profile_text = format_my_profile(user_data)
    await update.message.reply_text(
        f"Registrasi Selesai!\n\nIni adalah profil Anda:\n\n{profile_text}\n\n"
        "Gunakan /search untuk mulai mencari teman atau /help untuk melihat menu.",
        parse_mode=ParseMode.HTML
    )
    return ConversationHandler.END

async def register_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await db.delete_verification_state(user_id)
    await update.message.reply_text("Pendaftaran dibatalkan. 씁쓸...")
    return ConversationHandler.END

async def register_in_progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Anda sedang dalam proses registrasi. Silakan selesaikan langkah saat ini atau /cancel untuk batal."
    )
    return None