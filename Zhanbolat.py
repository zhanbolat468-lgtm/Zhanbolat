
import os
import time
import sqlite3
import threading
import requests
from datetime import datetime, timedelta

import telebot
from telebot import types


# =========================================================
#                    БАПТАУЛАР
# =========================================================

BOT_TOKEN = "8858577930:AAHmq6BIf0xpWywf3vQMTr0IJgo5ui2eCJI"
ADMIN_ID = 8372467283

DB_NAME = "manager_bot.db"


# =========================================================
#                    BOT
# =========================================================

if BOT_TOKEN == "BOT_TOKEN_HERE":
    print("BOT_TOKEN енгізіңіз!")
    raise SystemExit

bot = telebot.TeleBot(
    BOT_TOKEN,
    parse_mode="HTML"
)

db_lock = threading.Lock()

admin_state = {}
broadcast_state = {}


# =========================================================
#                    DATABASE
# =========================================================

def get_db():
    conn = sqlite3.connect(
        DB_NAME,
        check_same_thread=False
    )
    conn.row_factory = sqlite3.Row
    return conn


def init_db():

    with db_lock:

        conn = get_db()

        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT DEFAULT '',
                first_name TEXT DEFAULT '',
                joined_at TEXT DEFAULT '',
                last_seen TEXT DEFAULT '',
                banned INTEGER DEFAULT 0
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT UNIQUE NOT NULL,
                title TEXT DEFAULT '',
                username TEXT DEFAULT '',
                channel_type TEXT NOT NULL,
                invite_link TEXT DEFAULT '',
                added_at TEXT DEFAULT ''
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT DEFAULT ''
            )
        """)

        conn.commit()
        conn.close()


init_db()


# =========================================================
#                    SETTINGS
# =========================================================

def set_setting(key, value):

    with db_lock:

        conn = get_db()

        conn.execute("""
            INSERT INTO settings(key, value)
            VALUES (?, ?)
            ON CONFLICT(key)
            DO UPDATE SET value=excluded.value
        """, (
            key,
            str(value)
        ))

        conn.commit()
        conn.close()


def get_setting(key, default=""):

    with db_lock:

        conn = get_db()

        row = conn.execute("""
            SELECT value
            FROM settings
            WHERE key=?
        """, (key,)).fetchone()

        conn.close()

    if row:
        return row["value"]

    return default


# =========================================================
#                    USERS
# =========================================================

def save_user(user):

    now = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    with db_lock:

        conn = get_db()

        row = conn.execute("""
            SELECT user_id
            FROM users
            WHERE user_id=?
        """, (user.id,)).fetchone()

        if row:

            conn.execute("""
                UPDATE users
                SET username=?,
                    first_name=?,
                    last_seen=?
                WHERE user_id=?
            """, (
                user.username or "",
                user.first_name or "",
                now,
                user.id
            ))

        else:

            conn.execute("""
                INSERT INTO users(
                    user_id,
                    username,
                    first_name,
                    joined_at,
                    last_seen,
                    banned
                )
                VALUES (?, ?, ?, ?, ?, 0)
            """, (
                user.id,
                user.username or "",
                user.first_name or "",
                now,
                now
            ))

        conn.commit()
        conn.close()


def is_banned(user_id):

    with db_lock:

        conn = get_db()

        row = conn.execute("""
            SELECT banned
            FROM users
            WHERE user_id=?
        """, (user_id,)).fetchone()

        conn.close()

    return bool(
        row and row["banned"] == 1
    )


def set_banned(user_id, value):

    with db_lock:

        conn = get_db()

        # Егер user базада жоқ болса, автоматты түрде қосылады
        conn.execute("""
            INSERT INTO users(
                user_id,
                username,
                first_name,
                joined_at,
                last_seen,
                banned
            )
            VALUES (?, '', '', ?, ?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET banned=excluded.banned
        """, (
            user_id,
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            1 if value else 0
        ))

        conn.commit()
        conn.close()


# =========================================================
#                    CHANNELS
# =========================================================

def get_main_channel():

    with db_lock:

        conn = get_db()

        row = conn.execute("""
            SELECT *
            FROM channels
            WHERE channel_type='main'
            ORDER BY id DESC
            LIMIT 1
        """).fetchone()

        conn.close()

    return row


def get_extra_channels():

    with db_lock:

        conn = get_db()

        rows = conn.execute("""
            SELECT *
            FROM channels
            WHERE channel_type='extra'
            ORDER BY id ASC
        """).fetchall()

        conn.close()

    return rows


def get_channel_by_id(channel_id):

    with db_lock:

        conn = get_db()

        row = conn.execute("""
            SELECT *
            FROM channels
            WHERE id=?
        """, (channel_id,)).fetchone()

        conn.close()

    return row


def add_channel(
    chat_id,
    title,
    username,
    channel_type,
    invite_link
):

    with db_lock:

        conn = get_db()

        conn.execute("""
            INSERT INTO channels(
                chat_id,
                title,
                username,
                channel_type,
                invite_link,
                added_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            str(chat_id),
            title,
            username,
            channel_type,
            invite_link,
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        ))

        conn.commit()
        conn.close()


