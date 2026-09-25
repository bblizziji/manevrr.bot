import telebot
from telebot import types
import sqlite3
from datetime import datetime, timedelta, timezone
import logging
import time
import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

user_data = {}

bot = telebot.TeleBot("8889296379:AAF0B3-SGaOQuvQuOzMsjqKyfMZ9x3UAX_o")

ADMINS = [819284226, 8837073941, 576205495]


def get_current_hour_msk():
    """Возвращает текущий час по МСК (UTC+3)"""
    now_utc = datetime.now(timezone.utc)
    now_msk = now_utc + timedelta(hours=3)
    return now_msk.hour


def get_current_datetime_msk():
    """Возвращает текущую дату и время по МСК"""
    now_utc = datetime.now(timezone.utc)
    now_msk = now_utc + timedelta(hours=3)
    return now_msk


def get_available_dates():
    dates = []
    now_msk = get_current_datetime_msk()
    current_hour = now_msk.hour

    if current_hour < 23:
        dates.append(("date_today", "Сегодня"))

    days_ru = {
        'Monday': 'ПН', 'Tuesday': 'ВТ', 'Wednesday': 'СР',
        'Thursday': 'ЧТ', 'Friday': 'ПТ', 'Saturday': 'СБ', 'Sunday': 'ВС'
    }

    for i in range(1, 8):
        future_date = now_msk + timedelta(days=i)
        date_str = future_date.strftime("%d.%m.%Y")
        day_name = future_date.strftime("%A")
        if i == 1:
            label = f"{date_str} (Завтра)"
        else:
            label = f"{date_str} ({days_ru.get(day_name, day_name)})"
        dates.append((f"date_{i}", label))

    return dates


def init_db():
    conn = sqlite3.connect("bookings.db")
    cur = conn.cursor()

    cur.execute("PRAGMA table_info(bookings)")
    columns = [column[1] for column in cur.fetchall()]

    cur.execute('''CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        phone TEXT,
        booking_date TEXT,
        booking_time_start TEXT,
        booking_time_end TEXT,
        table_type TEXT,
        created_at TEXT,
        status TEXT DEFAULT 'active'
    )''')

    if 'booking_time_start' not in columns:
        cur.execute('ALTER TABLE bookings ADD COLUMN booking_time_start TEXT')
    if 'booking_time_end' not in columns:
        cur.execute('ALTER TABLE bookings ADD COLUMN booking_time_end TEXT')
    if 'table_type' not in columns:
        cur.execute('ALTER TABLE bookings ADD COLUMN table_type TEXT')
    if 'status' not in columns:
        cur.execute('ALTER TABLE bookings ADD COLUMN status TEXT DEFAULT "active"')

    conn.commit()
    cur.close()
    conn.close()


init_db()


