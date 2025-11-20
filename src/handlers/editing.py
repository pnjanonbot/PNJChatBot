import re
import datetime
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from .. import database as db
from .. import config
from ..utils import (
    build_jurusan_keyboard, build_prodi_keyboard,
    build_gender_keyboard, send_verification_email,
    build_avatar_keyboard, is_valid_pnj_email
)

async def edit_profile_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    query = update.callback_query
    message = update.message
    reply_func = None
    error_reply_func = None
    if query:
        await query.answer()
        reply_func = query.edit_message_text
        error_reply_func = query.message.reply_text
    elif message:
        reply_func = message.reply_text
        error_reply_func = message.reply_text
    else:
        return ConversationHandler.END

    if not await db.check_profile_complete(user_id):
        await error_reply_func("Anda harus menyelesaikan registrasi dulu sebelum bisa mengedit. Silakan /register.")
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton("📧 Ubah Email (Wajib Verifikasi Ulang)", callback_data="edit_email")],
        [InlineKeyboardButton("🎓 Ubah Jurusan & Prodi", callback_data="edit_jurusan_prodi")],
        [InlineKeyboardButton("🚻 Ubah Gender", callback_data="edit_gender")],
        [InlineKeyboardButton("🗓️ Ubah Angkatan", callback_data="edit_angkatan")],
        [InlineKeyboardButton("📝 Ubah Bio", callback_data="edit_bio")],
        [InlineKeyboardButton("🎭 Ubah Avatar", callback_data="edit_avatar")],
        [InlineKeyboardButton("🚫 Daftar Blokir & Buka Blokir", callback_data="edit_blocked_list")],
        [InlineKeyboardButton("🖼️ Setelan Penerimaan Media", callback_data="edit_auto_media")],
        [InlineKeyboardButton("❌ Batal", callback_data="edit_cancel")]
    ]
    await reply_func(
        "Pilih data yang ingin Anda ubah:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return config.EDIT_MENU

async def edit_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "edit_email":
        await query.edit_message_text("Silakan masukkan alamat email PNJ baru Anda:")
        return config.EDIT_EMAIL_INPUT

    elif query.data == "edit_jurusan_prodi":
        await query.edit_message_text(
            "Pilih Jurusan baru Anda:",
            reply_markup=build_jurusan_keyboard()
        )
        return config.EDIT_JURUSAN_SELECT

    elif query.data == "edit_gender":
        await query.edit_message_text(
            "Pilih Gender baru Anda:",
            reply_markup=build_gender_keyboard()
        )
        return config.EDIT_GENDER_SELECT

    elif query.data == "edit_angkatan":
        await query.edit_message_text("Masukkan Angkatan baru Anda (Contoh: 2023):")
        return config.EDIT_ANGKATAN_INPUT

    elif query.data == "edit_bio":
        await query.edit_message_text("Tulis bio baru Anda (maks 150 karakter):")
        return config.EDIT_BIO

    elif query.data == "edit_avatar":
        await query.edit_message_text(
            "Pilih Avatar baru Anda:",
            reply_markup=build_avatar_keyboard()
        )
        return config.EDIT_AVATAR_SELECT

    elif query.data == "edit_blocked_list":
        return await show_blocked_list(update, context)
    elif query.data == "edit_auto_media":
        return await show_auto_media_menu(update, context)
    elif query.data == "edit_cancel":
        await query.edit_message_text("Dibatalkan.")
        return ConversationHandler.END

    return ConversationHandler.END

async def edit_jurusan_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    jurusan = query.data

    await db.update_user_profile(user_id, 'jurusan', jurusan)

    keyboard = build_prodi_keyboard(jurusan, back_button_callback="back_to_jurusan_edit")
    if not keyboard:
        await query.edit_message_text("Error: Jurusan tidak ditemukan. Silakan /cancel dan coba lagi.")
        return ConversationHandler.END
    await query.edit_message_text(
        f"Jurusan diubah ke: {jurusan}\n\nSekarang, pilih Program Studi baru Anda:",
        reply_markup=keyboard
    )
    return config.EDIT_PRODI_SELECT

async def back_to_edit_jurusan_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "Pilih Jurusan baru Anda:",
        reply_markup=build_jurusan_keyboard()
    )
    return config.EDIT_JURUSAN_SELECT

async def edit_prodi_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    prodi = query.data

    await db.update_user_profile(user_id, 'prodi', prodi)

    await query.edit_message_text("Jurusan & Prodi berhasil diubah!")
    return ConversationHandler.END

async def edit_gender_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    gender = query.data

    await db.update_user_profile(user_id, 'gender', gender)

    await query.edit_message_text(f"Gender berhasil diubah menjadi: {gender.title()}")
    return ConversationHandler.END

async def edit_angkatan_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    angkatan = update.message.text.strip()
    try:
        year = int(angkatan)
        current_year = datetime.datetime.now().year
        if 2015 <= year <= current_year:
            await db.update_user_profile(user_id, 'angkatan', angkatan)
            await update.message.reply_text(f"Angkatan berhasil diubah menjadi: {angkatan}")
            return ConversationHandler.END
        else:
            await update.message.reply_text(f"Angkatan tidak valid. Harap masukkan tahun antara 2015 dan {current_year}. Coba lagi:")
            return config.EDIT_ANGKATAN_INPUT
    except ValueError:
        await update.message.reply_text("Format angkatan tidak valid. Harap masukkan 4 digit tahun (Contoh: 2023). Coba lagi:")
        return config.EDIT_ANGKATAN_INPUT

