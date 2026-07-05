
import telebot
from telebot import *
import webbrowser
from pyexpat.errors import messages
import sqlite3
from datetime import datetime, timedelta
import logging
import time

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

user_data = {}

bot = telebot.TeleBot("8889296379:AAF0B3-SGaOQuvQuOzMsjqKyfMZ9x3UAX_o")
name = None

# Список администраторов (ID пользователей Telegram)
ADMINS = [819284226]  # Убедитесь, что эти ID правильные


def init_db():
    conn = sqlite3.connect("bookings.db")
    cur = conn.cursor()

    # Проверяем существующие колонки
    cur.execute("PRAGMA table_info(bookings)")
    columns = [column[1] for column in cur.fetchall()]

    # Создаем таблицу если её нет
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
        created_at TEXT,
        status TEXT DEFAULT 'active'
    )''')

    # Добавляем недостающие колонки
    if 'booking_time_start' not in columns:
        cur.execute('ALTER TABLE bookings ADD COLUMN booking_time_start TEXT')
        logger.info("✅ Добавлена колонка booking_time_start")

    if 'booking_time_end' not in columns:
        cur.execute('ALTER TABLE bookings ADD COLUMN booking_time_end TEXT')
        logger.info("✅ Добавлена колонка booking_time_end")

    if 'status' not in columns:
        cur.execute('ALTER TABLE bookings ADD COLUMN status TEXT DEFAULT "active"')
        logger.info("✅ Добавлена колонка status")

    conn.commit()
    cur.close()
    conn.close()


init_db()


def add_booking(user_id, username, first_name, last_name, phone, booking_date, booking_time_start, booking_time_end):
    conn = sqlite3.connect('bookings.db')
    cursor = conn.cursor()
    cursor.execute('''INSERT INTO bookings (user_id, username, first_name, last_name, phone, booking_date, booking_time_start, booking_time_end, created_at, status) 
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', \
                   (user_id, username, first_name, last_name, phone, booking_date, booking_time_start, booking_time_end,
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
    """Получает занятое время для конкретной даты"""
    conn = sqlite3.connect('bookings.db')
    cursor = conn.cursor()
    try:
        cursor.execute(
            'SELECT booking_time_start, booking_time_end FROM bookings WHERE booking_date = ? AND status = "active"',
            (booking_date,))
        booked_times = cursor.fetchall()
    except sqlite3.OperationalError as e:
        logger.error(f"Ошибка при получении занятого времени: {e}")
        booked_times = []
    conn.close()
    return booked_times


def safe_delete_message(chat_id, message_id):
    """Безопасное удаление сообщения"""
    try:
        if chat_id and message_id:
            bot.delete_message(chat_id, message_id)
            return True
    except Exception as e:
        # Игнорируем ошибку "message to delete not found"
        if "message to delete not found" in str(e):
            logger.debug(f"Сообщение {message_id} уже было удалено")
        else:
            logger.error(f"Не удалось удалить сообщение {message_id}: {e}")
    return False


def notify_admins(message_text):
    """Отправляет уведомление всем админам с обработкой ошибок"""
    for admin_id in ADMINS:
        try:
            bot.send_message(admin_id, message_text)
            logger.info(f"✅ Уведомление отправлено админу {admin_id}")
        except Exception as e:
            logger.error(f"❌ Не удалось отправить сообщение админу {admin_id}: {e}")


def complete_booking(user_id, name, call=None):
    user_data_item = user_data.get(user_id, {})
    booking_date = user_data_item.get('booking_date')
    booking_time_start = user_data_item.get('booking_time_start')
    booking_time_end = user_data_item.get('booking_time_end')
    phone = user_data_item.get('phone')

    if not booking_date or not booking_time_start or not booking_time_end or not phone:
        bot.send_message(user_id, "❌ Ошибка! Попробуйте начать заново.")
        return

    add_booking(user_id=user_id, username=call.from_user.username if call else None, first_name=name, last_name="",
                phone=phone, booking_date=booking_date, booking_time_start=booking_time_start,
                booking_time_end=booking_time_end)

    # Отправляем уведомление админам
    admin_message = (
        f"🆕 НОВАЯ БРОНЬ!\n\n"
        f"👤 Имя: {name}\n"
        f"📱 Телефон: {phone}\n"
        f"📱 Username: @{call.from_user.username if call and call.from_user.username else 'нет'}\n"
        f"🆔 ID: {user_id}\n"
        f"📅 Дата: {booking_date}\n"
        f"🕐 Время: {booking_time_start} - {booking_time_end}"
    )
    notify_admins(admin_message)

    bot.send_message(user_id,
                     f"✅ Бронь подтверждена!\n\n"f"📅 Дата: {booking_date}\n"f"🕐 Время: {booking_time_start} - {booking_time_end}\n"f"👤 Имя: {name}\n"f"📱 Телефон: {phone}\n\n"f"Скоро с вами свяжется менеджер.")
    user_data.pop(user_id, None)