def add_booking(user_id, username, first_name, last_name, phone, booking_date, booking_time_start, booking_time_end,
                table_type):
    conn = sqlite3.connect('bookings.db')
    cursor = conn.cursor()
    cursor.execute('''INSERT INTO bookings (user_id, username, first_name, last_name, phone, booking_date, booking_time_start, booking_time_end, table_type, created_at, status) 
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                   (user_id, username, first_name, last_name, phone, booking_date, booking_time_start, booking_time_end,
                    table_type,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'active'))
    conn.commit()
    conn.close()


def cancel_booking(booking_id, user_id):
    conn = sqlite3.connect('bookings.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE bookings SET status = "cancelled" WHERE id = ? AND user_id = ?', (booking_id, user_id))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0


def clear_user_bookings(user_id):
    """Удаляет все брони пользователя из БД. Возвращает число удалённых записей."""
    conn = sqlite3.connect('bookings.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM bookings WHERE user_id = ?', (user_id,))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected


def get_booked_times(booking_date, table_type):
    """Возвращает занятые интервалы на дату ТОЛЬКО для указанного типа стола/комнаты"""
    conn = sqlite3.connect('bookings.db')
    cursor = conn.cursor()
    try:
        cursor.execute(
            'SELECT booking_time_start, booking_time_end FROM bookings '
            'WHERE booking_date = ? AND table_type = ? AND status = "active"',
            (booking_date, table_type))
        booked_times = cursor.fetchall()
    except Exception as e:
        logger.error(f"get_booked_times error: {e}")
        booked_times = []
    conn.close()
    return booked_times


def get_active_bookings():
    """Возвращает все АКТИВНЫЕ брони всех пользователей, отсортированные по дате/времени"""
    conn = sqlite3.connect('bookings.db')
    cursor = conn.cursor()
    try:
        cursor.execute(
            'SELECT id, user_id, username, first_name, phone, booking_date, '
            'booking_time_start, booking_time_end, table_type, created_at '
            'FROM bookings WHERE status = "active" '
            'ORDER BY booking_date, booking_time_start')
        bookings = cursor.fetchall()
    except Exception as e:
        logger.error(f"get_active_bookings error: {e}")
        bookings = []
    conn.close()
    return bookings


def safe_delete_message(chat_id, message_id):
    try:
        if chat_id and message_id:
            bot.delete_message(chat_id, message_id)
            return True
    except:
        return False
    return False


def notify_admins(message_text):
    for admin_id in ADMINS:
        try:
            bot.send_message(admin_id, message_text)
        except Exception as e:
            logger.error(f"Не удалось отправить админу {admin_id}: {e}")


def get_type_emoji(table_type):
    """Возвращает эмодзи для типа стола/комнаты"""
    if table_type == "Русский бильярд":
        return "🇷🇺"
    elif table_type == "Пул":
        return "🎱"
    elif table_type == "Комната для настольных игр":
        return "🎲"
    return "🎯"


def get_day_label(booking_date):
    """Возвращает текстовую подпись дня брони (сегодня/завтра/послезавтра/через N дней)"""
    try:
        now_msk = get_current_datetime_msk()
        booking_dt = datetime.strptime(booking_date, "%d.%m.%Y").date()
        today_dt = now_msk.date()
        days_diff = (booking_dt - today_dt).days

        if days_diff == 0:
            return "сегодня"
        elif days_diff == 1:
            return "завтра"
        elif days_diff == 2:
            return "послезавтра"
        elif days_diff == 3:
            return "через 3 дня"
        else:
            return f"через {days_diff} дней"
    except Exception as e:
        logger.error(f"Ошибка определения дня брони: {e}")
        return ""


def complete_booking(user_id, name, call=None):
    user_data_item = user_data.get(user_id, {})
    booking_date = user_data_item.get('booking_date')
    booking_time_start = user_data_item.get('booking_time_start')
    booking_time_end = user_data_item.get('booking_time_end')
    table_type = user_data_item.get('table_type')
    phone = user_data_item.get('phone')

    if not booking_date or not booking_time_start or not booking_time_end or not table_type or not phone:
        bot.send_message(user_id, "❌ Ошибка! Попробуйте начать заново.")
        return

    # Проверка пересечения с уже существующими бронями того же типа стола/комнаты
    try:
        start_h = int(booking_time_start.split(":")[0])
        end_h = int(booking_time_end.split(":")[0])
        if end_h == 0:
            end_h = 24

        for bs, be in get_booked_times(booking_date, table_type):
            try:
                bs_h = int(bs.split(":")[0])
                be_h = int(be.split(":")[0])
                if be_h == 0:
                    be_h = 24
                if start_h < be_h and end_h > bs_h:
                    bot.send_message(user_id, "❌ Это время уже занято. Выберите другое.")
                    return
            except Exception:
                continue
    except Exception as e:
        logger.error(f"Ошибка проверки пересечения: {e}")

    add_booking(user_id=user_id, username=call.from_user.username if call else None, first_name=name, last_name="",
                phone=phone, booking_date=booking_date, booking_time_start=booking_time_start,
                booking_time_end=booking_time_end, table_type=table_type)

    day_label = get_day_label(booking_date)
    date_with_label = f"{booking_date} ({day_label})" if day_label else booking_date

    type_emoji = get_type_emoji(table_type)
    admin_message = (
        f"🆕 НОВАЯ БРОНЬ!\n\n"
        f"👤 Имя: {name}\n"
        f"📱 Телефон: {phone}\n"
        f"📱 Username: @{call.from_user.username if call and call.from_user.username else 'нет'}\n"
        f"📅 Дата: {date_with_label}\n"
        f"🕐 Время: {booking_time_start} - {booking_time_end}\n"
        f"{type_emoji} {table_type}"
    )
    notify_admins(admin_message)

    bot.send_message(user_id,
                     f"✅ Бронь подтверждена!\n\n"
                     f"📅 Дата: {booking_date}\n"
                     f"🕐 Время: {booking_time_start} - {booking_time_end}\n"
                     f"{type_emoji} {table_type}\n"
                     f"👤 Имя: {name}\n"
                     f"📱 Телефон: {phone}\n\n"
                     f"Скоро с вами свяжется менеджер.")
    user_data.pop(user_id, None)


def show_main_menu(chat_id, user_id=None):
    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton("💰 Тарифы", callback_data="tariffs")
    btn2 = types.InlineKeyboardButton("📅 Забронировать стол", callback_data="bron")
    btn3 = types.InlineKeyboardButton("🎲 Забронировать комнату для настольных игр", callback_data="bron_room")
    btn4 = types.InlineKeyboardButton("📋 Мои брони", callback_data="books")
    btn5 = types.InlineKeyboardButton("📜 Правила посещения", callback_data="rules")

    markup.row(btn1)
    markup.row(btn2)
    markup.row(btn3)
    markup.row(btn4)
    markup.row(btn5)

    # Кнопка только для админов
    if user_id is not None and user_id in ADMINS:
        admin_btn = types.InlineKeyboardButton("👑 Все актуальные брони", callback_data="admin_all_bookings")
        markup.row(admin_btn)

    bot.send_message(chat_id, "🏠 Главное меню\n\nЧто хочешь сделать?", reply_markup=markup)


def show_admin_bookings(chat_id):
    """Показывает ВСЕ активные брони всех пользователей (только для админов)"""
    bookings = get_active_bookings()

    if not bookings:
        markup = types.InlineKeyboardMarkup()
        back_btn = types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")
        markup.row(back_btn)
        bot.send_message(chat_id, "📋 Актуальных броней нет.", reply_markup=markup)
        return

    text = "👑 АКТУАЛЬНЫЕ БРОНИ (все пользователи):\n\n"
    current_date = None

    for b in bookings:
        booking_id, b_user_id, username, first_name, phone, date, start_time, end_time, table_type, created = b

        if date != current_date:
            current_date = date
            day_label = get_day_label(date)
            date_header = f"📅 {date} ({day_label})" if day_label else f"📅 {date}"
            text += f"{date_header}\n"
            text += "─────────────\n"

        type_emoji = get_type_emoji(table_type)
        uname = f"@{username}" if username else "нет"
        text += f"#{booking_id} | {start_time}-{end_time} | {type_emoji} {table_type}\n"
        text += f"   👤 {first_name} | 📱 {phone}\n"
        text += f"   🆔 {b_user_id} | {uname}\n\n"

        if len(text) > 3500:
            text += "... (список обрезан)"
            break

    markup = types.InlineKeyboardMarkup()
    back_btn = types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")
    markup.row(back_btn)

    bot.send_message(chat_id, text, reply_markup=markup)


def show_my_bookings(chat_id, user_id):
    conn = sqlite3.connect('bookings.db')
    cursor = conn.cursor()
    try:
        cursor.execute(
            'SELECT id, booking_date, booking_time_start, booking_time_end, table_type, created_at, status FROM bookings WHERE user_id = ? ORDER BY created_at DESC',
            (user_id,))
        bookings = cursor.fetchall()
    except:
        bookings = []
    conn.close()

    if bookings:
        text = "📋 ВАШИ БРОНИ:\n\n"
        markup = types.InlineKeyboardMarkup(row_width=1)

        for booking in bookings:
            booking_id, date, start_time, end_time, table_type, created, status = booking
            status_emoji = "✅" if status == "active" else "❌"
            status_text = "Активна" if status == "active" else "Отменена"
            type_emoji = get_type_emoji(table_type)
            text += f"{status_emoji} {date} {start_time}-{end_time}\n"
            text += f"   {type_emoji} {table_type}\n"
            text += f"   Статус: {status_text}\n"
            text += f"   ID: #{booking_id}\n\n"

            if status == "active":
                cancel_btn = types.InlineKeyboardButton(f"❌ Отменить бронь #{booking_id}",
                                                        callback_data=f"cancel_{booking_id}")
                markup.row(cancel_btn)

        clear_btn = types.InlineKeyboardButton("🗑 Очистить список броней", callback_data="clear_bookings")
        markup.row(clear_btn)

        back_btn = types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")
        markup.row(back_btn)

        bot.send_message(chat_id, text, reply_markup=markup)
    else:
        markup = types.InlineKeyboardMarkup()
        back_btn = types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")
        markup.row(back_btn)
        bot.send_message(chat_id, "📋 У вас пока нет бронирований.", reply_markup=markup)


def show_booking_dates(chat_id):
    markup = types.InlineKeyboardMarkup(row_width=1)
    available_dates = get_available_dates()
    for date_key, date_label in available_dates:
        btn = types.InlineKeyboardButton(date_label, callback_data=date_key)
        markup.row(btn)
    back_btn = types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_table")
    markup.row(back_btn)
    bot.send_message(chat_id, "📅 Выберите дату бронирования:", reply_markup=markup)


def show_table_type_menu(chat_id, user_id):
    """Показывает выбор типа стола (ПЕРВЫЙ ШАГ)"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("🇷🇺 Русский бильярд", callback_data="table_russian")
    btn2 = types.InlineKeyboardButton("🎱 Пул", callback_data="table_pool")
    markup.row(btn1, btn2)

    back_btn = types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")
    markup.row(back_btn)

    bot.send_message(chat_id, "🎯 Выберите тип стола:", reply_markup=markup)


def show_start_time_menu(chat_id, user_id):
    booking_date = user_data[user_id].get('booking_date')
    is_today = user_data[user_id].get('is_today', False)
    table_type = user_data[user_id].get('table_type')

    markup = types.InlineKeyboardMarkup(row_width=4)
    times = []

    booked_intervals = get_booked_times(booking_date, table_type) if booking_date else []
    current_hour = get_current_hour_msk()

    min_start_hour = 16
    if is_today:
        min_start_hour = max(16, current_hour + 1)

    # Последнее доступное время начала — 22:00 (range до 23, не включая 23)
    for hour in range(min_start_hour, 23):
        is_booked = False
        for booked_start, booked_end in booked_intervals:
            if booked_start and booked_end:
                try:
                    booked_start_hour = int(booked_start.split(":")[0])
                    booked_end_hour = int(booked_end.split(":")[0])
                    if booked_end_hour == 0:
                        booked_end_hour = 24
                    if booked_start_hour <= hour < booked_end_hour:
                        is_booked = True
                        break
                except:
                    continue
        if not is_booked:
            time_str = f"{hour:02d}:00"
            times.append(types.InlineKeyboardButton(time_str, callback_data=f"start_{time_str}"))

    if not times:
        markup = types.InlineKeyboardMarkup()
        back_btn = types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_dates")
        menu_btn = types.InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")
        markup.row(back_btn)
        markup.row(menu_btn)
        bot.send_message(chat_id, "❌ Нет доступного времени для бронирования.", reply_markup=markup)
        return

    for i in range(0, len(times), 4):
        markup.row(*times[i:i + 4])

    back_btn = types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_dates")
    menu_btn = types.InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")
    markup.row(back_btn)
    markup.row(menu_btn)

    if is_today:
        current_hour = get_current_hour_msk()
        bot.send_message(
            chat_id,
            f"📅 Дата: {booking_date} (СЕГОДНЯ)\n\n"
            f"🕐 Выберите время НАЧАЛА:\n"
            f"⏰ Текущее время: {current_hour:02d}:00 по МСК",
            reply_markup=markup
        )
    else:
        bot.send_message(
            chat_id,
            f"📅 Дата: {booking_date}\n\n"
            "🕐 Выберите время НАЧАЛА:",
            reply_markup=markup
        )


def show_end_time_menu(chat_id, user_id):
    booking_date = user_data[user_id].get('booking_date')
    is_today = user_data[user_id].get('is_today', False)
    start_time = user_data[user_id].get('booking_time_start')
    table_type = user_data[user_id].get('table_type')

    if not start_time:
        return

    start_hour = int(start_time.split(":")[0])

    markup = types.InlineKeyboardMarkup(row_width=4)
    times = []

    booked_intervals = get_booked_times(booking_date, table_type) if booking_date else []
    current_hour = get_current_hour_msk()

    min_end_hour = start_hour + 1
    if is_today:
        min_end_hour = max(min_end_hour, current_hour + 1)

    for hour in range(min_end_hour, 24):
        is_booked = False
        for booked_start, booked_end in booked_intervals:
            if booked_start and booked_end:
                try:
                    booked_start_hour = int(booked_start.split(":")[0])
                    booked_end_hour = int(booked_end.split(":")[0])
                    if booked_end_hour == 0:
                        booked_end_hour = 24
                    if booked_start_hour <= hour < booked_end_hour:
                        is_booked = True
                        break
                except:
                    continue
        if not is_booked:
            time_str = f"{hour:02d}:00"
            times.append(types.InlineKeyboardButton(time_str, callback_data=f"end_{time_str}"))

    # ===== ДОБАВЛЯЕМ 00:00 (ПОЛНОЧЬ) =====
    midnight_blocked = False
    for booked_start, booked_end in booked_intervals:
        if booked_start and booked_end:
            try:
                bs_h = int(booked_start.split(":")[0])
                be_h = int(booked_end.split(":")[0])
                if be_h == 0:
                    be_h = 24
                if bs_h <= 23 < be_h:
                    midnight_blocked = True
                    break
            except:
                continue

    if not midnight_blocked:
        times.append(types.InlineKeyboardButton("00:00", callback_data="end_00:00"))

    if not times:
        markup = types.InlineKeyboardMarkup()
        back_btn = types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_start")
        menu_btn = types.InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")
        markup.row(back_btn)
        markup.row(menu_btn)
        bot.send_message(chat_id, "❌ Нет доступного времени для окончания.", reply_markup=markup)
        return

    for i in range(0, len(times), 4):
        markup.row(*times[i:i + 4])

    back_btn = types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_start")
    menu_btn = types.InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")
    markup.row(back_btn)
    markup.row(menu_btn)

    bot.send_message(
        chat_id,
        f"📅 Дата: {booking_date}\n"
        f"🕐 Начало: {start_time}\n\n"
        "🕐 Выберите время ОКОНЧАНИЯ:\n"
        "⏰ Минимальная продолжительность - 1 час\n"
        "🌙 Можно выбрать 00:00 (полночь)",
        reply_markup=markup
    )


@bot.message_handler(commands=["start"])
def main(message):
    show_main_menu(message.chat.id, message.from_user.id)


@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    try:
        # ✅ ОБЯЗАТЕЛЬНО: отвечаем на callback, чтобы кнопка не "грузилась" вечно
        bot.answer_callback_query(call.id)

        if not hasattr(call, 'data'):
            return

        chat_id = call.message.chat.id
        user_id = call.from_user.id

        safe_delete_message(chat_id, call.message.message_id)

        # ===== НАВИГАЦИЯ =====

        if call.data == "back_to_menu":
            if user_id in user_data:
                user_data.pop(user_id, None)
            show_main_menu(chat_id, user_id)
            return

        if call.data == "back_to_table":
            if user_id in user_data:
                user_data[user_id].pop('booking_date', None)
                user_data[user_id].pop('booking_time_start', None)
                user_data[user_id].pop('booking_time_end', None)
                user_data[user_id].pop('is_today', None)
                user_data[user_id]['state'] = 'selecting_table'
            show_table_type_menu(chat_id, user_id)
            return

        if call.data == "back_to_dates":
            if user_id in user_data:
                user_data[user_id].pop('booking_time_start', None)
                user_data[user_id].pop('booking_time_end', None)
                user_data[user_id]['state'] = 'selecting_date'
            show_booking_dates(chat_id)
            return

        if call.data == "back_to_start":
            if user_id in user_data:
                user_data[user_id].pop('booking_time_end', None)
                user_data[user_id]['state'] = 'selecting_start_time'
            show_start_time_menu(chat_id, user_id)
            return

        # ===== АДМИН: ВСЕ АКТУАЛЬНЫЕ БРОНИ =====

        if call.data == "admin_all_bookings":
            if user_id not in ADMINS:
                bot.send_message(chat_id, "⛔ У вас нет доступа.")
                return
            show_admin_bookings(chat_id)
            return

        # ===== ОСНОВНЫЕ КНОПКИ =====

        if call.data == "tariffs":
            markup = types.InlineKeyboardMarkup()
            back_btn = types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")
            markup.row(back_btn)
            bot.send_message(
                chat_id,
                "💰 ТАРИФЫ\n\n"
                "ПЕРВЫЙ ЧАС БЕСПЛАТНО ЗА ОТЗЫВ\n\n"
                "🎱 БИЛЬЯРД\n\n"
                "🏢 ПО БУДНЯМ (ПН-ЧТ):\n"
                "• 1 час — 600 ₽\n"
                "• 2 часа — 1200 ₽\n"
                "• 3 часа — 1800 ₽\n\n"
                "🎉 ПО ВЫХОДНЫМ (ПТ-ВС):\n"
                "• 1 час — 1000 ₽\n"
                "• 2 часа — 2000 ₽\n"
                "• 3 часа — 3000 ₽\n\n"
                "🎲 КОМНАТА ДЛЯ НАСТОЛЬНЫХ ИГР\n\n"
                "🏢 ПО БУДНЯМ (ПН-ЧТ):\n"
                "• 1 час — 300 ₽\n\n"
                "🎉 ПО ВЫХОДНЫМ (ПТ-ВС):\n"
                "• 1 час — 500 ₽\n\n",
                reply_markup=markup
            )

        elif call.data == "rules":
            markup = types.InlineKeyboardMarkup()
            back_btn = types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")
            markup.row(back_btn)
            bot.send_message(
                chat_id,
                "📋 ПРАВИЛА ПОСЕЩЕНИЯ\n\n"
                "🚫 Со своим нельзя\n"
                "Своё пиво, лимонад, кофе и еду приносить запрещено.\n\n"
                "🍾 Пробковый сбор\n"
                "За крепкий алкоголь - 300₽ с человека.\n\n"
                "🚫 На бильярдный стол напитки и еду ставить запрещено\n\n"
                "⚠️ ШТРАФЫ:\n"
                "• Порча бильярдного стола - 30 000₽\n"
                "• Порча кия - 7000₽\n"
                "• Порча шаров - 5000₽",
                reply_markup=markup
            )

        elif call.data == "bron":
            if user_id in user_data:
                user_data.pop(user_id, None)
            user_data[user_id] = {'state': 'selecting_table'}
            show_table_type_menu(chat_id, user_id)

        # ===== БРОНЬ КОМНАТЫ ДЛЯ НАСТОЛЬНЫХ ИГР =====

        elif call.data == "bron_room":
            if user_id in user_data:
                user_data.pop(user_id, None)
            user_data[user_id] = {
                'state': 'selecting_date',
                'table_type': "Комната для настольных игр"
            }
            show_booking_dates(chat_id)

        # ===== ВЫБОР ТИПА СТОЛА (ПЕРВЫЙ ШАГ) =====

        elif call.data == "table_russian":
            if user_id in user_data:
                user_data[user_id]['table_type'] = "Русский бильярд"
                user_data[user_id]['state'] = 'selecting_date'
            show_booking_dates(chat_id)

        elif call.data == "table_pool":
            if user_id in user_data:
                user_data[user_id]['table_type'] = "Пул"
                user_data[user_id]['state'] = 'selecting_date'
            show_booking_dates(chat_id)

        # ===== ВЫБОР ДАТЫ =====

        elif call.data.startswith("date_"):
            days_map = {"date_1": 1, "date_2": 2, "date_3": 3, "date_4": 4,
                        "date_5": 5, "date_6": 6, "date_7": 7}

            is_today = call.data == "date_today"
            days = 0 if is_today else days_map.get(call.data, 1)

            now_msk = get_current_datetime_msk()
            booking_date = (now_msk + timedelta(days=days)).strftime("%d.%m.%Y")

            if user_id not in user_data:
                user_data[user_id] = {}
            user_data[user_id]['booking_date'] = booking_date
            user_data[user_id]['is_today'] = is_today
            user_data[user_id]['state'] = 'selecting_start_time'

            show_start_time_menu(chat_id, user_id)

        # ===== ВЫБОР ВРЕМЕНИ НАЧАЛА =====

        elif call.data.startswith("start_") and user_data.get(user_id, {}).get('state') == 'selecting_start_time':
            start_time = call.data.replace("start_", "")
            user_data[user_id]['booking_time_start'] = start_time
            user_data[user_id]['state'] = 'selecting_end_time'

            show_end_time_menu(chat_id, user_id)

        # ===== ВЫБОР ВРЕМЕНИ ОКОНЧАНИЯ =====

        elif call.data.startswith("end_") and user_data.get(user_id, {}).get('state') == 'selecting_end_time':
            end_time = call.data.replace("end_", "")
            user_data[user_id]['booking_time_end'] = end_time
            user_data[user_id]['state'] = 'waiting_phone'

            booking_date = user_data[user_id]['booking_date']
            start_time = user_data[user_id]['booking_time_start']
            table_type = user_data[user_id]['table_type']

            start_hour = int(start_time.split(":")[0])
            end_hour = int(end_time.split(":")[0])
            if end_hour == 0:
                end_hour = 24
            duration = end_hour - start_hour

            markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
            btn_phone = types.KeyboardButton("📱 Отправить номер телефона", request_contact=True)
            markup.add(btn_phone)
            btn_manual = types.KeyboardButton("✏️ Ввести номер вручную")
            markup.add(btn_manual)
            btn_back = types.KeyboardButton("🔙 Назад в меню")
            markup.add(btn_back)

            type_emoji = get_type_emoji(table_type)
            bot.send_message(
                chat_id,
                f"📅 Дата: {booking_date}\n"
                f"🕐 Время: {start_time} - {end_time}\n"
                f"{type_emoji} {table_type}\n"
                f"⏱ Продолжительность: {duration} час(а/ов)\n\n"
                "📱 Пожалуйста, отправьте ваш номер телефона",
                reply_markup=markup
            )

        # ===== ВВОД ИМЕНИ =====

        elif call.data == "manual_name":
            if user_id not in user_data:
                user_data[user_id] = {}
            user_data[user_id]['state'] = 'waiting_name'

            markup = types.InlineKeyboardMarkup()
            back_btn = types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_dates")
            menu_btn = types.InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")
            markup.row(back_btn)
            markup.row(menu_btn)

            bot.send_message(chat_id, "✏️ Введите ваше имя:", reply_markup=markup)

        # ===== МОИ БРОНИ =====

        elif call.data == "books":
            show_my_bookings(chat_id, user_id)

        # ===== ОЧИСТКА СПИСКА БРОНЕЙ =====

        elif call.data == "clear_bookings":
            markup = types.InlineKeyboardMarkup(row_width=2)
            yes_btn = types.InlineKeyboardButton("✅ Да, удалить всё", callback_data="clear_bookings_confirm")
            no_btn = types.InlineKeyboardButton("↩️ Отмена", callback_data="books")
            markup.row(yes_btn, no_btn)
            bot.send_message(
                chat_id,
                "⚠️ Вы уверены, что хотите удалить ВСЕ свои брони?\n"
                "Это действие нельзя отменить.",
                reply_markup=markup
            )

        elif call.data == "clear_bookings_confirm":
            deleted = clear_user_bookings(user_id)
            if deleted > 0:
                bot.send_message(chat_id, f"🗑 Удалено броней: {deleted}")
                notify_admins(f"🗑 Пользователь {user_id} очистил список своих броней ({deleted} шт.)")
            else:
                bot.send_message(chat_id, "📋 Список и так пуст.")
            time.sleep(0.5)
            show_my_bookings(chat_id, user_id)

        # ===== ОТМЕНА БРОНИ =====

        elif call.data.startswith("cancel_"):
            booking_id = int(call.data.replace("cancel_", ""))
            if cancel_booking(booking_id, user_id):
                bot.send_message(chat_id, f"✅ Бронь #{booking_id} успешно отменена!")
                notify_admins(f"❌ Бронь #{booking_id} отменена пользователем {user_id}")
                time.sleep(0.5)
                show_my_bookings(chat_id, user_id)
            else:
                bot.send_message(chat_id, f"❌ Не удалось отменить бронь #{booking_id}.")

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        try:
            bot.send_message(call.message.chat.id, "⚠️ Произошла ошибка. Попробуйте еще раз.")
        except:
            pass


@bot.message_handler(func=lambda message: message.text == "✏️ Ввести номер вручную")
def manual_phone_input(message):
    user_id = message.from_user.id
    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]['state'] = 'waiting_phone'

    safe_delete_message(message.chat.id, message.message_id)

    markup = types.InlineKeyboardMarkup()
    back_btn = types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")
    markup.row(back_btn)

    bot.send_message(message.chat.id,
                     "📱 Введите ваш номер телефона в формате:\nПример: +7 999 123-45-67 или 89991234567",
                     reply_markup=markup)


@bot.message_handler(content_types=['text', 'contact'])
def handle_messages(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    # ===== ОБРАБОТКА КОНТАКТА =====
    if message.contact:
        if user_id not in user_data or user_data[user_id].get('state') != 'waiting_phone':
            bot.send_message(chat_id, "⚠️ Сначала выберите дату и время бронирования.")
            return

        phone = message.contact.phone_number
        user_data[user_id]['phone'] = phone
        user_data[user_id]['state'] = 'waiting_name'

        markup_remove = types.ReplyKeyboardRemove()
        safe_delete_message(chat_id, message.message_id)

        bot.send_message(
            chat_id,
            f"✅ Номер сохранён: {phone}\n\n"
            "✏️ Теперь введите ваше имя:",
            reply_markup=markup_remove
        )
        return

    if not message.text:
        bot.send_message(chat_id, "⚠️ Используйте кнопки.")
        return

    if message.text == "🔙 Назад в меню":
        safe_delete_message(chat_id, message.message_id)
        if user_id in user_data:
            user_data.pop(user_id, None)
        show_main_menu(chat_id, user_id)
        return

    if user_id in user_data and user_data[user_id].get('state') == 'waiting_phone':
        phone = message.text.strip()
        if any(char.isdigit() for char in phone):
            user_data[user_id]['phone'] = phone
            user_data[user_id]['state'] = 'waiting_name'
            markup_remove = types.ReplyKeyboardRemove()

            safe_delete_message(chat_id, message.message_id)

            bot.send_message(
                chat_id,
                f"✅ Номер сохранён: {phone}\n\n"
                "✏️ Теперь введите ваше имя:",
                reply_markup=markup_remove
            )
        else:
            bot.send_message(chat_id, "❌ Введите корректный номер телефона")
        return

    if user_id in user_data and user_data[user_id].get('state') == 'waiting_name':
        name = message.text.strip()
        if len(name) >= 2:
            safe_delete_message(chat_id, message.message_id)
            complete_booking(user_id, name)
        else:
            bot.send_message(chat_id, "❌ Имя должно содержать хотя бы 2 символа.")
        return

    if user_id in user_data:
        bot.send_message(chat_id, "⚠️ Используйте кнопки.")
    else:
        show_main_menu(chat_id, user_id)


if __name__ == "__main__":
    try:
        logger.info("🤖 Бот запущен!")
        bot.polling(none_stop=True, skip_pending=True, timeout=60)
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
