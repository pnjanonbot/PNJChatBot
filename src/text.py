START_MESSAGE = (
    "Selamat datang kembali!\n\n"
    "Siap untuk mencari teman baru?"
)

START_REGISTER_MESSAGE = (
    "Selamat datang!\nBot ini butuh verifikasi email PNJ.\n\n"
    "Silakan masukkan email PNJ Anda (harus berakhiran salah satu dari: "
    "{domains}).\n\n"
    "Ketik /cancel untuk batal."
)

HELP_USER = (
    "<b>Daftar Perintah Bot PNJ Anon</b>\n\n"
    "Berikut adalah daftar perintah yang bisa Anda gunakan:\n\n"
    "<b>Perintah Utama:</b>\n"
    "• /start - Memulai bot dan menampilkan menu utama.\n"
    "• /help - Menampilkan pesan bantuan ini.\n"
    "• /search - Mulai mencari partner untuk mengobrol.\n"
    "• /stop - Menghentikan pencarian atau mengakhiri obrolan saat ini.\n\n"
    "<b>Manajemen Profil:</b>\n"
    "• /myprofile - Menampilkan profil Anda saat ini.\n"
    "• /editprofile - Mengizinkan Anda untuk mengubah detail profil.\n\n"
    "<b>Interaksi:</b>\n"
    "• /report - Melaporkan partner ngobrol Anda saat ini (hanya dalam chat).\n\n"
    "<b>Lainnya:</b>\n"
    "• /stats - Menampilkan statistik bot.\n"
    "• /cancel - Membatalkan proses saat ini (misalnya saat registrasi)."
)

HELP_ADMIN = (
    "\n\n<b>Perintah Admin:</b>\n"
    "• /admin_ban <code>&lt;user_id&gt;</code> - Ban user.\n"
    "• /admin_unban <code>&lt;user_id&gt;</code> - Unban user.\n"
    "• /admin_check <code>&lt;user_id&gt;</code> - Cek profil user.\n"
    "• /user - Lihat semua user.\n"
    "• /admin_broadcast <code>&lt;pesan&gt;</code> - Kirim pesan ke semua user.\n"
    "• /admin_broadcast_dummy <code>&lt;pesan&gt;</code> - Kirim pesan ke user dummy."
)

STATS_TEMPLATE = (
    "<b>Statistik Bot PNJ Anon</b>\n\n"
    "• <b>Total User:</b> {total}\n"
    "• <b>Sedang Chatting:</b> {chatting} ({pairs} pasang)\n"
    "• <b>Sedang Menunggu:</b> {waiting}"
)