def show_main_menu(chat_id):
    """Показывает главное меню"""
    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton("💰 Тарифы", callback_data="tariffs")
    btn2 = types.InlineKeyboardButton("📅 Забронировать стол", callback_data="bron")
    btn3 = types.InlineKeyboardButton("📋 Мои брони", callback_data="books")
    btn4 = types.InlineKeyboardButton("📜 Правила посещения", callback_data="rules")

    markup.row(btn1)
    markup.row(btn2)
    markup.row(btn3)
    markup.row(btn4)

    try:
        bot.send_message(chat_id, "🏠 Главное меню\n\nЧто хочешь сделать?", reply_markup=markup)
    except Exception as e:
        logger.error(f"Ошибка при отправке главного меню пользователю {chat_id}: {e}")


def show_my_bookings(chat_id, user_id):
    """Показывает список броней пользователя"""
    conn = sqlite3.connect('bookings.db')
    cursor = conn.cursor()
    try:
        cursor.execute(
            'SELECT id, booking_date, booking_time_start, booking_time_end, created_at, status FROM bookings WHERE user_id = ? ORDER BY created_at DESC',
            (user_id,))
        bookings = cursor.fetchall()
    except sqlite3.OperationalError as e:
        logger.error(f"Ошибка при получении броней: {e}")
        bookings = []
    conn.close()

    if bookings:
        text = "📋 ВАШИ БРОНИ:\n\n"
        markup = types.InlineKeyboardMarkup(row_width=1)

        for booking in bookings:
            booking_id, date, start_time, end_time, created, status = booking
            status_emoji = "✅" if status == "active" else "❌"
            status_text = "Активна" if status == "active" else "Отменена"
            text += f"{status_emoji} {date} {start_time}-{end_time}\n"
            text += f"   Статус: {status_text}\n"
            text += f"   ID: #{booking_id}\n\n"

            # Добавляем кнопку отмены только для активных броней
            if status == "active":
                cancel_btn = types.InlineKeyboardButton(
                    f"❌ Отменить бронь #{booking_id}",
                    callback_data=f"cancel_{booking_id}"
                )
                markup.row(cancel_btn)

        back_btn = types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")
        markup.row(back_btn)

        bot.send_message(chat_id, text, reply_markup=markup)
    else:
        markup = types.InlineKeyboardMarkup()
        back_btn = types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")
        markup.row(back_btn)
        bot.send_message(chat_id, "📋 У вас пока нет бронирований.", reply_markup=markup)


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


@bot.message_handler(commands=["start"])
def main(message):
    show_main_menu(message.chat.id)


def generate_time_buttons(chat_id, start_hour=16, end_hour=23, booking_date=None):
    """Генерирует кнопки с временем для выбора, исключая занятое время"""
    markup = types.InlineKeyboardMarkup(row_width=4)
    times = []

    # Получаем занятое время для выбранной даты
    booked_intervals = []
    if booking_date:
        booked_intervals = get_booked_times(booking_date)

    # Создаем список доступных часов
    available_hours = []
    for hour in range(start_hour, end_hour + 1):
        # Проверяем, не занят ли этот час
        is_booked = False
        for booked_start, booked_end in booked_intervals:
            if booked_start and booked_end:
                try:
                    booked_start_hour = int(booked_start.split(":")[0])
                    booked_end_hour = int(booked_end.split(":")[0])
                    if booked_start_hour <= hour < booked_end_hour:
                        is_booked = True
                        break
                except (ValueError, AttributeError):
                    continue
        if not is_booked:
            available_hours.append(hour)

    # Создаем кнопки только для доступных часов
    for hour in available_hours:
        time_str = f"{hour:02d}:00"
        times.append(types.InlineKeyboardButton(time_str, callback_data=f"time_{time_str}"))

    # Если нет доступных часов
    if not times:
        markup = types.InlineKeyboardMarkup()
        back_btn = types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_booking")
        menu_btn = types.InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")
        markup.row(back_btn)
        markup.row(menu_btn)
        if booking_date:
            bot.send_message(chat_id, "❌ К сожалению, на эту дату все время уже занято. Выберите другую дату.")
        return markup

    # Разбиваем по 4 кнопки в ряд
    for i in range(0, len(times), 4):
        markup.row(*times[i:i + 4])

    back_btn = types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_booking")
    menu_btn = types.InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")
    markup.row(back_btn)
    markup.row(menu_btn)

    return markup