async def edit_email_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    email = re.sub(r'\s+', '', update.message.text).lower()

    if not is_valid_pnj_email(email):
        domains_str = ', '.join(config.VALID_EMAIL_DOMAINS)
        await update.message.reply_text(
            f"Email tidak valid. HARUS berakhiran salah satu dari: {domains_str}.\n"
            "Silakan masukkan lagi atau /cancel."
        )
        return config.EDIT_EMAIL_INPUT

    existing_user = await db.get_user_by_email(email)
    if existing_user and existing_user['user_id'] != user_id:
        await update.message.reply_text("Email ini sudah terdaftar di akun lain. Silakan gunakan email yang berbeda atau /cancel.")
        return config.EDIT_EMAIL_INPUT
    code = str(random.randint(100000, 999999))

    await db.create_verification_state(user_id, email, code)
    await update.message.reply_text("Memproses email...")
    if send_verification_email(email, code):
        await update.message.reply_text(f"Kode verifikasi 6 digit telah dikirim ke {email}.\nSilakan cek inbox (atau spam) Anda dan masukkan kodenya.\n\nKetik /cancel untuk batal.")
        return config.EDIT_VERIFY_CODE
    else:
        await update.message.reply_text("Gagal mengirim email. Coba lagi, atau hubungi admin.")
        return config.EDIT_EMAIL_INPUT

async def edit_verify_code_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_code = update.message.text.strip()
    state = await db.get_verification_state(user_id)
    if not state:
        await update.message.reply_text("Sesi Anda telah berakhir. Silakan /cancel dan coba lagi.")
        return ConversationHandler.END

    correct_code = state.get("verify_code")
    email = state.get("email")

    if user_code == correct_code:
        await db.update_user_profile(user_id, 'email', email)
        await db.delete_verification_state(user_id)
        await update.message.reply_text("Email berhasil diubah!")
        return ConversationHandler.END
    else:
        await update.message.reply_text("Kode salah. Coba lagi, atau /cancel.")
        return config.EDIT_VERIFY_CODE

async def edit_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Proses edit dibatalkan.")
    else:
        await update.message.reply_text("Proses edit dibatalkan.")
    return ConversationHandler.END

async def edit_avatar_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    avatar = query.data
    if avatar not in config.AVATAR_LIST:
        await query.message.reply_text("Pilihan avatar tidak valid, coba lagi.")
        return config.EDIT_AVATAR_SELECT
    await db.update_user_profile(user_id, 'avatar', avatar)
    await query.edit_message_text(f"Avatar berhasil diubah menjadi: {avatar}")
    return ConversationHandler.END

async def edit_bio_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bio_text = update.message.text[:150]
    await db.update_user_profile(user_id, 'bio', bio_text)
    await update.message.reply_text(f"Bio berhasil diubah menjadi:\n\n{bio_text}")
    return ConversationHandler.END

async def show_blocked_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    blocked_users = await db.get_users_blocked_by(user_id)

    keyboard = []
    if not blocked_users:
        keyboard.append([InlineKeyboardButton("Anda belum memblokir siapa pun", callback_data="unblock_done")])
    else:
        for user in blocked_users:
            user_label = f"Buka Blokir: {user['jurusan']} - {user['prodi']} (...{str(user['blocked_id'])[-4:]})"
            keyboard.append(
                [InlineKeyboardButton(user_label, callback_data=f"unblock_user_{user['blocked_id']}")]
            )

    keyboard.append([InlineKeyboardButton("Selesai & Kembali", callback_data="unblock_done")])

    await query.edit_message_text(
        "Ini adalah daftar pengguna yang telah Anda blokir.\n\n"
        "Mem-buka blokir akan memungkinkan bot untuk memasangkan Anda dengan mereka lagi (jika mereka juga tidak memblokir Anda).",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    return config.EDIT_BLOCKED_LIST

async def handle_unblock_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    if data == "unblock_done":
        await query.edit_message_text("Pengeditan profil selesai.")
        return ConversationHandler.END
    if data.startswith("unblock_user_"):
        try:
            blocked_id = int(data.split('_')[-1])
            success = await db.unblock_user(user_id, blocked_id)

            if success:
                await query.answer("Berhasil membuka blokir!")
            else:
                await query.answer("Gagal membuka blokir.", show_alert=True)
            return await show_blocked_list(update, context)

        except Exception as e:
            await query.message.reply_text(f"Terjadi error: {e}")
            return ConversationHandler.END

async def show_auto_media_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    user = await db.get_user(user_id)
    current_status = user.get('auto_accept_media', False)

    status_icon = "🟢" if current_status else "🔴"
    status_text = "Aktif" if current_status else "Nonaktif"

    keyboard = [
        [InlineKeyboardButton(
            f"{status_icon} Otomatis Terima Media ({status_text})",
            callback_data="auto_media_toggle"
        )],
        [InlineKeyboardButton("Kembali", callback_data="auto_media_back")]
    ]

    await query.edit_message_text(
        "Atur preferensi penerimaan media Anda.\n\n"
        "Jika diaktifkan, media yang dikirim partner akan langsung tampil "
        "tanpa perlu persetujuan Anda.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return config.EDIT_AUTO_MEDIA

async def handle_auto_media_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    if data == "auto_media_back":
        await query.edit_message_text("Pengeditan profil selesai.")
        return ConversationHandler.END
    if data == "auto_media_toggle":
        user = await db.get_user(user_id)
        current_status = user.get('auto_accept_media', False)
        new_status = not current_status

        await db.update_user_profile(user_id, 'auto_accept_media', new_status)

        status_text = "DIAKTIFKAN" if new_status else "DINONAKTIFKAN"
        await query.answer(f"Otomatis Terima Media telah {status_text}", show_alert=True)

        return await show_auto_media_menu(update, context)

async def edit_in_progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Anda sedang dalam proses edit profil. Silakan selesaikan langkah saat ini atau /cancel untuk batal."
    )
    return None