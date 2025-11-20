import aiomysql
import logging

from . import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

g_pool = None

async def init_db():
    global g_pool
    if g_pool:
        return

    try:
        g_pool = await aiomysql.create_pool(
            host=config.DB_HOST,
            port=config.DB_PORT,
            user=config.DB_USER,
            password=config.DB_PASS,
            db=config.DB_NAME,
            autocommit=False,
            minsize=1,
            maxsize=10
        )

        async with g_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY,
                        status VARCHAR(255) NOT NULL DEFAULT 'idle',
                        partner_id BIGINT,
                        nama VARCHAR(255),
                        jurusan VARCHAR(255),
                        prodi VARCHAR(255),
                        angkatan VARCHAR(50),
                        gender VARCHAR(50),
                        email VARCHAR(255) UNIQUE,
                        report_count INT NOT NULL DEFAULT 0,
                        like_count INT NOT NULL DEFAULT 0,
                        bio TEXT,
                        avatar VARCHAR(10) DEFAULT '👤',
                        pref_gender VARCHAR(10) DEFAULT 'apa_saja',
                        auto_accept_media BOOLEAN NOT NULL DEFAULT FALSE,
                        total_chats INT NOT NULL DEFAULT 0,
                        total_messages_sent INT NOT NULL DEFAULT 0,
                        waiting_since DATETIME NULL DEFAULT NULL
                    )
                """)

                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS match_history (
                        user_id_1 BIGINT NOT NULL,
                        user_id_2 BIGINT NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (user_id_1, user_id_2)
                    )
                """)

                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS verification_state (
                        user_id BIGINT PRIMARY KEY,
                        email VARCHAR(255),
                        verify_code VARCHAR(10),
                        revoke_code VARCHAR(10),
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                    )
                """)

                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS pending_media (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        sender_id BIGINT NOT NULL,
                        receiver_id BIGINT NOT NULL,
                        file_id VARCHAR(255) NOT NULL,
                        file_type VARCHAR(50) NOT NULL,
                        caption TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS blocked_users (
                        blocker_id BIGINT NOT NULL,
                        blocked_id BIGINT NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (blocker_id, blocked_id),
                        FOREIGN KEY (blocker_id) REFERENCES users(user_id) ON DELETE CASCADE
                    )
                """)



        logging.info("Database MySQL pool berhasil diinisialisasi.")
    except Exception as e:
        logging.error(f"Error saat inisialisasi MySQL pool: {e}")
        raise e

async def get_user(user_id):
    try:
        async with g_pool.acquire() as conn:
            async with conn.cursor(aiomysql.cursors.DictCursor) as cursor:
                await cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
                return await cursor.fetchone()
    except Exception as e:
        logging.error(f"Error saat get_user {user_id}: {e}")
        return None