def delete_channel(channel_id):

    with db_lock:

        conn = get_db()

        conn.execute("""
            DELETE FROM channels
            WHERE id=?
        """, (channel_id,))

        conn.commit()
        conn.close()


# =========================================================
#                    ADMIN
# =========================================================

def is_admin(user_id):
    return int(user_id) == int(ADMIN_ID)


# =========================================================
#                    TELEGRAM API
# =========================================================

def telegram_api(method, data=None):

    url = (
        f"https://api.telegram.org/"
        f"bot{BOT_TOKEN}/{method}"
    )

    try:

        response = requests.post(
            url,
            data=data or {},
            timeout=30
        )

        result = response.json()

        if not result.get("ok"):
            print(
                f"[API ERROR] {method}:",
                result
            )

        return result

    except Exception as e:

        print(
            f"[API ERROR] {method}:",
            e
        )

        return {
            "ok": False,
            "description": str(e)
        }


# =========================================================
#                    BOT ADMIN CHECK
# =========================================================

def check_bot_admin(chat_id):

    try:

        me = bot.get_me()

        member = bot.get_chat_member(
            chat_id,
            me.id
        )

        if member.status not in (
            "administrator",
            "creator"
        ):
            return (
                False,
                "Бот бұл арнада админ емес."
            )

        if member.status == "administrator":

            can_invite = getattr(
                member,
                "can_invite_users",
                False
            )

            if not can_invite:

                return (
                    False,
                    "Ботта Invite Users / Join Request құқығы жоқ."
                )

        return True, "OK"

    except Exception as e:

        return False, str(e)


# =========================================================
#              JOIN REQUEST LINK
# =========================================================

def create_join_request_link(chat_id):

    try:

        result = bot.create_chat_invite_link(
            chat_id=chat_id,
            name="Manager Bot",
            creates_join_request=True
        )

        return result.invite_link

    except Exception as e:

        print(
            "Invite link error:",
            e
        )

        return ""


# =========================================================
#                    CHANNEL INPUT
# =========================================================

def normalize_channel(value):

    value = value.strip()

    prefixes = [
        "https://t.me/",
        "http://t.me/",
        "t.me/"
    ]

    for prefix in prefixes:

        if value.startswith(prefix):

            value = value.replace(
                prefix,
                "",
                1
            )

            value = value.split(
                "/"
            )[0]

            if not value.startswith("@"):
                value = "@" + value

            break

    return value


# =========================================================
#              SUBSCRIPTION KEYBOARD
# =========================================================

def subscription_keyboard():

    markup = types.InlineKeyboardMarkup(
        row_width=1
    )

    extras = get_extra_channels()

    # ҚАНША КАНАЛ БАР — СОНША БАТЫРМА
    for index, channel in enumerate(
        extras,
        start=1
    ):

        link = channel["invite_link"]

        if link:

            markup.add(
                types.InlineKeyboardButton(
                    f"📢 Подписаться {index}",
                    url=link
                )
            )

    # Тексеру әрқашан бар
    markup.add(
        types.InlineKeyboardButton(
            "Тексеру ✅️",
            callback_data="check_subscription"
        )
    )

    return markup


# =========================================================
#              SUBSCRIPTION SCREEN
# =========================================================

def send_subscription_screen(
    chat_id,
    error=False
):

    extras = get_extra_channels()

    if error:

        text = (
            "❗️ <b>Сіз арналарға тіркелмедіңіз, "
            "қайта көріңіз ‼️</b>\n\n"
            "Барлық көрсетілген арналарға "
            "заявка жіберіңіз 👇"
        )

    else:

        if extras:

            text = (
                "Сәлеметсізбе каналға кіру үшін "
                "астыдағы арналарымызға тіркеліп кетіңіз!\n\n"
                "Арналарға заявка жіберіңіз 👇"
            )

        else:

            text = (
                "Сәлеметсізбе!\n\n"
                "Қазіргі уақытта қосылуға міндетті "
                "арна жоқ."
            )

    bot.send_message(
        chat_id,
        text,
        reply_markup=subscription_keyboard()
    )


# =========================================================
#                    START
# =========================================================

