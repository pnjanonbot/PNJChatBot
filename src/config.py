import os
import json
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
VALID_EMAIL_DOMAINS = tuple(domain.strip() for domain in os.getenv("VALID_EMAIL_DOMAINS", "").split(','))
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_APP_PASSWORD = os.getenv("SENDER_APP_PASSWORD")
SMTP_USER = os.getenv("SMTP_USER")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
DUMMY_USER_ID = os.getenv("DUMMY_USER_ID")
BAN_THRESHOLD = int(os.getenv("BAN_THRESHOLD", 3))
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", 3306))
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_NAME = os.getenv("DB_NAME")

def load_jurusan_prodi():
    try:
        with open('jurusan.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

JURUSAN_PRODI = load_jurusan_prodi()

ICEBREAKER_QUESTIONS = [
    "Lagi sibuk apa aja nih selain kuliah?",
    "Apa mata kuliah favoritmu semester ini dan kenapa?",
    "Kalau bisa punya kekuatan super, kamu mau punya kekuatan apa?",
    "Musik atau genre lagu apa yang lagi sering kamu dengerin?",
    "Kalau ada satu tempat di dunia yang bisa kamu kunjungi sekarang, kamu mau ke mana?",
    "Apa series atau film terakhir yang kamu tonton dan seru banget?",
]

REPORT_REASONS = ["Pelecehan/Abuse", "Spam", "Konten Tidak Pantas", "Lainnya"]

AVATAR_LIST = [
    "🐧", "🚀", "💻", "🎨", "🦉", "🤔", "👻", "🤖", "🦊", "👑"
]

(ASK_EMAIL, CONFIRM_EMAIL, VERIFY_CODE, REGISTER_NAMA, REGISTER_JURUSAN,
 REGISTER_PRODI, REGISTER_ANGKATAN, REGISTER_GENDER, REGISTER_AVATAR,
 REGISTER_BIO, VERIFY_REVOKE_CODE) = range(11) 
(EDIT_MENU, EDIT_JURUSAN_SELECT, EDIT_PRODI_SELECT,
 EDIT_GENDER_SELECT, EDIT_ANGKATAN_INPUT, EDIT_EMAIL_INPUT,
 EDIT_VERIFY_CODE, EDIT_BIO, EDIT_AVATAR_SELECT) = range(11, 20)
(REPORT_REASON_SELECT, REPORT_OTHER_DETAIL) = range(20, 22)
EDIT_BLOCKED_LIST = 22
(SEARCH_PREF_GENDER, SEARCH_PROCESSING) = range(23, 25)
EDIT_AUTO_MEDIA = 25

BAD_WORDS = [
    "anjing", "babi", "bangsat", "kontol", "memek", "jembut",
    "ngentot", "pantek", "tolol", "goblok", "bodoh", "lonte"
]