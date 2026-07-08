import telebot
from telebot import *
import sqlite3
from datetime import datetime, timedelta, timezone
import logging
import time
import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

user_data = {}

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

session = requests.Session()
session.verify = False

bot = telebot.TeleBot("8889296379:AAF0B3-SGaOQuvQuOzMsjqKyfMZ9x3UAX_o")
bot.session = session

ADMINS = [819284226, 8837073941]


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


def add_booking(user_id, username, first_name, last_name, phone, booking_date, booking_time_start, booking_time_end, table_type):
    conn = sqlite3.connect('bookings.db')
    cursor = conn.cursor()
    cursor.execute('''INSERT INTO bookings (user_id, username, first_name, last_name, phone, booking_date, booking_time_start, booking_time_end, table_type, created_at, status) 
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                   (user_id, username, first_name, last_name, phone, booking_date, booking_time_start, booking_time_end, table_type,
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


def get_booked_times(booking_date):
    conn = sqlite3.connect('bookings.db')
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT booking_time_start, booking_time_end FROM bookings WHERE booking_date = ? AND status = "active"', (booking_date,))
        booked_times = cursor.fetchall()
    except:
        booked_times = []
    conn.close()
    return booked_times


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

    add_booking(user_id=user_id, username=call.from_user.username if call else None, first_name=name, last_name="",
                phone=phone, booking_date=booking_date, booking_time_start=booking_time_start,
                booking_time_end=booking_time_end, table_type=table_type)

    # Отправка админу с указанием стола
    table_emoji = "🇷🇺" if table_type == "Русский бильярд" else "🎱"
    admin_message = (
        f"🆕 НОВАЯ БРОНЬ!\n\n"
        f"👤 Имя: {name}\n"
        f"📱 Телефон: {phone}\n"
        f"📱 Username: @{call.from_user.username if call and call.from_user.username else 'нет'}\n"
        f"🆔 ID: {user_id}\n"
        f"📅 Дата: {booking_date}\n"
        f"🕐 Время: {booking_time_start} - {booking_time_end}\n"
        f"{table_emoji} Стол: {table_type}"
    )
    notify_admins(admin_message)

    bot.send_message(user_id,
                     f"✅ Бронь подтверждена!\n\n"
                     f"📅 Дата: {booking_date}\n"
                     f"🕐 Время: {booking_time_start} - {booking_time_end}\n"
                     f"{table_emoji} Стол: {table_type}\n"
                     f"👤 Имя: {name}\n"
                     f"📱 Телефон: {phone}\n\n"
                     f"Скоро с вами свяжется менеджер.")
    user_data.pop(user_id, None)


def show_main_menu(chat_id):
    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton("💰 Тарифы", callback_data="tariffs")
    btn2 = types.InlineKeyboardButton("📅 Забронировать стол", callback_data="bron")
    btn3 = types.InlineKeyboardButton("📋 Мои брони", callback_data="books")
    btn4 = types.InlineKeyboardButton("📜 Правила посещения", callback_data="rules")

    markup.row(btn1)
    markup.row(btn2)
    markup.row(btn3)
    markup.row(btn4)

    bot.send_message(chat_id, "🏠 Главное меню\n\nЧто хочешь сделать?", reply_markup=markup)


def show_my_bookings(chat_id, user_id):
    conn = sqlite3.connect('bookings.db')
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT id, booking_date, booking_time_start, booking_time_end, table_type, created_at, status FROM bookings WHERE user_id = ? ORDER BY created_at DESC', (user_id,))
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
            table_emoji = "🇷🇺" if table_type == "Русский бильярд" else "🎱"
            text += f"{status_emoji} {date} {start_time}-{end_time}\n"
            text += f"   {table_emoji} {table_type}\n"
            text += f"   Статус: {status_text}\n"
            text += f"   ID: #{booking_id}\n\n"

            if status == "active":
                cancel_btn = types.InlineKeyboardButton(f"❌ Отменить бронь #{booking_id}", callback_data=f"cancel_{booking_id}")
                markup.row(cancel_btn)

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
    
    markup = types.InlineKeyboardMarkup(row_width=4)
    times = []
    
    booked_intervals = get_booked_times(booking_date) if booking_date else []
    current_hour = get_current_hour_msk()
    
    min_start_hour = 16
    if is_today:
        min_start_hour = max(16, current_hour + 1)
    
    for hour in range(min_start_hour, 24):
        is_booked = False
        for booked_start, booked_end in booked_intervals:
            if booked_start and booked_end:
                try:
                    booked_start_hour = int(booked_start.split(":")[0])
                    booked_end_hour = int(booked_end.split(":")[0])
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
        markup.row(*times[i:i+4])
    
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
    
    if not start_time:
        return
    
    start_hour = int(start_time.split(":")[0])
    
    markup = types.InlineKeyboardMarkup(row_width=4)
    times = []
    
    booked_intervals = get_booked_times(booking_date) if booking_date else []
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
                    if booked_start_hour <= hour < booked_end_hour:
                        is_booked = True
                        break
                except:
                    continue
        if not is_booked:
            time_str = f"{hour:02d}:00"
            times.append(types.InlineKeyboardButton(time_str, callback_data=f"end_{time_str}"))
    
    is_booked = False
    for booked_start, booked_end in booked_intervals:
        if booked_start and booked_end:
            try:
                booked_start_hour = int(booked_start.split(":")[0])
                booked_end_hour = int(booked_end.split(":")[0])
                if booked_start_hour <= 24 < booked_end_hour:
                    is_booked = True
                    break
            except:
                continue
    if not is_booked and (not is_today or (is_today and current_hour < 23)):
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
        markup.row(*times[i:i+4])
    
    back_btn = types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_start")
    menu_btn = types.InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")
    markup.row(back_btn)
    markup.row(menu_btn)
    
    bot.send_message(
        chat_id,
        f"📅 Дата: {booking_date}\n"
        f"🕐 Начало: {start_time}\n\n"
        "🕐 Выберите время ОКОНЧАНИЯ:\n"
        "⏰ Минимальная продолжительность - 1 час",
        reply_markup=markup
    )


@bot.message_handler(commands=["start"])
def main(message):
    show_main_menu(message.chat.id)


@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    try:
        if not hasattr(call, 'data'):
            return

        chat_id = call.message.chat.id
        user_id = call.from_user.id

        safe_delete_message(chat_id, call.message.message_id)

        # ===== НАВИГАЦИЯ =====
        
        if call.data == "back_to_menu":
            if user_id in user_data:
                user_data.pop(user_id, None)
            show_main_menu(chat_id)
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

        # ===== ОСНОВНЫЕ КНОПКИ =====

        if call.data == "tariffs":
            markup = types.InlineKeyboardMarkup()
            back_btn = types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")
            markup.row(back_btn)
            bot.send_message(
                chat_id,
                "💰 ТАРИФЫ\n\n"
                "ПЕРВЫЙ ЧАС БЕСПЛАТНО ЗА ОТЗЫВ\n\n"
                "🏢 ПО БУДНЯМ (ПН-ЧТ):\n"
                "• 1 час — 600 ₽\n"
                "• 2 часа — 1200 ₽\n"
                "• 3 часа — 1800 ₽\n\n"
                "🎉 ПО ВЫХОДНЫМ (ПТ-ВС):\n"
                "• 1 час — 1000 ₽\n"
                "• 2 часа — 2000 ₽\n"
                "• 3 часа — 3000 ₽\n\n",
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

            table_emoji = "🇷🇺" if table_type == "Русский бильярд" else "🎱"
            bot.send_message(
                chat_id,
                f"📅 Дата: {booking_date}\n"
                f"🕐 Время: {start_time} - {end_time}\n"
                f"{table_emoji} Стол: {table_type}\n"
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

    if not message.text:
        if message.contact:
            phone = message.contact.phone_number
            if user_id in user_data and 'booking_date' in user_data[user_id]:
                user_data[user_id]['phone'] = phone
                markup_remove = types.ReplyKeyboardRemove()

                safe_delete_message(message.chat.id, message.message_id)

                bot.send_message(
                    message.chat.id,
                    f"✅ Номер сохранён: {phone}",
                    reply_markup=markup_remove
                )

                markup = types.InlineKeyboardMarkup(row_width=1)
                btn_manual_name = types.InlineKeyboardButton("✏️ Ввести имя вручную", callback_data="manual_name")
                markup.row(btn_manual_name)
                back_btn = types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_dates")
                menu_btn = types.InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")
                markup.row(back_btn)
                markup.row(menu_btn)

                bot.send_message(message.chat.id, "✏️ Введите ваше имя:", reply_markup=markup)
            return
        else:
            bot.send_message(message.chat.id, "⚠️ Используйте кнопки.")
            return

    if message.text == "🔙 Назад в меню":
        safe_delete_message(message.chat.id, message.message_id)
        if user_id in user_data:
            user_data.pop(user_id, None)
        show_main_menu(message.chat.id)
        return

    if user_id in user_data and user_data[user_id].get('state') == 'waiting_phone':
        phone = message.text.strip()
        if any(char.isdigit() for char in phone):
            user_data[user_id]['phone'] = phone
            user_data[user_id]['state'] = 'waiting_name'
            markup_remove = types.ReplyKeyboardRemove()

            safe_delete_message(message.chat.id, message.message_id)

            bot.send_message(message.chat.id, f"✅ Номер сохранён: {phone}", reply_markup=markup_remove)

            markup = types.InlineKeyboardMarkup(row_width=1)
            btn_manual_name = types.InlineKeyboardButton("✏️ Ввести имя вручную", callback_data="manual_name")
            markup.row(btn_manual_name)
            back_btn = types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_dates")
            menu_btn = types.InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")
            markup.row(back_btn)
            markup.row(menu_btn)

            bot.send_message(message.chat.id, "✏️ Введите ваше имя:", reply_markup=markup)
        else:
            bot.send_message(message.chat.id, "❌ Введите корректный номер телефона")
        return

    if user_id in user_data and user_data[user_id].get('state') == 'waiting_name':
        name = message.text.strip()
        if len(name) >= 2:
            safe_delete_message(message.chat.id, message.message_id)
            complete_booking(user_id, name)
        else:
            bot.send_message(message.chat.id, "❌ Имя должно содержать хотя бы 2 символа.")
        return

    if user_id in user_data:
        bot.send_message(message.chat.id, "⚠️ Используйте кнопки.")
    else:
        show_main_menu(message.chat.id)


if __name__ == "__main__":
    try:
        logger.info("🤖 Бот запущен!")
        bot.polling(none_stop=True)
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