@bot.message_handler(
    commands=["start"]
)
def start_command(message):

    save_user(
        message.from_user
    )

    if is_banned(
        message.from_user.id
    ):

        bot.send_message(
            message.chat.id,
            "🚫 <b>Сіз боттан бұғатталғансыз.</b>"
        )

        return

    send_subscription_screen(
        message.chat.id
    )


# =========================================================
#          PENDING JOIN REQUEST CHECK
# =========================================================

def has_pending_join_request(
    chat_id,
    user_id
):

    result = telegram_api(
        "getChatJoinRequests",
        {
            "chat_id": chat_id,
            "limit": 100
        }
    )

    if not result.get("ok"):

        print(
            "getChatJoinRequests error:",
            result
        )

        return False

    request_list = result.get(
        "result",
        []
    )

    for request in request_list:

        user = request.get(
            "user",
            {}
        )

        if int(
            user.get("id", 0)
        ) == int(user_id):

            return True

    return False


# =========================================================
#              CHECK ALL EXTRA CHANNELS
# =========================================================

def check_all_extra_requests(
    user_id
):

    extras = get_extra_channels()

    # ЕШҚАНДАЙ КАНАЛ ЖОҚ БОЛСА
    # ТЕКСЕРУДІ АВТОМАТТЫ ТҮРДЕ ӨТКІЗЕМІЗ
    if len(extras) == 0:

        return (
            True,
            None
        )

    # БАР КАНАЛДАРДЫҢ ҒАНА REQUEST-ІН ТЕКСЕРЕДІ
    for channel in extras:

        if not has_pending_join_request(
            channel["chat_id"],
            user_id
        ):

            return (
                False,
                channel
            )

    return (
        True,
        None
    )


# =========================================================
#              APPROVE MAIN REQUEST
# =========================================================

def approve_main_request(
    user_id
):

    main = get_main_channel()

    if not main:

        return (
            False,
            "Басты арна қосылмаған."
        )

    result = telegram_api(
        "approveChatJoinRequest",
        {
            "chat_id": main["chat_id"],
            "user_id": user_id
        }
    )

    if result.get("ok"):

        return (
            True,
            None
        )

    return (
        False,
        result.get(
            "description",
            "Белгісіз қате"
        )
    )


# =========================================================
#                    CALLBACK
# =========================================================