@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    try:
        # Проверяем, что call - это объект, а не строка
        if not hasattr(call, 'data'):
            logger.error("call не содержит data")
            return

        # Безопасно удаляем сообщение с кнопками
        if hasattr(call, 'message') and hasattr(call.message, 'chat'):
            safe_delete_message(call.message.chat.id, call.message.message_id)

        # Получаем chat_id для отправки сообщений
        chat_id = call.message.chat.id if hasattr(call, 'message') and hasattr(call.message, 'chat') else None
        if not chat_id:
            logger.error("Не удалось получить chat_id")
            return

        user_id = call.from_user.id

        # Кнопка "Главное меню" - возврат в главное меню
        if call.data == "back_to_menu":
            if user_id in user_data:
                user_data.pop(user_id, None)
            show_main_menu(chat_id)
            return

        # Кнопка "Назад" в бронировании - возврат к выбору даты
        if call.data == "back_to_booking":
            if user_id in user_data:
                # Очищаем данные о времени, но оставляем дату
                user_data[user_id].pop('booking_time_start', None)
                user_data[user_id].pop('booking_time_end', None)
                user_data[user_id]['state'] = 'selecting_date'
            # Показываем выбор даты
            show_booking_dates(chat_id)
            return

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
            show_booking_dates(chat_id)

        elif call.data.startswith("date_"):
            # Обработка выбора даты
            days_map = {
                "date_tomorrow": 1,
                "date_1day_after": 2,
                "date_2day_after": 3,
                "date_3day_after": 4,
                "date_4day_after": 5,
                "date_5day_after": 6,
                "date_6day_after": 7
            }

            days = days_map.get(call.data, 1)
            booking_date = (datetime.now() + timedelta(days=days)).strftime("%d.%m.%Y")

            if user_id not in user_data:
                user_data[user_id] = {}
            user_data[user_id]['booking_date'] = booking_date
            user_data[user_id]['state'] = 'selecting_start_time'

            # Показываем выбор времени начала с учетом занятых слотов
            markup = generate_time_buttons(chat_id, 16, 23, booking_date)
            bot.send_message(
                chat_id,
                f"📅 Дата: {booking_date}\n\n"
                "🕐 Выберите время НАЧАЛА бронирования:\n"
                "⏰ Работаем с 16:00 до 00:00\n"
                "❌ Занятое время не отображается",
                reply_markup=markup
            )

        elif call.data.startswith("time_") and user_data.get(user_id, {}).get('state') == 'selecting_start_time':
            # Обработка выбора времени начала
            selected_time = call.data.replace("time_", "")
            user_data[user_id]['booking_time_start'] = selected_time
            user_data[user_id]['state'] = 'selecting_end_time'

            booking_date = user_data[user_id]['booking_date']
            start_hour = int(selected_time.split(":")[0])

            markup = types.InlineKeyboardMarkup(row_width=4)
            times = []

            # Получаем занятые интервалы для даты
            booked_intervals = get_booked_times(booking_date)

            # Добавляем доступные часы для окончания
            for hour in range(start_hour + 1, 24):
                time_str = f"{hour:02d}:00"
                is_booked = False
                for booked_start, booked_end in booked_intervals:
                    if booked_start and booked_end:
                        try:
                            booked_start_hour = int(booked_start.split(":")[0])
                            booked_end_hour = int(booked_end.split(":")[0])
                            if booked_start_hour <= hour < booked_end_hour:
                                is_booked = True
                                break
                        except (ValueError, AttributeError):
                            continue
                if not is_booked:
                    times.append(types.InlineKeyboardButton(time_str, callback_data=f"end_time_{time_str}"))

            # Добавляем 00:00, если он доступен
            is_booked = False
            for booked_start, booked_end in booked_intervals:
                if booked_start and booked_end:
                    try:
                        booked_start_hour = int(booked_start.split(":")[0])
                        booked_end_hour = int(booked_end.split(":")[0])
                        if booked_start_hour <= 24 < booked_end_hour:
                            is_booked = True
                            break
                    except (ValueError, AttributeError):
                        continue
            if not is_booked:
                times.append(types.InlineKeyboardButton("00:00", callback_data="end_time_00:00"))

            # Если нет доступных часов для окончания
            if not times:
                markup = types.InlineKeyboardMarkup()
                back_btn = types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_booking")
                menu_btn = types.InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")
                markup.row(back_btn)
                markup.row(menu_btn)
                bot.send_message(
                    chat_id,
                    "❌ Нет доступного времени для окончания бронирования. Выберите другое время начала.",
                    reply_markup=markup
                )
                # Возвращаем к выбору времени начала
                user_data[user_id]['state'] = 'selecting_start_time'
                markup = generate_time_buttons(chat_id, 16, 23, booking_date)
                bot.send_message(
                    chat_id,
                    f"📅 Дата: {booking_date}\n\n"
                    "🕐 Выберите другое время НАЧАЛА:",
                    reply_markup=markup
                )
                return

            # Разбиваем по 4 кнопки в ряд
            for i in range(0, len(times), 4):
                markup.row(*times[i:i + 4])

            back_btn = types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_booking")
            menu_btn = types.InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")
            markup.row(back_btn)
            markup.row(menu_btn)

            bot.send_message(
                chat_id,
                f"📅 Дата: {user_data[user_id]['booking_date']}\n"
                f"🕐 Начало: {selected_time}\n\n"
                "🕐 Выберите время ОКОНЧАНИЯ бронирования:\n"
                "⏰ Минимальная продолжительность - 1 час",
                reply_markup=markup
            )

        elif call.data.startswith("end_time_") and user_data.get(user_id, {}).get('state') == 'selecting_end_time':
            # Обработка выбора времени окончания
            end_time = call.data.replace("end_time_", "")
            user_data[user_id]['booking_time_end'] = end_time
            user_data[user_id]['state'] = 'waiting_phone'

            booking_date = user_data[user_id]['booking_date']
            start_time = user_data[user_id]['booking_time_start']

            # Рассчитываем продолжительность
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

            bot.send_message(
                chat_id,
                f"📅 Дата: {booking_date}\n"
                f"🕐 Время: {start_time} - {end_time}\n"
                f"⏱ Продолжительность: {duration} час(а/ов)\n\n"
                "📱 Пожалуйста, отправьте ваш номер телефона\n"
                "или нажмите кнопку 'Ввести вручную'",
                reply_markup=markup
            )

        elif call.data == "send_name":
            name = call.from_user.first_name
            if call.from_user.last_name:
                name += " " + call.from_user.last_name
            complete_booking(user_id, name, call)

        elif call.data == "manual_name":
            if user_id not in user_data:
                user_data[user_id] = {}
            user_data[user_id]['state'] = 'waiting_name'

            markup = types.InlineKeyboardMarkup()
            back_btn = types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_booking")
            menu_btn = types.InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")
            markup.row(back_btn)
            markup.row(menu_btn)

            bot.send_message(chat_id, "✏️ Введите ваше имя:", reply_markup=markup)

        elif call.data == "books":
            show_my_bookings(chat_id, user_id)

        elif call.data.startswith("cancel_"):
            # Обработка отмены брони
            booking_id = int(call.data.replace("cancel_", ""))

            if cancel_booking(booking_id, user_id):
                bot.send_message(
                    chat_id,
                    f"✅ Бронь #{booking_id} успешно отменена!"
                )
                # Отправляем уведомление админам об отмене
                admin_message = f"❌ Бронь #{booking_id} отменена пользователем {user_id}"
                notify_admins(admin_message)
                # Обновляем список броней через небольшую задержку
                time.sleep(0.5)
                show_my_bookings(chat_id, user_id)
            else:
                bot.send_message(
                    chat_id,
                    f"❌ Не удалось отменить бронь #{booking_id}. Возможно, она уже была отменена."
                )

    except Exception as e:
        logger.error(f"Ошибка в callback: {e}")
        try:
            if hasattr(call, 'message') and hasattr(call.message, 'chat'):
                bot.send_message(call.message.chat.id, "⚠️ Произошла ошибка. Пожалуйста, попробуйте еще раз.")
        except:
            pass


