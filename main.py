import telebot
from telebot import *
import webbrowser
from pyexpat.errors import messages
import sqlite3
from datetime import datetime, timedelta
user_data = {}

bot=telebot.TeleBot("8889296379:AAF0B3-SGaOQuvQuOzMsjqKyfMZ9x3UAX_o")
name=None

ADMINS = [819284226]





def init_db():

    conn=sqlite3.connect("bookings.db")
    cur=conn.cursor()

    cur.execute('''CREATE TABLE IF NOT EXISTS bookings (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,username TEXT,first_name TEXT,last_name TEXT,phone TEXT,booking_date TEXT,created_at TEXT)''')
    conn.commit()
    cur.close()
init_db()




def add_booking(user_id, username, first_name, last_name, phone,booking_date):
    conn = sqlite3.connect('bookings.db')
    cursor = conn.cursor()
    cursor.execute('''INSERT INTO bookings (user_id, username, first_name, last_name, phone, booking_date, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)''', \
                   (user_id,username,first_name,last_name,phone,booking_date,datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()


def complete_booking(user_id, name, call=None):
    # Получаем данные пользователя
    user_data_item = user_data.get(user_id, {})
    booking_date = user_data_item.get('booking_date')
    phone = user_data_item.get('phone')

    if not booking_date or not phone:
        bot.send_message(user_id, "❌ Ошибка! Попробуйте начать заново.")
        return

    add_booking(user_id=user_id,username=call.from_user.username if call else None,first_name=name,last_name="",phone=phone,booking_date=booking_date)

    for admin_id in ADMINS:
        try:
            bot.send_message(admin_id,f"НОВАЯ БРОНЬ!\n\n"f"Имя: {name}\n"f"Телефон: {phone}\n"f"Username: @{call.from_user.username if call else 'нет'}\n"f"ID: {user_id}\n"f"Дата: {booking_date}")
        except Exception as e:
            print(f"Ошибка отправки админу: {e}")


    bot.send_message(user_id,f"✅ Бронь подтверждена!\n\n"f"📅 Дата: {booking_date}\n"f"👤 Имя: {name}\n"f"📱 Телефон: {phone}\n\n"f"Скоро с вами свяжется менеджер.")
    user_data.pop(user_id, None)


@bot.message_handler(func=lambda message: message.text == "✏️ Ввести номер вручную")
def manual_phone_input(message):
    user_id = message.from_user.id
    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]['state'] = 'waiting_phone'

    bot.send_message(message.chat.id,"📱 Введите ваш номер телефона в формате:\n""Пример: +7 999 123-45-67 или 89991234567")

@bot.message_handler(commands=["start"])
def main(message):
    markup = types.InlineKeyboardMarkup()  # создаём кнопку

    btn1=types.InlineKeyboardButton("Тарифы",callback_data="tariffs")  # добавляем кнопку
    btn2 = types.InlineKeyboardButton("Забронировать стол", callback_data="bron")
    btn3 = types.InlineKeyboardButton("Мои брони", callback_data="books")
    btn4 = types.InlineKeyboardButton("Правила посещения", callback_data="rules")
    btn5 = types.InlineKeyboardButton("Юридическая информация", callback_data="info")

    markup.row(btn1)
    markup.row(btn2)
    markup.row(btn3)
    markup.row(btn4)
    markup.row(btn5)


    bot.send_message(message.chat.id, f"Привет,{message.from_user.first_name}! \n\nУ нас есть комфортные столы, приятная атмосфера и вкусный бар."\
                                      f" Ждём тебя на игру! \n\nЧто хочешь сделать?", reply_markup=markup)





@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    markup = types.InlineKeyboardMarkup()
    if call.data == "tariffs":
        bot.send_message(call.message.chat.id, "1 час — 600 ₽\n2 часа — 1200 ₽\n3 часа — 1800 ₽")


    elif call.data == "rules":
        bot.send_message(call.message.chat.id, "Со своим нельзя \nСвоё пиво,лимонад,кофе и еду приносить запрещено.   \n\nПробковый сбор \nЗа крпкий алкоголь - 300₽ с человека. \n\nНа бильярдный стол напитки и еду ставить запрещено   \n\nПорча бильярдного стола \nШтраф за порчу бильярдного стола - 30 000₽  \n\nПорча кия  \nШтраф за порчу кия - 7000₽  \n\nПорча шаров  \nШтраф за порчу шаров - 5000₽ ")

    elif call.data == "bron":

        tomorrow_date1 = (datetime.now() + timedelta(days=1)).strftime("%d.%m.%Y")
        tomorrow_date2 = (datetime.now() + timedelta(days=2)).strftime("%d.%m.%Y")
        tomorrow_date3 = (datetime.now() + timedelta(days=3)).strftime("%d.%m.%Y")
        tomorrow_date4 = (datetime.now() + timedelta(days=4)).strftime("%d.%m.%Y")
        tomorrow_date5 = (datetime.now() + timedelta(days=5)).strftime("%d.%m.%Y")
        tomorrow_date6 = (datetime.now() + timedelta(days=6)).strftime("%d.%m.%Y")
        tomorrow_date7 = (datetime.now() + timedelta(days=7)).strftime("%d.%m.%Y")

        btn6 = types.InlineKeyboardButton(f"{tomorrow_date1}", callback_data="tomorrow")  # добавляем кнопку
        btn7 = types.InlineKeyboardButton(f"{tomorrow_date2}", callback_data="1day_after")  # добавляем кнопку
        btn8 = types.InlineKeyboardButton(f"{tomorrow_date3}", callback_data="2day_after")  # добавляем кнопку
        btn9 = types.InlineKeyboardButton(f"{tomorrow_date4}", callback_data="3day_after")  # добавляем кнопку
        btn10 = types.InlineKeyboardButton(f"{tomorrow_date5}", callback_data="4day_after")  # добавляем кнопку
        btn11 = types.InlineKeyboardButton(f"{tomorrow_date6}", callback_data="5day_after")  # добавляем кнопку
        btn12 = types.InlineKeyboardButton(f"{tomorrow_date7}", callback_data="6day_after")  # добавляем кнопку

        markup.row(btn6)
        markup.row(btn7)
        markup.row(btn8)
        markup.row(btn9)
        markup.row(btn10)
        markup.row(btn11)
        markup.row(btn12)

        bot.send_message(call.message.chat.id, "Выбери дату",reply_markup=markup)



    elif call.data in ["tomorrow", "1day_after", "2day_after", "3day_after", "4day_after", "5day_after", "6day_after"]:
        days_map = {"tomorrow": 1,"1day_after": 2,"2day_after": 3,"3day_after": 4,"4day_after": 5,"5day_after": 6,"6day_after": 7}

        days = days_map[call.data]

        booking_date = (datetime.now() + timedelta(days=days)).strftime("%d.%m.%Y")

        user_data[call.from_user.id] = {'booking_date': booking_date}

        markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)

        btn_phone = types.KeyboardButton("📱 Отправить номер телефона",request_contact=True)

        markup.add(btn_phone)

        btn_manual = types.KeyboardButton("✏️ Ввести номер вручную")

        markup.add(btn_manual)

        # ✅ ОДНО СООБЩЕНИЕ

        bot.send_message(call.message.chat.id,f"📱 Пожалуйста, отправьте ваш номер телефона\n"f"или нажмите кнопку 'Ввести вручную'",reply_markup=markup)


    elif call.data == "send_phone":
        bot.send_message(call.message.chat.id,"📱 Нажмите кнопку 'Отправить контакт' внизу экрана")




    elif call.data == "send_name":
        name = call.from_user.first_name
        if call.from_user.last_name:
            name += " " + call.from_user.last_name

        complete_booking(call.from_user.id, name, call)



    elif call.data == "manual_name":

        user_id = call.from_user.id

        # ✅ ПРОВЕРЯЕМ, ЕСТЬ ЛИ ПОЛЬЗОВАТЕЛЬ В user_data

        if user_id not in user_data:
            user_data[user_id] = {}

        user_data[user_id]['state'] = 'waiting_name'

        bot.send_message(call.message.chat.id, "✏️ Введите ваше имя:")

    elif call.data == "books":
        conn = sqlite3.connect('bookings.db')
        cursor = conn.cursor()
        cursor.execute('SELECT booking_date, created_at FROM bookings WHERE user_id = ? ORDER BY created_at DESC',
                       (call.from_user.id,))
        bookings = cursor.fetchall()
        conn.close()

        if bookings:
            text = "📋 Ваши брони:\n\n"
            for i, (date, created) in enumerate(bookings, 1):
                text += f"{i}. 📅 {date} (забронировано: {created[:16]})\n"
            bot.send_message(call.message.chat.id, text)
        else:
            bot.send_message(call.message.chat.id, "📋 У вас пока нет бронирований.")