@bot.callback_query_handler(
    func=lambda call: True
)
def callback_handler(call):

    user_id = call.from_user.id
    data = call.data

    # =====================================================
    # BAN
    # =====================================================

    if is_banned(user_id):

        bot.answer_callback_query(
            call.id,
            "🚫 Сіз бұғатталғансыз.",
            show_alert=True
        )

        return

    # =====================================================
    # CHECK
    # =====================================================

    if data == "check_subscription":

        bot.answer_callback_query(
            call.id,
            "🔎 Тексерілуде..."
        )

        ok, channel = check_all_extra_requests(
            user_id
        )

        if not ok:

            send_subscription_screen(
                user_id,
                error=True
            )

            return

        approved, error = approve_main_request(
            user_id
        )

        if approved:

            bot.send_message(
                user_id,
                "✅ <b>Дайын!</b>\n\n"
                "Сіздің Басты арнадағы "
                "заявкаңыз қабылданды."
            )

        else:

            bot.send_message(
                user_id,
                "⚠️ <b>Басты арнадағы заявка "
                "қабылданбады.</b>\n\n"
                "Басты арнаға join request "
                "жібергеніңізге көз жеткізіңіз."
            )

        return

    # =====================================================
    # ADMIN
    # =====================================================

    if data == "admin_panel":

        if is_admin(user_id):
            show_admin_panel(user_id)

        return

    if data == "admin_channels":

        if is_admin(user_id):
            show_channels_panel(user_id)

        return

    if data == "admin_users":

        if is_admin(user_id):
            show_users_panel(user_id)

        return

    if data == "admin_stats":

        if is_admin(user_id):
            show_stats(user_id)

        return

    if data == "admin_bans":

        if is_admin(user_id):
            show_bans_panel(user_id)

        return

    # =====================================================
    # BROADCAST
    # =====================================================

    if data == "admin_broadcast":

        if not is_admin(user_id):
            return

        broadcast_state[user_id] = True

        bot.send_message(
            user_id,
            "📢 <b>РАССЫЛМА</b>\n\n"
            "Жіберетін хабарламаны жіберіңіз.\n\n"
            "Мәтін, фото, видео, файл және "
            "Premium Emoji қолдануға болады.\n\n"
            "Тоқтату үшін: /cancel"
        )

        return

    # =====================================================
    # ADD MAIN
    # =====================================================

    if data == "add_main":

        if not is_admin(user_id):
            return

        admin_state[user_id] = {
            "action": "add_main"
        }

        bot.send_message(
            user_id,
            "🏆 <b>БАСТЫ АРНА ҚОСУ</b>\n\n"
            "Арнаның @username немесе ID-сін жіберіңіз.\n\n"
            "Мысалы:\n"
            "<code>@mychannel</code>\n"
            "<code>-1001234567890</code>"
        )

        return

    # =====================================================
    # DELETE MAIN
    # =====================================================

    if data == "delete_main":

        if not is_admin(user_id):
            return

        main = get_main_channel()

        if not main:

            bot.answer_callback_query(
                call.id,
                "Басты арна жоқ.",
                show_alert=True
            )

            return

        delete_channel(
            main["id"]
        )

        bot.send_message(
            user_id,
            "🗑 <b>Басты арна өшірілді.</b>"
        )

        return

    # =====================================================
    # ADD EXTRA
    # =====================================================

    if data == "add_extra":

        if not is_admin(user_id):
            return

        # 3-тен артық қоспайды
        extras = get_extra_channels()

        if len(extras) >= 3:

            bot.answer_callback_query(
                call.id,
                "⚠️ Максимум 3 қосымша арна.",
                show_alert=True
            )

            return

        admin_state[user_id] = {
            "action": "add_extra"
        }

        bot.send_message(
            user_id,
            "📢 <b>ҚОСЫМША АРНА ҚОСУ</b>\n\n"
            "Арнаның @username немесе ID-сін жіберіңіз."
        )

        return

    # =====================================================
    # DELETE EXTRA
    # =====================================================

    if data.startswith(
        "delete_extra:"
    ):

        if not is_admin(user_id):
            return

        try:

            channel_id = int(
                data.split(
                    ":",
                    1
                )[1]
            )

        except Exception:

            bot.answer_callback_query(
                call.id,
                "Қате.",
                show_alert=True
            )

            return

        channel = get_channel_by_id(
            channel_id
        )

        if not channel:

            bot.answer_callback_query(
                call.id,
                "Канал табылмады.",
                show_alert=True
            )

            return

        delete_channel(
            channel_id
        )

        bot.answer_callback_query(
            call.id,
            "✅ Канал өшірілді."
        )

        show_channels_panel(
            user_id
        )

        return

    # =====================================================
    # SEARCH USER
    # =====================================================

    if data == "search_user":

        if not is_admin(user_id):
            return

        admin_state[user_id] = {
            "action": "search_user"
        }

        bot.send_message(
            user_id,
            "🔎 <b>ПАЙДАЛАНУШЫ ІЗДЕУ</b>\n\n"
            "Telegram ID жіберіңіз."
        )

        return

    # =====================================================
    # UNBAN
    # =====================================================

    if data.startswith(
        "unban:"
    ):

        if not is_admin(user_id):
            return

        try:

            target_id = int(
                data.split(
                    ":",
                    1
                )[1]
            )

        except Exception:

            return

        set_banned(
            target_id,
            False
        )

        bot.answer_callback_query(
            call.id,
            "✅ Unban жасалды."
        )

        show_bans_panel(
            user_id
        )

        return

    # =====================================================
    # BACK
    # =====================================================

    if data == "admin_back":

        if not is_admin(user_id):
            return

        show_admin_panel(
            user_id
        )

        return


# =========================================================
#                    ADMIN PANEL
# =========================================================

def show_admin_panel(
    chat_id
):

    text = (
        "👑 <b>АДМИН ПАНЕЛІ</b>\n\n"
        "🤖 <b>Manager Bot</b>\n"
        "Басқару бөлімін таңдаңыз:"
    )

    markup = types.InlineKeyboardMarkup(
        row_width=2
    )

    markup.add(

        types.InlineKeyboardButton(
            "🏆 Каналдар",
            callback_data="admin_channels"
        ),

        types.InlineKeyboardButton(
            "👥 Пользователи",
            callback_data="admin_users"
        ),

        types.InlineKeyboardButton(
            "📊 Статистика",
            callback_data="admin_stats"
        ),

        types.InlineKeyboardButton(
            "🚫 Блокировки",
            callback_data="admin_bans"
        ),

        types.InlineKeyboardButton(
            "📢 Рассылка",
            callback_data="admin_broadcast"
        )
    )

    bot.send_message(
        chat_id,
        text,
        reply_markup=markup
    )


# =========================================================
#                    CHANNEL PANEL
# =========================================================