def show_booking_dates(chat_id):
    """Показывает выбор даты для бронирования"""
    tomorrow_date1 = (datetime.now() + timedelta(days=1)).strftime("%d.%m.%Y")
    tomorrow_date2 = (datetime.now() + timedelta(days=2)).strftime("%d.%m.%Y")
    tomorrow_date3 = (datetime.now() + timedelta(days=3)).strftime("%d.%m.%Y")
    tomorrow_date4 = (datetime.now() + timedelta(days=4)).strftime("%d.%m.%Y")
    tomorrow_date5 = (datetime.now() + timedelta(days=5)).strftime("%d.%m.%Y")
    tomorrow_date6 = (datetime.now() + timedelta(days=6)).strftime("%d.%m.%Y")
    tomorrow_date7 = (datetime.now() + timedelta(days=7)).strftime("%d.%m.%Y")

    btn6 = types.InlineKeyboardButton(f"{tomorrow_date1}", callback_data="date_tomorrow")
    btn7 = types.InlineKeyboardButton(f"{tomorrow_date2}", callback_data="date_1day_after")
    btn8 = types.InlineKeyboardButton(f"{tomorrow_date3}", callback_data="date_2day_after")
    btn9 = types.InlineKeyboardButton(f"{tomorrow_date4}", callback_data="date_3day_after")
    btn10 = types.InlineKeyboardButton(f"{tomorrow_date5}", callback_data="date_4day_after")
    btn11 = types.InlineKeyboardButton(f"{tomorrow_date6}", callback_data="date_5day_after")
    btn12 = types.InlineKeyboardButton(f"{tomorrow_date7}", callback_data="date_6day_after")

    back_btn = types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.row(btn6)
    markup.row(btn7)
    markup.row(btn8)
    markup.row(btn9)
    markup.row(btn10)
    markup.row(btn11)
    markup.row(btn12)
    markup.row(back_btn)

    bot.send_message(chat_id, "📅 Выберите дату бронирования:", reply_markup=markup)


