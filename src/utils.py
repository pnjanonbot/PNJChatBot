import logging
import smtplib
import ssl
import html
import time
import re
from email.mime.text import MIMEText
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup

from . import database as db
from . import config

logger = logging.getLogger(__name__)

user_last_message_time = {}

def is_spamming(user_id: int, limit: float = 1.0) -> bool:
    current_time = time.time()
    last_time = user_last_message_time.get(user_id, 0)
    
    if current_time - last_time < limit:
        return True
    
    user_last_message_time[user_id] = current_time
    return False

def is_valid_pnj_email(email: str) -> bool:
    escaped_domains = [re.escape(d) for d in config.VALID_EMAIL_DOMAINS]
    pattern = r'^[a-zA-Z0-9._%+-]+@({})$'.format('|'.join(escaped_domains))
    
    if re.fullmatch(pattern, email):
        return True
    return False

def get_like_badge(like_count: int) -> str:
    if like_count >= 50:
        return "👑 LEGENDARIS"
    elif like_count >= 20:
        return "🌟 Populer"
    elif like_count >= 10:
        return "✨ Dikenal"
    else:
        return ""

def format_profile(user_data: dict) -> str:
    if not user_data:
        return "❌ Profil partner tidak ditemukan."
    
    gender_map = {"cowo": "Laki-laki ♂️", "cewe": "Perempuan ♀️"}
    
    nama = html.escape(user_data.get('nama', 'N/A')) 
    jurusan = html.escape(user_data.get('jurusan', 'N/A'))
    prodi = html.escape(user_data.get('prodi', 'N/A'))
    bio = html.escape(user_data.get('bio', 'N/A'))

    gender = gender_map.get(user_data.get('gender', '').lower(), 'N/A')
    like_count = user_data.get('like_count', 0)
    badge = get_like_badge(like_count)
    avatar = user_data.get('avatar', '👤')

    return (
        f"<b>{avatar} Partner Ditemukan!</b>\n"
        f"{f'<b>{badge}</b> ' if badge else ''}(👍 Disukai {like_count} kali)\n\n"
        f"Berikut adalah profil partner ngobrolmu:\n\n"
        f"🎓 <b>Jurusan:</b> {jurusan}\n"
        f"📚 <b>Prodi:</b> {prodi}\n"
        f"🗓️ <b>Angkatan:</b> {user_data.get('angkatan', 'N/A')}\n"
        f"👤 <b>Gender:</b> {gender}\n\n"
        f"📝 <b>Bio:</b>\n"
        f"<i>{bio}</i>"
    )

def format_profile_for_admin(user_data: dict) -> str:
    if not user_data:
        return "Data User Penuh Tidak Ditemukan."
    return (
        f"Nama: {user_data.get('nama', 'N/A')}\n"
        f"Email: {user_data.get('email', 'N/A')}\n"
        f"Jurusan: {user_data.get('jurusan', 'N/A')}\n"
        f"Prodi: {user_data.get('prodi', 'N/A')}\n"
        f"Angkatan: {user_data.get('angkatan', 'N/A')}\n"
        f"Bio: {user_data.get('bio', 'N/A')}\n"
        f"User ID: {user_data.get('user_id', 'N/A')}\n"
        f"Laporan: {user_data.get('report_count', 0)}\n"
        f"Disukai: {user_data.get('like_count', 0)}"
    )