def show_channels_panel(
    chat_id
):

    main = get_main_channel()
    extras = get_extra_channels()

    text = (
        "🏆 <b>КАНАЛДАР</b>\n\n"
    )

    # =====================================================
    # MAIN
    # =====================================================

    if main:

        ok, reason = check_bot_admin(
            main["chat_id"]
        )

        status = (
            "✅ Бот админ"
            if ok
            else "❌ Бот админ емес"
        )

        title = (
            main["title"]
            or main["chat_id"]
        )

        text += (
            "🌟 <b>Басты арна</b>\n"
            f"├─ {title}\n"
            f"└─ {status}\n\n"
        )

    else:

        text += (
            "🌟 <b>Басты арна</b>\n"
            "└─ ❌ Қосылмаған\n\n"
        )

    # =====================================================
    # EXTRA
    # =====================================================

    if extras:

        for index, channel in enumerate(
            extras,
            start=1
        ):

            ok, reason = check_bot_admin(
                channel["chat_id"]
            )

            status = (
                "✅ Бот админ"
                if ok
                else "❌ Бот админ емес"
            )

            title = (
                channel["title"]
                or channel["chat_id"]
            )

            text += (
                f"📢 <b>Қосымша арна {index}</b>\n"
                f"├─ {title}\n"
                f"└─ {status}\n\n"
            )

    else:

        text += (
            "📢 <b>Қосымша арналар</b>\n"
            "└─ Қазір ешқандай арна жоқ.\n\n"
        )

    # =====================================================
    # BUTTONS
    # =====================================================

    markup = types.InlineKeyboardMarkup(
        row_width=2
    )

    markup.add(

        types.InlineKeyboardButton(
            "➕ Басты арна",
            callback_data="add_main"
        ),

        types.InlineKeyboardButton(
            "🗑 Басты арна",
            callback_data="delete_main"
        )
    )

    if len(extras) < 3:

        markup.add(
            types.InlineKeyboardButton(
                "➕ Қосымша арна",
                callback_data="add_extra"
            )
        )

    # Әр нақты қосылған каналға delete
    for index, channel in enumerate(
        extras,
        start=1
    ):

        markup.add(
            types.InlineKeyboardButton(
                f"🗑 Қосымша {index}",
                callback_data=(
                    f"delete_extra:{channel['id']}"
                )
            )
        )

    markup.add(
        types.InlineKeyboardButton(
            "🔙 Артқа",
            callback_data="admin_back"
        )
    )

    bot.send_message(
        chat_id,
        text,
        reply_markup=markup
    )


# =========================================================
#                    USERS PANEL
# =========================================================

def show_users_panel(
    chat_id
):

    with db_lock:

        conn = get_db()

        total = conn.execute(
            "SELECT COUNT(*) FROM users"
        ).fetchone()[0]

        banned = conn.execute(
            """
            SELECT COUNT(*)
            FROM users
            WHERE banned=1
            """
        ).fetchone()[0]

        conn.close()

    text = (
        "👥 <b>ПАЙДАЛАНУШЫЛАР</b>\n\n"
        f"👤 Барлығы: <b>{total}</b>\n"
        f"🚫 Бан: <b>{banned}</b>\n\n"
        "Пайдаланушыны ID арқылы іздеуге болады."
    )

    markup = types.InlineKeyboardMarkup()

    markup.add(
        types.InlineKeyboardButton(
            "🔎 ID бойынша іздеу",
            callback_data="search_user"
        )
    )

    markup.add(
        types.InlineKeyboardButton(
            "🔙 Артқа",
            callback_data="admin_back"
        )
    )

    bot.send_message(
        chat_id,
        text,
        reply_markup=markup
    )


# =========================================================
#                    USER SEARCH
# =========================================================

def show_user_info(
    admin_id,
    target_id
):

    with db_lock:

        conn = get_db()

        row = conn.execute("""
            SELECT *
            FROM users
            WHERE user_id=?
        """, (target_id,)).fetchone()

        conn.close()

    if not row:

        bot.send_message(
            admin_id,
            "❌ <b>Пайдаланушы табылмады.</b>"
        )

        return

    username = row["username"]

    if username:
        username_text = "@" + username
    else:
        username_text = "жоқ"

    status = (
        "🚫 Заблокирован"
        if row["banned"]
        else "🟢 Белсенді"
    )

    text = (
        "👤 <b>ПАЙДАЛАНУШЫ</b>\n\n"
        f"🆔 ID: <code>{row['user_id']}</code>\n"
        f"👤 Аты: <b>{row['first_name'] or 'Жоқ'}</b>\n"
        f"🔗 Username: <b>{username_text}</b>\n"
        f"📅 Кірген уақыты: <b>{row['joined_at']}</b>\n"
        f"🕐 Соңғы әрекет: <b>{row['last_seen']}</b>\n"
        f"📌 Статус: <b>{status}</b>"
    )

    markup = types.InlineKeyboardMarkup(
        row_width=2
    )

    if row["banned"]:

        markup.add(
            types.InlineKeyboardButton(
                "✅ Unban",
                callback_data=(
                    f"unban:{target_id}"
                )
            )
        )

    else:

        markup.add(
            types.InlineKeyboardButton(
                "🚫 Ban",
                callback_data=(
                    f"ban_user:{target_id}"
                )
            )
        )

    bot.send_message(
        admin_id,
        text,
        reply_markup=markup
    )