@bot.message_handler(content_types=['text', 'contact'])
def handle_messages(message):
    user_id = message.from_user.id

    # Проверяем, есть ли текст в сообщении
    if not message.text:
        # Если сообщение не содержит текст, проверяем, может это контакт
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
                btn_name = types.InlineKeyboardButton("👤 Отправить имя из профиля", callback_data="send_name")
                markup.row(btn_name)
                btn_manual_name = types.InlineKeyboardButton("✏️ Ввести имя вручную", callback_data="manual_name")
                markup.row(btn_manual_name)
                back_btn = types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_booking")
                menu_btn = types.InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")
                markup.row(back_btn)
                markup.row(menu_btn)

                bot.send_message(
                    message.chat.id,
                    f"Теперь введите ваше имя или нажмите кнопку:",
                    reply_markup=markup
                )
            return
        else:
            bot.send_message(message.chat.id, "⚠️ Пожалуйста, используйте кнопки для взаимодействия с ботом.")
            return

    if message.text == "🔙 Назад в меню":
        safe_delete_message(message.chat.id, message.message_id)
        if user_id in user_data:
            user_data.pop(user_id, None)
        show_main_menu(message.chat.id)
        return

    # Обработка ввода номера вручную
    if user_id in user_data and user_data[user_id].get('state') == 'waiting_phone':
        phone = message.text.strip()
        if any(char.isdigit() for char in phone):
            user_data[user_id]['phone'] = phone
            user_data[user_id]['state'] = 'waiting_name'
            markup_remove = types.ReplyKeyboardRemove()

            safe_delete_message(message.chat.id, message.message_id)

            bot.send_message(message.chat.id, f"✅ Номер сохранён: {phone}", reply_markup=markup_remove)

            markup = types.InlineKeyboardMarkup(row_width=1)
            btn_name = types.InlineKeyboardButton("👤 Отправить имя из профиля", callback_data="send_name")
            markup.row(btn_name)
            btn_manual_name = types.InlineKeyboardButton("✏️ Ввести имя вручную", callback_data="manual_name")
            markup.row(btn_manual_name)
            back_btn = types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_booking")
            menu_btn = types.InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")
            markup.row(back_btn)
            markup.row(menu_btn)

            bot.send_message(
                message.chat.id,
                f"Теперь введите ваше имя или нажмите кнопку:",
                reply_markup=markup
            )
        else:
            bot.send_message(message.chat.id, "❌ Пожалуйста, введите корректный номер телефона (только цифры и знак +)")
        return

    # Обработка ввода имени
    if user_id in user_data and user_data[user_id].get('state') == 'waiting_name':
        name = message.text.strip()
        if len(name) >= 2:
            safe_delete_message(message.chat.id, message.message_id)
            complete_booking(user_id, name)
        else:
            bot.send_message(message.chat.id, "❌ Имя должно содержать хотя бы 2 символа. Попробуйте ещё раз:")
        return

    # Если пользователь ввел что-то непонятное
    if user_id in user_data:
        bot.send_message(message.chat.id, "⚠️ Я вас не понимаю. Пожалуйста, используйте кнопки для взаимодействия.")
    else:
        # Если пользователь не в процессе диалога, отправляем в главное меню
        show_main_menu(message.chat.id)


if __name__ == "__main__":
    try:
        logger.info("🤖 Бот запущен и готов к работе!")
        bot.polling(none_stop=True)
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