async def create_user(user_id):
    if str(user_id) == config.DUMMY_USER_ID:
        try:
            async with g_pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO users (user_id, status, nama, jurusan, prodi, angkatan, gender, email, bio, report_count, like_count)
                        VALUES (%s, 'idle', 'Dummy User', '-', '-', '-', 'cewe', CONCAT('dummy.', %s, '@dummy.com'), 'This is a dummy user for testing.', 0, 0)
                        ON DUPLICATE KEY UPDATE
                            status = VALUES(status),
                            nama = VALUES(nama),
                            jurusan = VALUES(jurusan),
                            prodi = VALUES(prodi),
                            angkatan = VALUES(angkatan),
                            gender = VALUES(gender),
                            email = VALUES(email),
                            bio = VALUES(bio),
                            report_count = 0,
                            like_count = 0
                        """,
                        (user_id, user_id)
                    )
                    await conn.commit()
                    logging.info(f"Dummy user profile created/reset for: {user_id} (Gender: cewe)")
            return
        except Exception as e:
            logging.error(f"Error saat create/reset dummy user {user_id}: {e}")
            return
    if await get_user(user_id):
        return
    try:
        async with g_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("INSERT INTO users (user_id, status) VALUES (%s, 'unregistered')", (user_id,))
                await conn.commit()
                logging.info(f"User baru dibuat: {user_id}")
    except Exception as e:
        logging.error(f"Error saat create_user {user_id}: {e}")

async def update_user_profile(user_id, field, value):
    allowed_fields = ['nama', 'jurusan', 'prodi', 'angkatan', 'gender',
                      'email', 'bio', 'like_count', 'avatar',
                      'pref_gender',
                      'auto_accept_media', 'total_chats', 'total_messages_sent']
    if field not in allowed_fields:
        logging.error(f"Attempt to update invalid field '{field}' for user {user_id}")
        return False
    try:
        async with g_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                query = f"UPDATE users SET {field} = %s WHERE user_id = %s"
                await cursor.execute(query, (value, user_id))
                await conn.commit()
            return True
    except Exception as e:
        if 'UNIQUE constraint' in str(e) or 'Duplicate entry' in str(e):
             logging.warning(f"IntegrityError (email duplikat) saat update {field} untuk {user_id}: {e}")
        else:
            logging.error(f"Error saat update_user_profile {user_id}: {e}")
        return False

async def check_profile_complete(user_id):
    user = await get_user(user_id)
    if not user:
        return False
    required_fields = ['email', 'nama', 'jurusan', 'prodi', 'angkatan', 'gender']
    return all(user.get(field) is not None for field in required_fields)

async def update_user_status(user_id, status, partner_id=None):
    try:
        async with g_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                if status == 'waiting':
                    await cursor.execute(
                        "UPDATE users SET status = %s, partner_id = %s, waiting_since = NOW() WHERE user_id = %s",
                        (status, partner_id, user_id)
                    )
                else:
                    await cursor.execute(
                        "UPDATE users SET status = %s, partner_id = %s, waiting_since = NULL WHERE user_id = %s",
                        (status, partner_id, user_id)
                    )
                await conn.commit()
    except Exception as e:
        logging.error(f"Error saat update_user_status {user_id}: {e}")

async def find_waiting_partner(user_id, my_profile_data, strict_prefs=True):
    try:
        blocked_ids = await get_blocked_list(user_id)
        excluded_ids = blocked_ids + [user_id]

        if not excluded_ids:
            excluded_placeholders = "''"
        else:
            excluded_placeholders = ','.join(['%s'] * len(excluded_ids))

        my_prefs = my_profile_data
        
        gender_params = [] 
        pref_clauses = [] 
        join_clause = "" 
        join_params = []
        match_history_clause = ""


        if strict_prefs:
            join_clause = """
                LEFT JOIN match_history mh ON
                (mh.user_id_1 = LEAST(u.user_id, %s) AND mh.user_id_2 = GREATEST(u.user_id, %s))
            """
            join_params.extend([user_id, user_id])
            match_history_clause = "AND mh.user_id_1 IS NULL"

            if my_prefs.get('pref_gender') != 'apa_saja':
                pref_clauses.append("u.gender = %s")
                gender_params.append(my_prefs.get('pref_gender'))
            pref_clauses.append("(u.pref_gender = 'apa_saja' OR u.pref_gender = %s)")
            gender_params.append(my_profile_data.get('gender'))

        else:
            pass

        where_clause_str = " AND ".join(pref_clauses) if pref_clauses else "1=1"

        async with g_pool.acquire() as conn:
            async with conn.cursor(aiomysql.cursors.DictCursor) as cursor:

                query = f"""
                    SELECT u.* FROM users u
                    {join_clause}
                    WHERE u.status = 'waiting'
                      AND u.user_id NOT IN ({excluded_placeholders})
                      {match_history_clause}
                      AND {where_clause_str}
                    ORDER BY
                        CASE WHEN u.waiting_since IS NULL THEN 2 ELSE 1 END,
                        u.waiting_since ASC,
                        RAND()
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED
                """

                final_params = tuple(join_params + excluded_ids + gender_params)
                
                await cursor.execute(query, final_params)
                
                return await cursor.fetchone()
    except Exception as e:
        logging.error(f"Error saat find_waiting_partner: {e}")
        return None

async def add_match_history(user_id_1, user_id_2):
    u1 = min(user_id_1, user_id_2)
    u2 = max(user_id_1, user_id_2)
    try:
        async with g_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("INSERT IGNORE INTO match_history (user_id_1, user_id_2) VALUES (%s, %s)", (u1, u2))
            await conn.commit()
    except Exception as e:
        logging.error(f"Error saat add_match_history for {u1}-{u2}: {e}")

async def increment_report_count(user_id):
    try:
        async with g_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("UPDATE users SET report_count = report_count + 1 WHERE user_id = %s", (user_id,))
                await conn.commit()
            logging.info(f"Report count ditambah untuk user {user_id}")
    except Exception as e:
        logging.error(f"Error saat increment_report_count {user_id}: {e}")

async def increment_like_count(user_id):
    try:
        async with g_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("UPDATE users SET like_count = like_count + 1 WHERE user_id = %s", (user_id,))
                await conn.commit()
            logging.info(f"Like count ditambah untuk user {user_id}")
    except Exception as e:
        logging.error(f"Error saat increment_like_count {user_id}: {e}")

async def set_report_count(user_id, count):
    try:
        async with g_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("UPDATE users SET report_count = %s WHERE user_id = %s", (count, user_id))
                await conn.commit()
            logging.info(f"Report count di-set ke {count} untuk user {user_id}")
    except Exception as e:
        logging.error(f"Error saat set_report_count {user_id}: {e}")

async def get_all_user_ids():
    try:
        async with g_pool.acquire() as conn:
            async with conn.cursor(aiomysql.cursors.DictCursor) as cursor:
                await cursor.execute("SELECT user_id FROM users")
                rows = await cursor.fetchall()
                return [row['user_id'] for row in rows]
    except Exception as e:
        logging.error(f"Error saat get_all_user_ids: {e}")
        return []

async def get_all_users_details():
    try:
        async with g_pool.acquire() as conn:
            async with conn.cursor(aiomysql.cursors.DictCursor) as cursor:
                await cursor.execute("SELECT user_id, nama, email, status, report_count FROM users")
                return await cursor.fetchall()
    except Exception as e:
        logging.error(f"Error saat get_all_users_details: {e}")
        return []

async def get_stats():
    stats = {'total': 0, 'chatting': 0, 'waiting': 0}
    try:
        async with g_pool.acquire() as conn:
            async with conn.cursor(aiomysql.cursors.DictCursor) as cursor:
                await cursor.execute("SELECT COUNT(*) AS total FROM users")
                stats['total'] = (await cursor.fetchone())['total']

                await cursor.execute("SELECT status, COUNT(*) AS count FROM users WHERE status IN ('chatting', 'waiting') GROUP BY status")
                rows = await cursor.fetchall()

                for row in rows:
                    if row['status'] == 'chatting':
                        stats['chatting'] = row['count']
                    elif row['status'] == 'waiting':
                        stats['waiting'] = row['count']
    except Exception as e:
        logging.error(f"Error saat get_stats: {e}")
    return stats

async def get_user_by_email(email):
    try:
        async with g_pool.acquire() as conn:
            async with conn.cursor(aiomysql.cursors.DictCursor) as cursor:
                await cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
                return await cursor.fetchone()
    except Exception as e:
        logging.error(f"Error saat get_user_by_email {email}: {e}")
        return None

async def clear_user_field(user_id, field):
    if field != 'email':
        logging.error(f"Attempt to clear invalid field '{field}' for user {user_id}")
        return False
    try:
        async with g_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(f"UPDATE users SET {field} = NULL WHERE user_id = %s", (user_id,))
                await conn.commit()
            logging.info(f"Field {field} di-clear untuk user {user_id}")
            return True
    except Exception as e:
        logging.error(f"Error saat clear_user_field {user_id}: {e}")
        return False

async def create_verification_state(user_id, email, verify_code):
    try:
        async with g_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """
                    INSERT INTO verification_state (user_id, email, verify_code, revoke_code, created_at)
                    VALUES (%s, %s, %s, NULL, NOW())
                    ON DUPLICATE KEY UPDATE
                        email = VALUES(email),
                        verify_code = VALUES(verify_code),
                        revoke_code = NULL,
                        created_at = NOW()
                    """,
                    (user_id, email, verify_code)
                )
                await conn.commit()
    except Exception as e:
        logging.error(f"Error saat create_verification_state for {user_id}: {e}")

async def update_verification_revoke_code(user_id, revoke_code):
    try:
        async with g_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "UPDATE verification_state SET revoke_code = %s, created_at = NOW() WHERE user_id = %s",
                    (revoke_code, user_id)
                )
                await conn.commit()
    except Exception as e:
        logging.error(f"Error saat update_verification_revoke_code for {user_id}: {e}")

async def get_verification_state(user_id):
    try:
        async with g_pool.acquire() as conn:
            async with conn.cursor(aiomysql.cursors.DictCursor) as cursor:
                await cursor.execute("SELECT * FROM verification_state WHERE user_id = %s", (user_id,))
                return await cursor.fetchone()
    except Exception as e:
        logging.error(f"Error saat get_verification_state for {user_id}: {e}")
        return None

async def delete_verification_state(user_id):
    try:
        async with g_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("DELETE FROM verification_state WHERE user_id = %s", (user_id,))
                await conn.commit()
    except Exception as e:
        logging.error(f"Error saat delete_verification_state for {user_id}: {e}")

async def create_pending_media(sender_id, receiver_id, file_id, file_type, caption):
    try:
        async with g_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """INSERT INTO pending_media (sender_id, receiver_id, file_id, file_type, caption)
                        VALUES (%s, %s, %s, %s, %s)""",
                    (sender_id, receiver_id, file_id, file_type, caption)
                )
                await conn.commit()
            return cursor.lastrowid
    except Exception as e:
        logging.error(f"Error saat create_pending_media: {e}")
        return None

async def get_pending_media(media_id):
    try:
        async with g_pool.acquire() as conn:
            async with conn.cursor(aiomysql.cursors.DictCursor) as cursor:
                await cursor.execute("SELECT * FROM pending_media WHERE id = %s", (media_id,))
                return await cursor.fetchone()
    except Exception as e:
        logging.error(f"Error saat get_pending_media: {e}")
        return None

async def delete_pending_media(media_id):
    try:
        async with g_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("DELETE FROM pending_media WHERE id = %s", (media_id,))
            await conn.commit()
    except Exception as e:
        logging.error(f"Error saat delete_pending_media: {e}")

async def block_user(blocker_id, blocked_id):
    try:
        async with g_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                if blocker_id == blocked_id or str(blocked_id) == config.DUMMY_USER_ID:
                    return False

                await cursor.execute(
                    "INSERT IGNORE INTO blocked_users (blocker_id, blocked_id) VALUES (%s, %s)",
                    (blocker_id, blocked_id)
                )
                await conn.commit()
            return True
    except Exception as e:
        logging.error(f"Error saat block_user {blocker_id} -> {blocked_id}: {e}")
        return False

async def get_blocked_list(user_id):
    try:
        async with g_pool.acquire() as conn:
            async with conn.cursor(aiomysql.cursors.DictCursor) as cursor:
                query = """
                    SELECT blocked_id AS id FROM blocked_users WHERE blocker_id = %s
                    UNION
                    SELECT blocker_id AS id FROM blocked_users WHERE blocked_id = %s
                """
                await cursor.execute(query, (user_id, user_id))
                rows = await cursor.fetchall()
            blocked_ids = [row['id'] for row in rows]
            return blocked_ids
    except Exception as e:
        logging.error(f"Error saat get_blocked_list {user_id}: {e}")
        return []

async def get_users_blocked_by(user_id):
    try:
        async with g_pool.acquire() as conn:
            async with conn.cursor(aiomysql.cursors.DictCursor) as cursor:
                query = """
                    SELECT b.blocked_id, u.jurusan, u.prodi
                    FROM blocked_users b
                    JOIN users u ON b.blocked_id = u.user_id
                    WHERE b.blocker_id = %s
                """
                await cursor.execute(query, (user_id,))
                return await cursor.fetchall()
    except Exception as e:
        logging.error(f"Error saat get_users_blocked_by {user_id}: {e}")
        return []

async def unblock_user(blocker_id, blocked_id):
    try:
        async with g_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                query = "DELETE FROM blocked_users WHERE blocker_id = %s AND blocked_id = %s"
                await cursor.execute(query, (blocker_id, blocked_id))
                await conn.commit()
            return True
    except Exception as e:
        logging.error(f"Error saat unblock_user {blocker_id} -> {blocked_id}: {e}")
        return False

async def increment_user_stats(user_id, chat_count=0, message_count=0):
    if chat_count == 0 and message_count == 0:
        return

    try:
        async with g_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                query_parts = []
                params = []

                if chat_count > 0:
                    query_parts.append("total_chats = total_chats + %s")
                    params.append(chat_count)

                if message_count > 0:
                    query_parts.append("total_messages_sent = total_messages_sent + %s")
                    params.append(message_count)

                params.append(user_id)

                query_str_parts = ", ".join(query_parts)
                query = f"UPDATE users SET {query_str_parts} WHERE user_id = %s"

                await cursor.execute(query, tuple(params))
                await conn.commit()
    except Exception as e:
        logging.error(f"Error saat increment_user_stats {user_id}: {e}")

async def cleanup_stale_pending_media(context=None):
    try:
        async with g_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                query = "DELETE FROM pending_media WHERE created_at < (NOW() - INTERVAL 24 HOUR)"
                await cursor.execute(query)
                deleted_count = cursor.rowcount
                await conn.commit()
                
                if deleted_count > 0:
                    logging.info(f"Cleanup job: Menghapus {deleted_count} record pending_media yang kedaluwarsa.")
                else:
                    logging.info("Cleanup job: Tidak ada record pending_media kedaluwarsa untuk dihapus.")
                    
    except Exception as e:
        logging.error(f"Error saat cleanup_stale_pending_media: {e}")

async def set_user_inactive(user_id):
    try:
        async with g_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("UPDATE users SET is_active = FALSE WHERE user_id = %s", (user_id,))
                await conn.commit()
        logging.info(f"User {user_id} ditandai sebagai INACTIVE.")
    except Exception as e:
        logging.error(f"Error saat set_user_inactive {user_id}: {e}")

async def get_active_user_ids():
    try:
        async with g_pool.acquire() as conn:
            async with conn.cursor(aiomysql.cursors.DictCursor) as cursor:
                await cursor.execute("SELECT user_id FROM users WHERE is_active = TRUE")
                rows = await cursor.fetchall()
                return [row['user_id'] for row in rows]
    except Exception as e:
        logging.error(f"Error saat get_active_user_ids: {e}")
        return []

async def close_db():
    global g_pool
    if g_pool:
        g_pool.close()
        await g_pool.wait_closed()
        logging.info("MySQL Connection Pool telah ditutup.")
    else:
        logging.info("Tidak ada koneksi database aktif untuk ditutup.")