# =========================================================
#                    STATISTICS
# =========================================================

def show_stats(
    chat_id
):

    now = datetime.now()

    today = now.strftime(
        "%Y-%m-%d"
    )

    week = (
        now - timedelta(days=7)
    ).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    with db_lock:

        conn = get_db()

        total = conn.execute(
            "SELECT COUNT(*) FROM users"
        ).fetchone()[0]

        banned = conn.execute(
            """
            SELECT COUNT(*)
            FROM users
            WHERE banned=1
            """
        ).fetchone()[0]

        today_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM users
            WHERE joined_at LIKE ?
            """,
            (
                today + "%",
            )
        ).fetchone()[0]

        week_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM users
            WHERE joined_at >= ?
            """,
            (
                week,
            )
        ).fetchone()[0]

        conn.close()

    active = total - banned

    text = (
        "📊 <b>СТАТИСТИКА</b>\n\n"
        f"👥 Барлық қолданушы: <b>{total}</b>\n"
        f"🟢 Белсенді: <b>{active}</b>\n"
        f"🚫 Бан: <b>{banned}</b>\n\n"
        f"📅 Бүгін: <b>{today_count}</b>\n"
        f"🗓 Соңғы 7 күн: <b>{week_count}</b>"
    )

    markup = types.InlineKeyboardMarkup()

    markup.add(
        types.InlineKeyboardButton(
            "🔙 Артқа",
            callback_data="admin_back"
        )
    )

    bot.send_message(
        chat_id,
        text,
        reply_markup=markup
    )


# =========================================================
#                    BANS PANEL
# =========================================================

def show_bans_panel(
    chat_id
):

    with db_lock:

        conn = get_db()

        rows = conn.execute("""
            SELECT
                user_id,
                username,
                first_name
            FROM users
            WHERE banned=1
            ORDER BY user_id DESC
            LIMIT 50
        """).fetchall()

        conn.close()

    text = (
        "🚫 <b>БЛОКИРОВКАЛАР</b>\n\n"
    )

    if not rows:

        text += (
            "Қазір банға салынған "
            "пайдаланушы жоқ."
        )

    else:

        for row in rows:

            text += (
                f"👤 {row['first_name'] or 'Без имени'}\n"
                f"🆔 <code>{row['user_id']}</code>\n\n"
            )

    markup = types.InlineKeyboardMarkup(
        row_width=1
    )

    for row in rows:

        markup.add(
            types.InlineKeyboardButton(
                f"✅ Unban {row['user_id']}",
                callback_data=(
                    f"unban:{row['user_id']}"
                )
            )
        )

    markup.add(
        types.InlineKeyboardButton(
            "🔙 Артқа",
            callback_data="admin_back"
        )
    )

    bot.send_message(
        chat_id,
        text,
        reply_markup=markup
    )


# =========================================================
#                    ADMIN MESSAGE
# =========================================================