@bot.message_handler(content_types=['text', 'contact'])
def handle_messages(message):
    user_id = message.from_user.id

    if message.contact:
        phone = message.contact.phone_number

        if user_id in user_data and 'booking_date' in user_data[user_id]:
            user_data[user_id]['phone'] = phone

            # ✅ УБИРАЕМ КЛАВИАТУРУ
            markup_remove = types.ReplyKeyboardRemove()
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

            bot.send_message(
                message.chat.id,
                f"Теперь введите ваше имя или нажмите кнопку:",
                reply_markup=markup
            )

    if user_id in user_data and user_data[user_id].get('state') == 'waiting_phone':
        phone = message.text.strip()

        if any(char.isdigit() for char in phone):
            user_data[user_id]['phone'] = phone
            user_data[user_id]['state'] = 'waiting_name'
            markup_remove = types.ReplyKeyboardRemove()
            bot.send_message(message.chat.id,f"✅ Номер сохранён: {phone}",reply_markup=markup_remove)

            markup = types.InlineKeyboardMarkup(row_width=1)
            btn_name = types.InlineKeyboardButton("👤 Отправить имя из профиля", callback_data="send_name")
            markup.row(btn_name)

            btn_manual_name = types.InlineKeyboardButton("✏️ Ввести имя вручную", callback_data="manual_name")
            markup.row(btn_manual_name)

            bot.send_message(message.chat.id,f"Теперь введите ваше имя или нажмите кнопку:",reply_markup=markup)


    if user_id in user_data and user_data[user_id].get('state') == 'waiting_name':
        name = message.text.strip()

        if len(name) >= 2:
            complete_booking(user_id, name)
        else:
            bot.send_message(message.chat.id,"❌ Имя должно содержать хотя бы 2 символа. Попробуйте ещё раз:")








init_db()
bot.polling(none_stop=True)