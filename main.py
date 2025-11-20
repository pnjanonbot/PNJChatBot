import logging
import logging.handlers
import sys
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
)

from src import config, database as db
from src.handlers.admin import (
    admin_unban_command,
    admin_ban_command,
    admin_check_command,
    admin_broadcast_command,
    admin_user_command,
    admin_broadcast_dummy_command,
)
from src.handlers.commands import (
    help_command,
    myprofile_command,
    stats_command,
    feedback_handler,
)
from src.handlers.editing import (
    edit_profile_start,
    edit_menu_handler,
    edit_jurusan_handler,
    edit_prodi_handler,
    edit_gender_handler,
    edit_angkatan_handler,
    edit_email_input_handler,
    edit_verify_code_handler,
    edit_bio_handler,
    edit_cancel,
    back_to_edit_jurusan_selection,
    edit_avatar_handler,
    show_blocked_list,
    handle_unblock_action,
    handle_auto_media_choice,
    edit_in_progress,
)
from src.handlers.main_menu import main_menu_callback_handler, handle_block_callback
from src.handlers.messaging import (
    handle_message,
    report_command,
    cancel_report,
    confirm_report,
    report_reason_handler,
    handle_media_accept,
    handle_media_decline,
    report_other_detail_handler,
    cancel_report_conv,
)
from src.handlers.registration import (
    register_start,
    handle_email,
    handle_email_confirmation,
    handle_verification,
    handle_transfer_choice,
    handle_revoke_code,
    register_nama,
    register_jurusan,
    register_prodi,
    register_angkatan,
    register_gender,
    register_bio,
    register_cancel,
    register_avatar,
    back_to_jurusan_selection,
    register_in_progress,
)
from src.handlers.searching import (
    search_command_entry,
    stop_command,
    handle_search_choice,
    search_in_progress,
)

log_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