@bot.message_handler(
    content_types=[
        "text",
        "photo",
        "video",
        "document",
        "audio",
        "voice",
        "animation",
        "sticker"
    ],
    func=lambda message: (
        message.from_user.id == ADMIN_ID
        and (
            message.from_user.id in admin_state
            or message.from_user.id in broadcast_state
        )
    )
)
def admin_message_handler(message):

    user_id = message.from_user.id

    # =====================================================
    # CANCEL
    # =====================================================

    if (
        message.content_type == "text"
        and message.text == "/cancel"
    ):

        admin_state.pop(
            user_id,
            None
        )

        broadcast_state.pop(
            user_id,
            None
        )

        bot.send_message(
            user_id,
            "❌ <b>Әрекет тоқтатылды.</b>"
        )

        return

    # =====================================================
    # BROADCAST
    # =====================================================

    if user_id in broadcast_state:

        broadcast_state.pop(
            user_id,
            None
        )

        start_broadcast(
            message
        )

        return

    # =====================================================
    # STATE
    # =====================================================

    state = admin_state.get(
        user_id
    )

    if not state:
        return

    action = state.get(
        "action"
    )

    # =====================================================
    # SEARCH USER
    # =====================================================

    if action == "search_user":

        if message.content_type != "text":

            bot.send_message(
                user_id,
                "❌ Telegram ID жіберіңіз."
            )

            return

        try:

            target_id = int(
                message.text.strip()
            )

        except ValueError:

            bot.send_message(
                user_id,
                "❌ ID дұрыс емес."
            )

            return

        admin_state.pop(
            user_id,
            None
        )

        show_user_info(
            user_id,
            target_id
        )

        return

    # =====================================================
    # ADD CHANNEL
    # =====================================================

    if action in (
        "add_main",
        "add_extra"
    ):

        if message.content_type != "text":

            bot.send_message(
                user_id,
                "⚠️ @username немесе ID жіберіңіз."
            )

            return

        value = normalize_channel(
            message.text
        )

        try:

            chat = bot.get_chat(
                value
            )

        except Exception as e:

            print(
                "get_chat:",
                e
            )

            bot.send_message(
                user_id,
                "❌ <b>Канал табылмады.</b>\n\n"
                "Мысалы:\n"
                "<code>@channel</code>\n"
                "<code>-1001234567890</code>"
            )

            return

        chat_id = chat.id
        title = chat.title or ""
        username = chat.username or ""

        # =================================================
        # BOT ADMIN
        # =================================================

        bot_ok, reason = check_bot_admin(
            chat_id
        )

        if not bot_ok:

            bot.send_message(
                user_id,
                "❌ <b>Канал қосылмады.</b>\n\n"
                f"<code>{reason}</code>\n\n"
                "Ботты каналға админ етіңіз және "
                "Join Request басқару құқығын беріңіз."
            )

            return

        # =================================================
        # MAIN
        # =================================================

        if action == "add_main":

            old_main = get_main_channel()

            if old_main:

                delete_channel(
                    old_main["id"]
                )

            invite_link = create_join_request_link(
                chat_id
            )

            if not invite_link:

                bot.send_message(
                    user_id,
                    "❌ Join Request сілтемесін жасау мүмкін болмады."
                )

                return

            try:

                add_channel(
                    chat_id,
                    title,
                    username,
                    "main",
                    invite_link
                )

            except Exception as e:

                bot.send_message(
                    user_id,
                    f"❌ База қатесі:\n<code>{e}</code>"
                )

                return

            admin_state.pop(
                user_id,
                None
            )

            bot.send_message(
                user_id,
                "✅ <b>БАСТЫ АРНА ҚОСЫЛДЫ</b>\n\n"
                f"🏆 {title}\n"
                f"🆔 <code>{chat_id}</code>\n\n"
                f"🔗 {invite_link}"
            )

            return

        # =================================================
        # EXTRA
        # =================================================

        if action == "add_extra":

            extras = get_extra_channels()

            if len(extras) >= 3:

                admin_state.pop(
                    user_id,
                    None
                )

                bot.send_message(
                    user_id,
                    "⚠️ Максимум 3 қосымша арна."
                )

                return

            # Duplicate
            for channel in extras:

                if str(
                    channel["chat_id"]
                ) == str(chat_id):

                    bot.send_message(
                        user_id,
                        "⚠️ Бұл канал бұрыннан қосылған."
                    )

                    return

            invite_link = create_join_request_link(
                chat_id
            )

            if not invite_link:

                bot.send_message(
                    user_id,
                    "❌ Join Request сілтемесін жасау мүмкін болмады."
                )

                return

            try:

                add_channel(
                    chat_id,
                    title,
                    username,
                    "extra",
                    invite_link
                )

            except Exception as e:

                bot.send_message(
                    user_id,
                    f"❌ База қатесі:\n<code>{e}</code>"
                )

                return

            admin_state.pop(
                user_id,
                None
            )

            number = len(extras) + 1

            bot.send_message(
                user_id,
                "✅ <b>ҚОСЫМША АРНА ҚОСЫЛДЫ</b>\n\n"
                f"📢 Арна: {title}\n"
                f"🔢 Нөмірі: {number}\n"
                f"🆔 <code>{chat_id}</code>\n\n"
                f"🔗 {invite_link}"
            )

            return

    # =====================================================
    # UNKNOWN
    # =====================================================

    admin_state.pop(
        user_id,
        None
    )


# =========================================================
#                    BAN CALLBACK
# =========================================================

# Негізгі callback handler-ден бөлек
# ban_user callback-ін өңдейді