def format_my_profile(user_data: dict) -> str:
    if not user_data:
        return "Gagal memuat profil."
    
    gender_map = {"cowo": "Laki-laki ♂️", "cewe": "Perempuan ♀️"}
    
    nama = html.escape(user_data.get('nama', 'N/A'))
    email = html.escape(user_data.get('email', 'N/A'))
    jurusan = html.escape(user_data.get('jurusan', 'N/A'))
    prodi = html.escape(user_data.get('prodi', 'N/A'))
    bio = html.escape(user_data.get('bio', 'N/A'))

    gender = gender_map.get(user_data.get('gender', '').lower(), 'N/A')
    like_count = user_data.get('like_count', 0)
    badge = get_like_badge(like_count)
    avatar = user_data.get('avatar', '👤')

    profile_text = (
        f"{avatar} <b>Profil Anda</b> {f'<b>{badge}</b>' if badge else ''}\n\n"
        f"• <b>Nama:</b> {nama}\n"
        f"• <b>Email:</b> {email}\n"
        f"• <b>Gender:</b> {gender}\n"
        f"• <b>Angkatan:</b> {user_data.get('angkatan', 'N/A')}\n\n"
        f"🎓 <b>Akademik:</b>\n"
        f"• <b>Jurusan:</b> {jurusan}\n"
        f"• <b>Prodi:</b> {prodi}\n\n"
        f"📝 <b>Bio:</b>\n"
        f"<i>{bio}</i>\n\n"
        f"----\n"
        f"👍 <b>Disukai:</b> {user_data.get('like_count', 0)} kali\n"
        f"🚫 <b>Laporan Diterima:</b> {user_data.get('report_count', 0)} kali"
        f"\n\n📊 <b>Statistik Anda:</b>\n"
        f"• <b>Total Obrolan:</b> {user_data.get('total_chats', 0)}\n"
        f"• <b>Total Pesan Terkirim:</b> {user_data.get('total_messages_sent', 0)}"
    )
    return profile_text

def build_jurusan_keyboard():
    keyboard = []
    for jurusan in config.JURUSAN_PRODI.keys():
        keyboard.append([InlineKeyboardButton(jurusan, callback_data=jurusan)])
    return InlineKeyboardMarkup(keyboard)

def build_prodi_keyboard(jurusan: str, back_button_callback: str = None):
    keyboard = []
    try:
        for prodi in config.JURUSAN_PRODI[jurusan]:
            keyboard.append([InlineKeyboardButton(prodi, callback_data=prodi)])
    except KeyError:
        return None
    if back_button_callback:
        keyboard.append([InlineKeyboardButton("⬅️ Kembali", callback_data=back_button_callback)])
    return InlineKeyboardMarkup(keyboard)

def build_gender_keyboard():
    keyboard = [[
        InlineKeyboardButton("♂️ Cowo", callback_data="cowo"),
        InlineKeyboardButton("♀️ Cewe", callback_data="cewe")
    ]]
    return InlineKeyboardMarkup(keyboard)

def build_avatar_keyboard():
    keyboard = []
    row = []
    for i, avatar in enumerate(config.AVATAR_LIST):
        row.append(InlineKeyboardButton(avatar, callback_data=avatar))
        if (i + 1) % 5 == 0:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    return InlineKeyboardMarkup(keyboard)

def send_verification_email(receiver_email: str, code: str) -> bool:
    logger.info(f"Mencoba mengirim email ke {receiver_email}...")
    body = f"Gunakan kode ini untuk memverifikasi akun Anda di bot Telegram PNJ:\n\n{code}\n\nJika Anda tidak meminta ini, abaikan saja."
    msg = MIMEText(body)
    msg['Subject'] = f"Kode Verifikasi Bot PNJ: {code}"
    msg['From'] = config.SENDER_EMAIL
    msg['To'] = receiver_email
    context = ssl.create_default_context()
    try:
        server = smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT)
        server.starttls(context=context)
        server.login(config.SMTP_USER, config.SENDER_APP_PASSWORD)
        server.sendmail(config.SENDER_EMAIL, receiver_email, msg.as_string())
        server.quit()
        logger.info(f"Email berhasil dikirim ke {receiver_email}.")
        return True
    except Exception as e:
        logger.error(f"Error saat kirim email: {e}")
        return False

async def check_is_banned(user_id: int, update: Update) -> bool:
    user = await db.get_user(user_id)
    if user and user['report_count'] >= config.BAN_THRESHOLD:
        if update.message:
            await update.message.reply_text(
                "Akun Anda telah ditangguhkan (suspended) karena beberapa laporan.\n"
                "Silakan hubungi admin."
            )
        return True
    return False

async def is_profile_complete(user_id, update: Update):
    if await db.check_profile_complete(user_id):
        return True
    if update.message:
        await update.message.reply_text("Profil Anda belum lengkap.\nSilakan gunakan /register.")
    return False