try:
    file_handler = logging.handlers.RotatingFileHandler(
        "pnjbot.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(log_formatter)
    root_logger.addHandler(file_handler)
except PermissionError:
    print("Peringatan: Tidak bisa menulis ke pnjbot.log karena masalah izin. Logging hanya ke konsol.")

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(log_formatter)
root_logger.addHandler(console_handler)

logger = logging.getLogger(__name__)

async def post_init_db(application: Application) -> None:
    await db.init_db()

async def post_shutdown_db(application: Application) -> None:
    await db.close_db()

def main() -> None:
    logger.info("Memulai bot...")
    application = (
        Application.builder()
        .token(config.BOT_TOKEN)
        .connect_timeout(10)
        .read_timeout(30)
        .post_init(post_init_db)
        .post_shutdown(post_shutdown_db)
        .build()
    )

    reg_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("register", register_start),
            CommandHandler("start", register_start),
        ],
        states={
            config.ASK_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_email)],
            
            config.CONFIRM_EMAIL: [
                CallbackQueryHandler(handle_email_confirmation, pattern="^reg_email_")
            ],
            
            config.VERIFY_CODE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_verification),
                CallbackQueryHandler(handle_transfer_choice, pattern="^transfer_"),
            ],
            config.VERIFY_REVOKE_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_revoke_code)],
            config.REGISTER_NAMA: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_nama)],
            config.REGISTER_JURUSAN: [CallbackQueryHandler(register_jurusan)],
            config.REGISTER_PRODI: [
                CallbackQueryHandler(back_to_jurusan_selection, pattern="^back_to_jurusan_reg$"),
                CallbackQueryHandler(register_prodi),
            ],
            config.REGISTER_ANGKATAN: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_angkatan)],
            config.REGISTER_GENDER: [CallbackQueryHandler(register_gender)],
            config.REGISTER_AVATAR: [CallbackQueryHandler(register_avatar)],
            config.REGISTER_BIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_bio)],
        },
        fallbacks=[
            CommandHandler("cancel", register_cancel),
            CommandHandler("register", register_in_progress),
            CommandHandler("start", register_in_progress),
        ],
    )

    edit_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("editprofile", edit_profile_start),
            CallbackQueryHandler(edit_profile_start, pattern="^main_edit$"),
        ],
        states={
            config.EDIT_MENU: [CallbackQueryHandler(edit_menu_handler, pattern="^edit_")],
            config.EDIT_JURUSAN_SELECT: [CallbackQueryHandler(edit_jurusan_handler)],
            config.EDIT_PRODI_SELECT: [
                CallbackQueryHandler(back_to_edit_jurusan_selection, pattern="^back_to_jurusan_edit$"),
                CallbackQueryHandler(edit_prodi_handler),
            ],
            config.EDIT_GENDER_SELECT: [CallbackQueryHandler(edit_gender_handler)],
            config.EDIT_ANGKATAN_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_angkatan_handler)],
            config.EDIT_EMAIL_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_email_input_handler)],
            config.EDIT_VERIFY_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_verify_code_handler)],
            config.EDIT_BIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_bio_handler)],
            config.EDIT_AVATAR_SELECT: [CallbackQueryHandler(edit_avatar_handler)],
            config.EDIT_BLOCKED_LIST: [CallbackQueryHandler(handle_unblock_action, pattern="^unblock_")],
            config.EDIT_AUTO_MEDIA: [CallbackQueryHandler(handle_auto_media_choice, pattern="^auto_media_")],
        },
        fallbacks=[
            CommandHandler("cancel", edit_cancel),
            CommandHandler("editprofile", edit_in_progress),
        ],
    )

    search_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("search", search_command_entry),
            CallbackQueryHandler(search_command_entry, pattern="^main_search$"),
        ],
        states={
            config.SEARCH_PREF_GENDER: [
                CallbackQueryHandler(handle_search_choice, pattern="^search_")
            ],
        },
        fallbacks=[
            CommandHandler("stop", stop_command),
            CommandHandler("search", search_in_progress),
        ],
    )

    application.add_handler(reg_conv_handler)
    application.add_handler(edit_conv_handler)
    application.add_handler(search_conv_handler)

    application.add_handler(CallbackQueryHandler(main_menu_callback_handler, pattern="^main_"))
    application.add_handler(CallbackQueryHandler(handle_block_callback, pattern=r"^feedback_block_"))

    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(CommandHandler("myprofile", myprofile_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("report", report_command))
    application.add_handler(CallbackQueryHandler(feedback_handler, pattern="^feedback_"))

    report_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(confirm_report, pattern=r"^report_yes_")],
        states={
            config.REPORT_REASON_SELECT: [
                CallbackQueryHandler(report_reason_handler, pattern="^report_reason_")
            ],
            config.REPORT_OTHER_DETAIL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, report_other_detail_handler)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_report_conv),
            CallbackQueryHandler(cancel_report, pattern=r"^report_no$"),
        ],
    )
    application.add_handler(report_conv_handler)

    application.add_handler(CallbackQueryHandler(handle_media_accept, pattern=r"^media_accept_"))
    application.add_handler(CallbackQueryHandler(handle_media_decline, pattern=r"^media_decline_"))

    application.add_handler(CommandHandler("admin_unban", admin_unban_command))
    application.add_handler(CommandHandler("admin_ban", admin_ban_command))
    application.add_handler(CommandHandler("admin_check", admin_check_command))
    application.add_handler(CommandHandler("admin_broadcast", admin_broadcast_command))
    application.add_handler(CommandHandler(["user", "users"], admin_user_command))
    application.add_handler(CommandHandler("admin_broadcast_dummy", admin_broadcast_dummy_command))

    media_filters = filters.TEXT | filters.PHOTO | filters.VOICE | filters.VIDEO | filters.ANIMATION
    application.add_handler(MessageHandler(media_filters & ~filters.COMMAND, handle_message))

    application.job_queue.run_repeating(
        db.cleanup_stale_pending_media,
        interval=86400, 
        first=10
    )
    logger.info("Job pembersihan pending_media harian telah dijadwalkan.")

    application.run_polling()

if __name__ == "__main__":
    main()