@bot.callback_query_handler(
    func=lambda call: call.data.startswith(
        "ban_user:"
    )
)
def ban_user_callback(call):

    if not is_admin(
        call.from_user.id
    ):
        return

    try:

        target_id = int(
            call.data.split(
                ":",
                1
            )[1]
        )

    except Exception:

        return

    set_banned(
        target_id,
        True
    )

    bot.answer_callback_query(
        call.id,
        "🚫 Бан жасалды."
    )

    show_user_info(
        call.from_user.id,
        target_id
    )


# =========================================================
#                    /ADMIN
# =========================================================

@bot.message_handler(
    commands=["admin"]
)
def admin_command(message):

    if not is_admin(
        message.from_user.id
    ):

        bot.send_message(
            message.chat.id,
            "🚫 <b>Бұл бөлім тек админге арналған.</b>"
        )

        return

    show_admin_panel(
        message.chat.id
    )


# =========================================================
#                    /BAN
# =========================================================

@bot.message_handler(
    commands=["ban"]
)
def ban_command(message):

    if not is_admin(
        message.from_user.id
    ):
        return

    parts = message.text.split()

    if len(parts) != 2:

        bot.send_message(
            message.chat.id,
            "Қолдану:\n"
            "<code>/ban USER_ID</code>"
        )

        return

    try:

        target_id = int(
            parts[1]
        )

    except ValueError:

        bot.send_message(
            message.chat.id,
            "❌ ID дұрыс емес."
        )

        return

    set_banned(
        target_id,
        True
    )

    bot.send_message(
        message.chat.id,
        f"🚫 <b>{target_id}</b> банға жіберілді."
    )


# =========================================================
#                    /UNBAN
# =========================================================

@bot.message_handler(
    commands=["unban"]
)
def unban_command(message):

    if not is_admin(
        message.from_user.id
    ):
        return

    parts = message.text.split()

    if len(parts) != 2:

        bot.send_message(
            message.chat.id,
            "Қолдану:\n"
            "<code>/unban USER_ID</code>"
        )

        return

    try:

        target_id = int(
            parts[1]
        )

    except ValueError:

        bot.send_message(
            message.chat.id,
            "❌ ID дұрыс емес."
        )

        return

    set_banned(
        target_id,
        False
    )

    bot.send_message(
        message.chat.id,
        f"✅ <b>{target_id}</b> баннан шығарылды."
    )


# =========================================================
#                    BROADCAST
# =========================================================

def start_broadcast(
    source_message
):

    with db_lock:

        conn = get_db()

        rows = conn.execute("""
            SELECT user_id
            FROM users
            WHERE banned=0
        """).fetchall()

        conn.close()

    total = len(rows)

    bot.send_message(
        ADMIN_ID,
        "📢 <b>РАССЫЛМА БАСТАЛДЫ</b>\n\n"
        f"👥 Алушы: <b>{total}</b>"
    )

    success = 0
    failed = 0

    for row in rows:

        user_id = row["user_id"]

        try:

            bot.copy_message(
                chat_id=user_id,
                from_chat_id=source_message.chat.id,
                message_id=source_message.message_id
            )

            success += 1

        except Exception as e:

            failed += 1

            print(
                f"Broadcast {user_id}:",
                e
            )

        time.sleep(0.05)

    bot.send_message(
        ADMIN_ID,
        "✅ <b>РАССЫЛМА АЯҚТАЛДЫ</b>\n\n"
        f"📨 Жеткізілді: <b>{success}</b>\n"
        f"❌ Жеткізілмеді: <b>{failed}</b>"
    )


# =========================================================
#                    JOIN REQUEST
# =========================================================

@bot.chat_join_request_handler()
def join_request_handler(
    request
):

    try:

        print(
            "[JOIN REQUEST]",
            request.from_user.id,
            request.chat.id
        )

    except Exception as e:

        print(
            "Join request error:",
            e
        )


# =========================================================
#                    RUN
# =========================================================

def run_bot():

    print("")
    print("========================================")
    print("       MANAGER BOT STARTED")
    print("========================================")
    print(
        "ADMIN_ID:",
        ADMIN_ID
    )
    print("========================================")
    print("")

    while True:

        try:

            bot.infinity_polling(
                skip_pending=True,
                timeout=60,
                long_polling_timeout=60,
                allowed_updates=[
                    "message",
                    "callback_query",
                    "chat_join_request"
                ]
            )

        except Exception as e:

            print("")
            print("POLLING ERROR:")
            print(e)
            print("")
            print(
                "5 секундтан кейін қайта іске қосылады..."
            )

            time.sleep(5)


# =========================================================
#                    START BOT
# =========================================================

if __name__ == "__main__":

    run_bot()
