import os
import telebot
from telebot import types
import re
import time
import base64
import io

import config
import db
import checker
import generator
import scheduler
import locales
from flask import Flask, send_from_directory, Response
from threading import Thread

app = Flask(__name__)

@app.route('/')
def home():
    return "Бот активен"


@app.route('/favicon.ico')
def favicon():
    """Serve favicon from static folder if present, otherwise return a tiny inline PNG."""
    static_dir = os.path.join(os.path.dirname(__file__), 'static')
    ico_path = os.path.join(static_dir, 'favicon.ico')
    try:
        if os.path.exists(ico_path):
            return send_from_directory(static_dir, 'favicon.ico')
    except Exception:
        pass

    # Fallback 1x1 transparent PNG
    png_b64 = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII='
    png = base64.b64decode(png_b64)
    return Response(png, mimetype='image/png')


def run():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))

Thread(target=run).start()

user_recent_suggestions = {}

# Initialize the bot
bot = telebot.TeleBot(config.BOT_TOKEN)

# Initialize database tables on startup
db.init_db()

# Start background trap checker scheduler
scheduler.start_scheduler(bot)

# Helper function to generate main menu keyboard
def get_main_menu_keyboard(lang):
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_5 = types.InlineKeyboardButton(locales.get(lang, 'btn_5_letters'), callback_data="menu_5_letters")
    btn_6 = types.InlineKeyboardButton(locales.get(lang, 'btn_6_letters'), callback_data="menu_6_letters")
    btn_7 = types.InlineKeyboardButton(locales.get(lang, 'btn_7_letters'), callback_data="menu_7_letters")
    btn_8 = types.InlineKeyboardButton(locales.get(lang, 'btn_8_letters'), callback_data="menu_8_letters")
    btn_filter = types.InlineKeyboardButton(locales.get(lang, 'btn_filter'), callback_data="menu_filter")
    btn_trap = types.InlineKeyboardButton(locales.get(lang, 'btn_trap'), callback_data="menu_trap")
    btn_ref = types.InlineKeyboardButton(locales.get(lang, 'btn_ref'), callback_data="menu_ref")
    btn_lang = types.InlineKeyboardButton(locales.get(lang, 'btn_lang'), callback_data="menu_lang")
    
    markup.add(btn_5, btn_6)
    markup.add(btn_7, btn_8)
    markup.add(btn_filter, btn_trap)
    markup.add(btn_ref, btn_lang)
    return markup

# Helper function to generate 5/6/7/8 letter menu keyboard
def get_letters_menu_keyboard(lang, length):
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_no_digits = types.InlineKeyboardButton(locales.get(lang, 'btn_no_digits'), callback_data=f"search_{length}_no_digits")
    btn_digits = types.InlineKeyboardButton(locales.get(lang, 'btn_digits'), callback_data=f"search_{length}_digits")
    btn_back = types.InlineKeyboardButton(locales.get(lang, 'btn_back'), callback_data="main_menu")
    
    markup.add(btn_no_digits, btn_digits)
    markup.add(btn_back)
    return markup

# Helper function to generate premium menu keyboard
def get_premium_promo_keyboard(lang):
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_buy = types.InlineKeyboardButton(locales.get(lang, 'btn_buy_premium'), callback_data="buy_premium")
    btn_back = types.InlineKeyboardButton(locales.get(lang, 'btn_back'), callback_data="main_menu")
    markup.add(btn_buy, btn_back)
    return markup

# Commands
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    username = message.from_user.username or f"User_{user_id}"
    db.add_user(user_id, username)
    user = db.get_user(user_id)
    lang = user['language'] if user else 'ru'
    
    parts = message.text.split()
    if len(parts) > 1 and parts[1].startswith("ref_"):
        try:
            referrer_id = int(parts[1].split("_")[1])
            if referrer_id != user_id:
                success = db.add_referral(referrer_id, user_id)
                if success:
                    ref_user = db.get_user(referrer_id)
                    if ref_user:
                        ref_lang = ref_user['language']
                        count = ref_user['referrals_count'] + 1
                        try:
                            if count == 3:
                                db.grant_referral_premium(referrer_id)
                                bot.send_message(referrer_id, locales.get(ref_lang, 'ref_premium_granted'), parse_mode="HTML")
                            else:
                                bot.send_message(referrer_id, locales.get(ref_lang, 'ref_success', count=count), parse_mode="HTML")
                        except:
                            pass
        except:
            pass
            
    welcome_text = locales.get(lang, 'welcome', name=message.from_user.first_name)
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(locales.get(lang, 'btn_search'), callback_data="main_menu"))
    
    bot.send_message(message.chat.id, welcome_text, parse_mode="HTML", reply_markup=markup)
    if user and user.get('premium_expired') == 1:
        bot.send_message(message.chat.id, locales.get(lang, 'premium_expired'), parse_mode="HTML")

@bot.message_handler(commands=['gift_premium'])
def gift_premium(message):
    """
    Developer command to easily toggle Premium status for testing purposes.
    """
    user_id = message.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        db.add_user(user_id, message.from_user.username or f"User_{user_id}")
        user = db.get_user(user_id)
        
    current_status = user['is_premium']
    new_status = 0 if current_status == 1 else 1
    if new_status == 1:
        db.set_premium(user_id, True, premium_source='developer')
    else:
        db.set_premium(user_id, False, premium_source='none')
    
    status_text = "АКТИВИРОВАН ⭐" if new_status == 1 else "ДЕАКТИВИРОВАН ❌"
    bot.send_message(
        message.chat.id,
        f"🛠 <b>Режим разработчика</b>\n\n"
        f"Ваш Premium-статус изменен!\n"
        f"Текущий статус: <b>{status_text}</b>\n\n"
        f"Используйте /start для возврата к поиску.",
        parse_mode="HTML"
    )

def get_admin_menu_markup():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"))
    markup.add(types.InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast"))
    markup.add(types.InlineKeyboardButton("⭐ Управление Premium", callback_data="admin_premium"))
    markup.add(types.InlineKeyboardButton("🔄 Обновить словарь", callback_data="admin_refresh_dict"))
    markup.add(types.InlineKeyboardButton("🧹 Управление ловушками", callback_data="admin_manage_traps"))
    markup.add(types.InlineKeyboardButton("👥 Пользователи и рефералы", callback_data="admin_users"))
    return markup


def send_admin_menu(message):
    admin_text = "🛠 <b>Панель Администратора</b>\n\nВыберите действие:"
    markup = get_admin_menu_markup()
    bot.send_message(message.chat.id, admin_text, parse_mode="HTML", reply_markup=markup)


def edit_admin_menu(message):
    admin_text = "🛠 <b>Панель Администратора</b>\n\nВыберите действие:"
    markup = get_admin_menu_markup()
    bot.edit_message_text(admin_text, message.chat.id, message.message_id, parse_mode="HTML", reply_markup=markup)


def render_admin_trap_panel(message):
    traps = db.get_active_traps()
    if not traps:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("◀️ Назад в админку", callback_data="admin_back"))
        bot.edit_message_text(
            "🧹 <b>Управление активными ловушками</b>\n\nАктивных ловушек пока нет.",
            message.chat.id,
            message.message_id,
            parse_mode="HTML",
            reply_markup=markup
        )
        return

    trap_lines = "\n".join(
        f"• <code>@{trap['username']}</code> — пользователь <code>{trap['user_id']}</code> (id {trap['id']})"
        for trap in traps[:10]
    )
    traps_text = (
        f"🧹 <b>Управление активными ловушками</b>\n\n"
        f"Всего активных ловушек: <b>{len(traps)}</b>\n\n"
        f"{trap_lines}"
    )
    markup = types.InlineKeyboardMarkup(row_width=1)
    for trap in traps[:10]:
        markup.add(types.InlineKeyboardButton(
            f"❌ Отключить @{trap['username']}",
            callback_data=f"admin_deactivate_trap_{trap['id']}"
        ))
    markup.add(types.InlineKeyboardButton("◀️ Назад в админку", callback_data="admin_back"))
    bot.edit_message_text(traps_text, message.chat.id, message.message_id, parse_mode="HTML", reply_markup=markup)


@bot.message_handler(commands=['admin'])
def admin_panel(message):
    user_id = message.from_user.id
    if user_id != config.ADMIN_ID:
        return
    send_admin_menu(message)


@bot.message_handler(commands=['refresh_dict'])
def refresh_dictionary_command(message):
    # Admin-only: force refresh the dictionary DB from upstream sources
    user_id = message.from_user.id
    if user_id != config.ADMIN_ID:
        return

    bot.send_message(message.chat.id, "🔁 Обновляю базу слов... это может занять некоторое время.")
    try:
        db.populate_dictionary(force=True)
        bot.send_message(message.chat.id, "✅ База слов успешно обновлена.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка при обновлении базы слов: {e}")

# Callback queries
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    # Ensure user exists in database
    db.add_user(user_id, call.from_user.username or f"User_{user_id}")
    user = db.reset_daily_attempts_if_needed(user_id)
    # Acknowledge callback immediately to avoid client waiting state
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass

    # Log callback for debugging
    try:
        print(f"Callback received: {call.data} from {user_id}")
    except Exception:
        pass
    
    if user and user.get('premium_expired') == 1:
        bot.send_message(call.message.chat.id, locales.get(user['language'] if user else 'ru', 'premium_expired'), parse_mode="HTML")

    # Handle back to welcome screen
    if call.data == "welcome_screen":
        welcome_text = (
            f"👋 <b>Рады видеть вас снова!</b>\n\n"
            f"Каждый найденный ник проходит автоматическую двойную проверку:\n"
            f"• <b>Telegram</b> — не занят ли профилем, каналом или ботом\n"
            f"• <b>Fragment</b> — не выставлен ли на аукцион или продажу\n\n"
            f"Используйте кнопку ниже, чтобы зайти в раздел поиска 👇"
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔎 Перейти к поиску", callback_data="main_menu"))
        bot.edit_message_text(welcome_text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)
        return

    # Handle main menu
    elif call.data == "main_menu":
        lang = user['language'] if user else 'ru'
        attempts_text = locales.get(lang, 'unlimited') if user['is_premium'] == 1 else f"{user['attempts_left']} шт."
        main_menu_text = locales.get(lang, 'main_menu_text', attempts=attempts_text)
        bot.edit_message_text(main_menu_text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=get_main_menu_keyboard(lang))

    # Handle 5 letters menu
    elif call.data == "menu_5_letters":
        lang = user['language'] if user else 'ru'
        attempts_text = locales.get(lang, 'unlimited') if user['is_premium'] == 1 else f"{user['attempts_left']} шт."
        menu_text = locales.get(lang, 'menu_5_letters_text', attempts=attempts_text)
        bot.edit_message_text(menu_text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=get_letters_menu_keyboard(lang, 5))

    # Handle 6 letters menu
    elif call.data == "menu_6_letters":
        lang = user['language'] if user else 'ru'
        attempts_text = locales.get(lang, 'unlimited') if user['is_premium'] == 1 else f"{user['attempts_left']} шт."
        menu_text = locales.get(lang, 'menu_6_letters_text', attempts=attempts_text)
        bot.edit_message_text(menu_text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=get_letters_menu_keyboard(lang, 6))

    elif call.data == "menu_7_letters":
        lang = user['language'] if user else 'ru'
        attempts_text = locales.get(lang, 'unlimited') if user['is_premium'] == 1 else f"{user['attempts_left']} шт."
        menu_text = locales.get(lang, 'menu_7_letters_text', attempts=attempts_text)
        bot.edit_message_text(menu_text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=get_letters_menu_keyboard(lang, 7))

    elif call.data == "menu_8_letters":
        lang = user['language'] if user else 'ru'
        attempts_text = locales.get(lang, 'unlimited') if user['is_premium'] == 1 else f"{user['attempts_left']} шт."
        menu_text = locales.get(lang, 'menu_8_letters_text', attempts=attempts_text)
        bot.edit_message_text(menu_text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=get_letters_menu_keyboard(lang, 8))

    # Handle searches
    elif call.data.startswith("search_"):
        # Format: search_{length}_{digits/no_digits}
        pattern = r"search_(\d+)_(digits|no_digits)"
        match = re.match(pattern, call.data)
        if match:
            length = int(match.group(1))
            include_digits = match.group(2) == "digits"
            
            # Check attempts
            lang = user['language'] if user else 'ru'
            if user['is_premium'] == 0 and user['attempts_left'] <= 0:
                out_of_attempts_text = locales.get(lang, 'out_of_attempts')
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton(locales.get(lang, 'btn_buy_premium'), callback_data="buy_premium"))
                markup.add(types.InlineKeyboardButton(locales.get(lang, 'btn_back'), callback_data="main_menu"))
                bot.edit_message_text(out_of_attempts_text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)
                return
                
            # Perform checking in progress
            loading_message = bot.send_message(
                call.message.chat.id,
                locales.get(lang, 'loading_check'),
                parse_mode="HTML"
            )
            
            # Decrement attempt if free
            if user['is_premium'] == 0:
                db.use_attempt(user_id)
                # Update user variable
                user = db.get_user(user_id)
                
            found = False
            max_tries = config.MAX_USERNAME_SEARCH_TRIES
            
            for try_idx in range(1, max_tries + 1):
                if try_idx % 50 == 0:
                    try:
                        bot.edit_message_text(
                            locales.get(lang, 'loading_progress', checked=try_idx, total=max_tries),
                            call.message.chat.id, loading_message.message_id, parse_mode="HTML"
                        )
                    except telebot.apihelper.ApiTelegramException:
                        pass
                
                # Generate username
                test_username = generator.generate_username(length, include_digits)
                
                if test_username in user_recent_suggestions.get(user_id, set()):
                    continue
                
                # Check status
                available = checker.is_username_available(test_username)
                
                if available is True:
                    # Found one!
                    rating = generator.rate_username(test_username)
                    stars = "⭐" * int(rating/2) if rating >= 2 else "⭐"
                    
                    # Update status
                    warning = locales.get(lang, 'warning_5_letters') if length == 5 and not include_digits else ""
                    
                    success_text = locales.get(lang, 'success_found', username=test_username, rating=rating, stars=stars, warning=warning)
                    
                    # Delete loading and send result
                    bot.delete_message(call.message.chat.id, loading_message.message_id)
                    
                    markup = types.InlineKeyboardMarkup()
                    markup.add(types.InlineKeyboardButton(locales.get(lang, 'btn_search_more'), callback_data=call.data))
                    markup.add(types.InlineKeyboardButton(locales.get(lang, 'btn_back'), callback_data="main_menu"))
                    
                    bot.send_message(call.message.chat.id, success_text, parse_mode="HTML", reply_markup=markup)
                    user_recent_suggestions.setdefault(user_id, set()).add(test_username)
                    found = True
                    break
                elif available is None:
                    # Rate limit or network error, wait a bit longer
                    time.sleep(1.0)
                else:
                    # Taken, continue loop
                    time.sleep(config.CHECK_COOLDOWN)
                    
            if not found:
                fail_text = locales.get(lang, 'fail_not_found', max=max_tries)
                bot.delete_message(call.message.chat.id, loading_message.message_id)
                
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton(locales.get(lang, 'btn_retry'), callback_data=call.data))
                markup.add(types.InlineKeyboardButton(locales.get(lang, 'btn_back'), callback_data="main_menu"))
                
                bot.send_message(call.message.chat.id, fail_text, parse_mode="HTML", reply_markup=markup)

    # Handle Filter menu
    elif call.data == "menu_filter":
        lang = user['language'] if user else 'ru'
        if user['is_premium'] == 1:
            filter_menu_text = locales.get(lang, 'filter_premium_text')
            markup = types.InlineKeyboardMarkup(row_width=1)
            btn_mask = types.InlineKeyboardButton(locales.get(lang, 'btn_mask'), callback_data="filter_by_mask")
            btn_rating = types.InlineKeyboardButton(locales.get(lang, 'btn_rating'), callback_data="filter_by_rating")
            btn_theme = types.InlineKeyboardButton(locales.get(lang, 'btn_theme'), callback_data="filter_by_theme")
            btn_word = types.InlineKeyboardButton(locales.get(lang, 'btn_word'), callback_data="filter_by_word")
            btn_back = types.InlineKeyboardButton(locales.get(lang, 'btn_back'), callback_data="main_menu")
            markup.add(btn_mask, btn_rating, btn_theme, btn_word, btn_back)
            bot.edit_message_text(filter_menu_text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)
        else:
            promo_text = locales.get(lang, 'filter_promo_text')
            bot.edit_message_text(promo_text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=get_premium_promo_keyboard(lang))

    # Filter: Mask choice
    elif call.data == "filter_by_mask":
        filter_text = (
            f"🔍 <b>Фильтр по маске</b>\n\n"
            f"Введите маску, по которой бот будет подбирать свободный ник.\n\n"
            f"📝 <b>Правила маски:</b>\n"
            f"• <code>?</code> — любая буква (a-z)\n"
            f"• <code>#</code> — любая цифра (0-9)\n"
            f"• <code>*</code> — буква или цифра\n"
            f"• Любые другие символы будут искаться как есть.\n\n"
            f"Пример: <code>a?b#c</code> (поиск свободных ников типа: a<b>x</b>b<b>7</b>c)\n"
            f"<i>Минимальная длина маски — 5 символов.</i>\n\n"
            f"👉 <b>Отправьте маску сообщением в чат:</b>"
        )
        lang = user['language'] if user else 'ru'
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton(locales.get(lang, 'btn_back'), callback_data="menu_filter"))
        sent_msg = bot.edit_message_text(filter_text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)
        bot.register_next_step_handler(sent_msg, process_filter_mask)

    # Filter: Word search
    elif call.data == "filter_by_word":
        lang = user['language'] if user else 'ru'
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton(locales.get(lang, 'btn_back'), callback_data="menu_filter"))
        sent_msg = bot.edit_message_text(locales.get(lang, 'word_search_prompt'), call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)
        bot.register_next_step_handler(sent_msg, process_word_search)

    # Filter: Rating choice menu
    elif call.data == "filter_by_rating":
        lang = user['language'] if user else 'ru'
        rating_text = (
            f"⭐ <b>Поиск по рейтингу редкости</b>\n\n"
            f"Бот анализирует генерируемые имена по словарной базе "
            f"(совпадение слов, слияния, корни слов) и фонетическим правилам.\n\n"
            f"Выберите минимальный уровень редкости юзернейма:"
        )
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn_7 = types.InlineKeyboardButton("⭐ 7/10 и выше", callback_data="select_rating_7")
        btn_8 = types.InlineKeyboardButton("⭐ 8/10 и выше", callback_data="select_rating_8")
        btn_9 = types.InlineKeyboardButton("⭐ 9/10 и выше", callback_data="select_rating_9")
        btn_10 = types.InlineKeyboardButton("⭐ 10/10 (Только слова)", callback_data="select_rating_10")
        btn_back = types.InlineKeyboardButton(locales.get(lang, 'btn_back'), callback_data="menu_filter")
        markup.add(btn_7, btn_8)
        markup.add(btn_9, btn_10)
        markup.add(btn_back)
        bot.edit_message_text(rating_text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

    # Filter: Theme choice menu
    elif call.data == "filter_by_theme":
        lang = user['language'] if user else 'ru'
        theme_text = locales.get(lang, 'theme_menu_text')
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton(locales.get(lang, 'btn_theme_crypto'), callback_data="theme_crypto"))
        markup.add(types.InlineKeyboardButton(locales.get(lang, 'btn_theme_gaming'), callback_data="theme_gaming"))
        markup.add(types.InlineKeyboardButton(locales.get(lang, 'btn_theme_aesthetics'), callback_data="theme_aesthetics"))
        markup.add(types.InlineKeyboardButton(locales.get(lang, 'btn_back'), callback_data="menu_filter"))
        bot.edit_message_text(theme_text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

    # Filter: Theme run
    elif call.data.startswith("theme_"):
        lang = user['language'] if user else 'ru'
        theme_name = call.data.split("_")[1]
        length = 7
        
        # Get localized theme name from button label
        theme_label_key = f'btn_theme_{theme_name}'
        theme_label = locales.get(lang, theme_label_key).split(' ', 1)[-1]  # Remove emoji
        
        loading_message = bot.send_message(
            call.message.chat.id,
            locales.get(lang, 'theme_loading', theme=theme_label),
            parse_mode="HTML"
        )
        
        found = False
        max_tries = config.MAX_USERNAME_SEARCH_TRIES
        
        for try_idx in range(1, max_tries + 1):
            if try_idx % 50 == 0:
                try:
                    bot.edit_message_text(
                        locales.get(lang, 'loading_progress', checked=try_idx, total=max_tries),
                        call.message.chat.id, loading_message.message_id, parse_mode="HTML"
                    )
                except telebot.apihelper.ApiTelegramException:
                    pass
                    
            test_username = generator.generate_thematic(theme_name, length)
            
            if test_username in user_recent_suggestions.get(user_id, set()):
                continue
                
            available = checker.is_username_available(test_username)
            if available is True:
                rating = generator.rate_username(test_username)
                stars = "⭐" * int(rating/2) if rating >= 2 else "⭐"
                
                success_text = locales.get(lang, 'success_found', username=test_username, rating=rating, stars=stars, warning="")
                
                bot.delete_message(call.message.chat.id, loading_message.message_id)
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton(locales.get(lang, 'btn_search_more'), callback_data=call.data))
                markup.add(types.InlineKeyboardButton(locales.get(lang, 'btn_back'), callback_data="menu_filter"))
                
                bot.send_message(call.message.chat.id, success_text, parse_mode="HTML", reply_markup=markup)
                user_recent_suggestions.setdefault(user_id, set()).add(test_username)
                found = True
                break
            elif available is None:
                time.sleep(1.0)
            else:
                time.sleep(config.CHECK_COOLDOWN)
                
        if not found:
            fail_text = locales.get(lang, 'fail_not_found', max=max_tries)
            bot.delete_message(call.message.chat.id, loading_message.message_id)
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton(locales.get(lang, 'btn_retry'), callback_data=call.data))
            markup.add(types.InlineKeyboardButton(locales.get(lang, 'btn_back'), callback_data="menu_filter"))
            bot.send_message(call.message.chat.id, fail_text, parse_mode="HTML", reply_markup=markup)

    # Word search: retry with same word
    elif call.data.startswith("word_again_"):
        lang = user['language'] if user else 'ru'
        clean_word = call.data.replace("word_again_", "")
        markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton(locales.get(lang, 'btn_back'), callback_data="menu_filter"))
        sent_msg = bot.send_message(
            call.message.chat.id,
            locales.get(lang, 'word_search_loading', word=clean_word),
            parse_mode="HTML",
            reply_markup=markup
        )
        # Reuse the step handler logic by simulating a message
        import types as pytypes
        fake_msg = pytypes.SimpleNamespace(
            from_user=call.from_user,
            chat=call.message.chat,
            text=clean_word
        )
        process_word_search(fake_msg)

    # Filter: Select length for rating search
    elif call.data.startswith("select_rating_"):
        min_rating = int(call.data.replace("select_rating_", ""))
        length_text = (
            f"📐 <b>Выберите длину юзернейма</b>\n\n"
            f"Вы выбрали минимальную редкость: <b>{min_rating}/10</b>\n\n"
            f"Выберите длину юзернейма для поиска:"
        )
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn_5 = types.InlineKeyboardButton("5 букв", callback_data=f"rating_len_5_{min_rating}")
        btn_6 = types.InlineKeyboardButton("6 букв", callback_data=f"rating_len_6_{min_rating}")
        btn_back = types.InlineKeyboardButton("Назад", callback_data="filter_by_rating")
        markup.add(btn_5, btn_6, btn_back)
        bot.edit_message_text(length_text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

    # Filter: Choose digits/no digits for rating search
    elif call.data.startswith("rating_len_"):
        # Format: rating_len_{length}_{min_rating}
        parts = call.data.split("_")
        length = int(parts[2])
        min_rating = int(parts[3])
        
        digits_text = (
            f"🔢 <b>Параметры поиска по редкости</b>\n\n"
            f"Длина юзернейма: <b>{length} букв</b>\n"
            f"Минимальная редкость: <b>{min_rating}/10</b>\n\n"
            f"Искать юзернеймы с цифрами или без?"
        )
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn_no_digits = types.InlineKeyboardButton("Без цифр", callback_data=f"rating_run_{length}_{min_rating}_no_digits")
        btn_digits = types.InlineKeyboardButton("С цифрами", callback_data=f"rating_run_{length}_{min_rating}_digits")
        btn_back = types.InlineKeyboardButton("Назад", callback_data=f"select_rating_{min_rating}")
        markup.add(btn_no_digits, btn_digits, btn_back)
        bot.edit_message_text(digits_text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

    # Filter: RUN RATING SEARCH
    elif call.data.startswith("rating_run_"):
        # Format: rating_run_{length}_{min_rating}_{digits/no_digits}
        parts = call.data.split("_")
        length = int(parts[2])
        min_rating = int(parts[3])
        include_digits = parts[4] == "digits"
        
        loading_message = bot.send_message(
            call.message.chat.id,
            f"🔎 <b>Запуск поиска по базам...</b>\n"
            f"Ищу свободный юзернейм ({length} букв, {'с цифрами' if include_digits else 'без цифр'}) "
            f"с редкостью <b>{min_rating}/10 и выше</b>.\n\n"
            f"<i>Это может занять некоторое время, так как мы фильтруем ники по словарям и рейтингу локально до запроса к сети.</i>",
            parse_mode="HTML"
        )
        
        found = False
        max_tries = config.MAX_USERNAME_SEARCH_TRIES
        
        for try_idx in range(1, max_tries + 1):
            if try_idx % 50 == 0:
                try:
                    bot.edit_message_text(
                        f"🔎 <b>Запуск поиска по базам...</b>\n"
                        f"Ищу свободный юзернейм ({length} букв, {'с цифрами' if include_digits else 'без цифр'}) "
                        f"с редкостью <b>{min_rating}/10 и выше</b>.\n\n"
                        f"⏳ <i>Проверено {try_idx} из {max_tries} вариантов...</i>",
                        call.message.chat.id, loading_message.message_id, parse_mode="HTML"
                    )
                except telebot.apihelper.ApiTelegramException:
                    pass

            # 1. Local generate a username aimed at the requested rarity level
            test_username = generator.generate_by_rating(length, min_rating, include_digits)
            
            if test_username in user_recent_suggestions.get(user_id, set()):
                continue
            
            # 2. Local check rating (fast, avoids HTTP spamming if rating is too low)
            rating = generator.rate_username(test_username)
            if rating < min_rating:
                continue
                
            # 3. Meets rating, now check network availability
            available = checker.is_username_available(test_username)
            
            if available is True:
                stars = "⭐" * int(rating/2) if rating >= 2 else "⭐"
                
                warning = "\n\n⚠️ <i>Внимание: Telegram часто блокирует регистрацию красивых 5-буквенных ников без цифр (ошибка «Некорректное имя»). Если занять не вышло, ищите 6 букв или с цифрами!</i>" if length == 5 and not include_digits else ""
                
                success_text = (
                    f"🎉 <b>Найден редкий свободный юзернейм!</b>\n\n"
                    f"👉 @<code>{test_username}</code>\n\n"
                    f"• <b>Рейтинг редкости:</b> {rating}/10 {stars}\n"
                    f"• <b>Telegram:</b> Свободен ✅\n"
                    f"• <b>Fragment:</b> Свободен ✅\n\n"
                    f"<i>Ник успешно проверен по базам слов и прошел двойной тест на доступность!</i>{warning}"
                )
                
                bot.delete_message(call.message.chat.id, loading_message.message_id)
                
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("🔎 Искать еще", callback_data=call.data))
                markup.add(types.InlineKeyboardButton("Назад в меню", callback_data="main_menu"))
                
                bot.send_message(call.message.chat.id, success_text, parse_mode="HTML", reply_markup=markup)
                user_recent_suggestions.setdefault(user_id, set()).add(test_username)
                found = True
                break
            elif available is None:
                time.sleep(1.0)
            else:
                time.sleep(config.CHECK_COOLDOWN)
                
        if not found:
            fail_text = (
                f"⚠️ <b>Ник с редкостью ≥ {min_rating}/10 не найден.</b>\n\n"
                f"Проверено {max_tries} вариантов. Все сгенерированные ники с таким рейтингом заняты на текущий момент.\n"
                f"Попробуйте запустить поиск снова или снизьте уровень редкости."
            )
            bot.delete_message(call.message.chat.id, loading_message.message_id)
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔁 Повторить поиск", callback_data=call.data))
            markup.add(types.InlineKeyboardButton("Назад", callback_data="filter_by_rating"))
            
            bot.send_message(call.message.chat.id, fail_text, parse_mode="HTML", reply_markup=markup)

    # Handle Trap menu
    elif call.data == "menu_trap":
        lang = user['language'] if user else 'ru'
        if user['is_premium'] == 1:
            # User is premium, show active traps and allow adding
            traps = db.get_user_traps(user_id)
            traps_text = "\n".join(f"• <code>@{t}</code>" for t in traps) if traps else "<i>(у вас пока нет активных ловушек)</i>"
                
            trap_menu_text = locales.get(lang, 'trap_menu_text', traps=traps_text)
            
            markup = types.InlineKeyboardMarkup()
            if traps:
                markup.add(types.InlineKeyboardButton("🗑 Удалить ловушку", callback_data="manage_traps"))
            markup.add(types.InlineKeyboardButton(locales.get(lang, 'btn_back'), callback_data="main_menu"))
            
            sent_msg = bot.edit_message_text(trap_menu_text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)
            bot.register_next_step_handler(sent_msg, process_trap_username)
        else:
            # Promo screen
            promo_text = locales.get(lang, 'trap_promo_text')
            bot.edit_message_text(promo_text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=get_premium_promo_keyboard(lang))
            
    # Handle Ref menu
    elif call.data == "menu_ref":
        lang = user['language'] if user else 'ru'
        count = user['referrals_count'] if user else 0
        bot_info = bot.get_me()
        bot_username = bot_info.username
        link = f"https://t.me/{bot_username}?start=ref_{user_id}"
        
        ref_text = locales.get(lang, 'ref_text', count=count, link=link)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(locales.get(lang, 'btn_back'), callback_data="main_menu"))
        bot.edit_message_text(ref_text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

    # Handle Lang menu
    elif call.data == "menu_lang":
        lang = user['language'] if user else 'ru'
        lang_text = locales.get(lang, 'lang_menu')
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn_ru = types.InlineKeyboardButton("🇷🇺 Русский", callback_data="set_lang_ru")
        btn_en = types.InlineKeyboardButton("🇬🇧 English", callback_data="set_lang_en")
        btn_back = types.InlineKeyboardButton(locales.get(lang, 'btn_back'), callback_data="main_menu")
        markup.add(btn_ru, btn_en)
        markup.add(btn_back)
        bot.edit_message_text(lang_text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)
        
    # Handle Set Lang
    elif call.data.startswith("set_lang_"):
        new_lang = call.data.split("_")[2]
        db.set_language(user_id, new_lang)
        bot.answer_callback_query(call.id, locales.get(new_lang, 'lang_saved'))
        
        # Return to main menu in new language
        attempts_text = locales.get(new_lang, 'unlimited') if user['is_premium'] == 1 else f"{user['attempts_left']} шт."
        main_menu_text = locales.get(new_lang, 'main_menu_text', attempts=attempts_text)
        bot.edit_message_text(
            main_menu_text, 
            call.message.chat.id, 
            call.message.message_id, 
            parse_mode="HTML", 
            reply_markup=get_main_menu_keyboard(new_lang)
        )

    # Manage active traps (Delete screen)
    elif call.data == "manage_traps":
        lang = user['language'] if user else 'ru'
        traps = db.get_user_traps(user_id)
        if not traps:
            bot.edit_message_text(
                "У вас нет активных ловушек.", 
                call.message.chat.id, 
                call.message.message_id, 
                reply_markup=get_main_menu_keyboard(lang)
            )
            return
            
        markup = types.InlineKeyboardMarkup(row_width=1)
        for t in traps:
            markup.add(types.InlineKeyboardButton(f"❌ Удалить @{t}", callback_data=f"delete_trap_{t}"))
        markup.add(types.InlineKeyboardButton("Назад", callback_data="menu_trap"))
        
        bot.edit_message_text("Выберите ловушку для удаления:", call.message.chat.id, call.message.message_id, reply_markup=markup)

    # Delete trap callback
    elif call.data.startswith("delete_trap_"):
        target_username = call.data.replace("delete_trap_", "")
        db.remove_trap(user_id, target_username)
        
        bot.answer_callback_query(call.id, f"Ловушка на @{target_username} удалена!")
        
        # Return to trap menu
        traps = db.get_user_traps(user_id)
        traps_text = "\n".join(f"• <code>@{t}</code>" for t in traps) if traps else "<i>(у вас пока нет активных ловушек)</i>"
        
        trap_menu_text = (
            f"📦 <b>Ловушка на ник (Мониторинг)</b>\n\n"
            f"Укажите занятый юзернейм, и как только он освободится — вы мгновенно получите оповещение!\n\n"
            f"📋 <b>Ваши активные ловушки:</b>\n"
            f"{traps_text}\n\n"
            f"👉 <b>Отправьте ник для отслеживания в чат:</b>"
        )
        markup = types.InlineKeyboardMarkup()
        if traps:
            markup.add(types.InlineKeyboardButton("🗑 Удалить ловушку", callback_data="manage_traps"))
        markup.add(types.InlineKeyboardButton("Назад", callback_data="main_menu"))
        
        bot.edit_message_text(trap_menu_text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

    # Buy premium details
    elif call.data == "buy_premium":
        lang = user['language'] if user else 'ru'
        promo_text = locales.get(lang, 'premium_promo', price=config.PREMIUM_PRICE_STARS)
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton(locales.get(lang, 'btn_pay', price=config.PREMIUM_PRICE_STARS), callback_data="pay_stars"))
        markup.add(types.InlineKeyboardButton(locales.get(lang, 'btn_back'), callback_data="main_menu"))
        bot.edit_message_text(promo_text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

    elif call.data == "pay_stars":
        bot.delete_message(call.message.chat.id, call.message.message_id)
        prices = [types.LabeledPrice(label='Premium Подписка', amount=config.PREMIUM_PRICE_STARS)]
        bot.send_invoice(
            call.message.chat.id,
            title="Premium на 1 месяц",
            description="Безлимитный поиск, фильтр по маске и ловушки на ники на 1 месяц.",
            invoice_payload="premium_subscription",
            provider_token="",
            currency="XTR",
            prices=prices,
        )

    # Admin actions
    elif call.data == "admin_refresh_dict":
        if user_id != config.ADMIN_ID: return
        bot.answer_callback_query(call.id, "Запускаю обновление словаря...")
        bot.send_message(call.message.chat.id, "🔁 Обновляю базу слов... это может занять некоторое время.")
        try:
            db.populate_dictionary(force=True)
            bot.send_message(call.message.chat.id, "✅ База слов успешно обновлена.")
        except Exception as e:
            bot.send_message(call.message.chat.id, f"❌ Ошибка при обновлении базы слов: {e}")

    elif call.data == "admin_manage_traps":
        if user_id != config.ADMIN_ID: return
        bot.answer_callback_query(call.id)
        render_admin_trap_panel(call.message)

    elif call.data.startswith("admin_deactivate_trap_"):
        if user_id != config.ADMIN_ID: return
        try:
            trap_id = int(call.data.rsplit("_", 1)[1])
            db.deactivate_trap(trap_id)
            bot.answer_callback_query(call.id, "Ловушка отключена.")
        except Exception:
            bot.answer_callback_query(call.id, "Не удалось отключить ловушку.")
        render_admin_trap_panel(call.message)

    elif call.data == "admin_users":
        if user_id != config.ADMIN_ID: return
        stats = db.get_stats()
        languages = db.get_language_distribution()
        top_referrers = db.get_top_referrers(5)

        language_lines = "\n".join(
            f"• {lang}: <b>{count}</b>" for lang, count in sorted(languages.items())
        ) or "<i>Нет данных</i>"
        referrals_lines = "\n".join(
            f"{idx}. @{row['username'] or row['user_id']} — <b>{row['referrals_count']}</b>" 
            for idx, row in enumerate(top_referrers, start=1)
        ) or "<i>Нет рефералов</i>"

        users_text = (
            f"👥 <b>Пользователи и рефералы</b>\n\n"
            f"👤 Всего пользователей: <b>{stats['total_users']}</b>\n"
            f"⭐ Premium: <b>{stats['premium_users']}</b>\n"
            f"🌐 Языки:\n{language_lines}\n\n"
            f"🏆 Топ рефералов:\n{referrals_lines}"
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("◀️ Назад в админку", callback_data="admin_back"))
        bot.answer_callback_query(call.id)
        bot.edit_message_text(users_text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

    elif call.data == "admin_stats":
        if user_id != config.ADMIN_ID: return
        stats = db.get_stats()
        stats_text = (
            f"📊 <b>Статистика бота</b>\n\n"
            f"👥 Всего пользователей: <b>{stats['total_users']}</b>\n"
            f"⭐ Premium: <b>{stats['premium_users']}</b>\n"
            f"📦 Активных ловушек: <b>{stats['active_traps']}</b>\n"
            f"🧹 Всего ловушек: <b>{stats['total_traps']}</b>\n"
            f"🔗 Всего рефералов: <b>{stats['total_referrals']}</b>"
        )
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, stats_text, parse_mode="HTML")
        
    elif call.data == "admin_broadcast":
        if user_id != config.ADMIN_ID: return
        msg = bot.send_message(call.message.chat.id, "Отправьте сообщение для рассылки всем пользователям (или напишите /cancel):")
        bot.register_next_step_handler(msg, process_admin_broadcast)
        
    elif call.data == "admin_premium":
        if user_id != config.ADMIN_ID: return
        msg = bot.send_message(call.message.chat.id, "Отправьте ID пользователя для изменения его Premium статуса (или /cancel):")
        bot.register_next_step_handler(msg, process_admin_premium)

    elif call.data == "admin_back":
        if user_id != config.ADMIN_ID: return
        bot.answer_callback_query(call.id)
        edit_admin_menu(call.message)

# Process Word Search Input
def process_word_search(message):
    user_id = message.from_user.id
    user = db.get_user(user_id)
    lang = user['language'] if user else 'ru'
    word = message.text.strip()
    
    if word.startswith("/"):
        bot.clear_step_handler_by_chat_id(message.chat.id)
        if word == "/start":
            send_welcome(message)
        return
    
    # Validate: only latin letters/digits, min 2 chars
    clean_word = ''.join(c for c in word.lower() if c.isalnum() and c.isascii())
    if len(clean_word) < 2:
        err_msg = bot.send_message(message.chat.id, locales.get(lang, 'word_search_invalid'), parse_mode="HTML")
        bot.register_next_step_handler(err_msg, process_word_search)
        return
    
    loading_msg = bot.send_message(
        message.chat.id,
        locales.get(lang, 'word_search_loading', word=clean_word),
        parse_mode="HTML"
    )
    
    found = False
    max_tries = config.MAX_USERNAME_SEARCH_TRIES
    
    for try_idx in range(1, max_tries + 1):
        if try_idx % 50 == 0:
            try:
                bot.edit_message_text(
                    locales.get(lang, 'word_search_loading', word=clean_word) + f"\n\n⏳ <i>{try_idx}/{max_tries}</i>",
                    message.chat.id, loading_msg.message_id, parse_mode="HTML"
                )
            except telebot.apihelper.ApiTelegramException:
                pass
        
        test_username = generator.generate_with_word(clean_word)
        if not test_username or len(test_username) < 5:
            continue
        
        if test_username in user_recent_suggestions.get(user_id, set()):
            continue
        
        available = checker.is_username_available(test_username)
        if available is True:
            rating = generator.rate_username(test_username)
            stars = "⭐" * int(rating/2) if rating >= 2 else "⭐"
            
            success_text = locales.get(lang, 'word_search_success',
                username=test_username, word=clean_word, rating=rating, stars=stars)
            
            bot.delete_message(message.chat.id, loading_msg.message_id)
            
            markup = types.InlineKeyboardMarkup()
            # "Try again with same word" stores word in callback
            markup.add(types.InlineKeyboardButton(
                locales.get(lang, 'btn_search_by_word_again'),
                callback_data=f"word_again_{clean_word}"
            ))
            markup.add(types.InlineKeyboardButton(
                locales.get(lang, 'btn_new_word'),
                callback_data="filter_by_word"
            ))
            markup.add(types.InlineKeyboardButton(locales.get(lang, 'btn_back'), callback_data="menu_filter"))
            
            bot.send_message(message.chat.id, success_text, parse_mode="HTML", reply_markup=markup)
            user_recent_suggestions.setdefault(user_id, set()).add(test_username)
            found = True
            break
        elif available is None:
            time.sleep(1.0)
        else:
            time.sleep(config.CHECK_COOLDOWN)
    
    if not found:
        bot.delete_message(message.chat.id, loading_msg.message_id)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(
            locales.get(lang, 'btn_search_by_word_again'),
            callback_data=f"word_again_{clean_word}"
        ))
        markup.add(types.InlineKeyboardButton(locales.get(lang, 'btn_new_word'), callback_data="filter_by_word"))
        bot.send_message(message.chat.id,
            locales.get(lang, 'word_search_fail', word=clean_word, max=max_tries),
            parse_mode="HTML", reply_markup=markup)

# Process Filter Input
def process_filter_mask(message):
    user_id = message.from_user.id
    mask = message.text.strip()
    
    # Check if back to menu command or start
    if mask.startswith("/"):
        bot.clear_step_handler_by_chat_id(message.chat.id)
        if mask == "/start":
            send_welcome(message)
        return
        
    # Validate mask length
    if len(mask) < 5:
        bot.send_message(
            message.chat.id,
            "❌ <b>Ошибка:</b> Маска должна содержать не менее 5 символов.\n"
            "Пожалуйста, пришлите другую маску или нажмите /start для возврата к меню.",
            parse_mode="HTML"
        )
        bot.register_next_step_handler(message, process_filter_mask)
        return
        
    loading_msg = bot.send_message(
        message.chat.id,
        f"🔍 <b>Ищу ник по маске:</b> <code>{mask}</code>...\n"
        f"Генерирую варианты и провожу двойной тест Telegram + Fragment.",
        parse_mode="HTML"
    )
    
    found = False
    max_tries = config.MAX_USERNAME_SEARCH_TRIES
    
    for try_idx in range(1, max_tries + 1):
        if try_idx % 50 == 0:
            try:
                bot.edit_message_text(
                    f"🔍 <b>Ищу ник по маске:</b> <code>{mask}</code>...\n"
                    f"Генерирую варианты и провожу двойной тест Telegram + Fragment.\n\n"
                    f"⏳ <i>Проверено {try_idx} из {max_tries} вариантов...</i>",
                    message.chat.id, loading_msg.message_id, parse_mode="HTML"
                )
            except telebot.apihelper.ApiTelegramException:
                pass

        test_username = generator.generate_from_mask(mask)
        
        if test_username in user_recent_suggestions.get(user_id, set()):
            continue
        
        # Safety check: if mask resulted in invalid/empty username, skip
        if len(test_username) < 5:
            continue
            
        available = checker.is_username_available(test_username)
        if available is True:
            rating = generator.rate_username(test_username)
            stars = "⭐" * int(rating/2) if rating >= 2 else "⭐"
            
            warning = "\n\n⚠️ <i>Внимание: Telegram часто блокирует регистрацию красивых 5-буквенных ников без цифр (ошибка «Некорректное имя»). Если занять не вышло, ищите 6 букв или с цифрами!</i>" if len(test_username) == 5 and not any(char.isdigit() for char in test_username) else ""
            
            success_text = (
                f"🎉 <b>Найден свободный ник по маске!</b>\n\n"
                f"👉 @<code>{test_username}</code>\n\n"
                f"• <b>Рейтинг редкости:</b> {rating}/10 {stars}\n"
                f"• <b>Соответствие маске:</b> <code>{mask}</code>\n\n"
                f"<i>Спешите зарегистрировать его в Telegram!</i>{warning}"
            )
            bot.delete_message(message.chat.id, loading_msg.message_id)
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔎 Искать еще", callback_data="menu_filter"))
            markup.add(types.InlineKeyboardButton("Назад в меню", callback_data="main_menu"))
            
            bot.send_message(message.chat.id, success_text, parse_mode="HTML", reply_markup=markup)
            user_recent_suggestions.setdefault(user_id, set()).add(test_username)
            found = True
            break
        elif available is None:
            time.sleep(1.0)
        else:
            time.sleep(config.CHECK_COOLDOWN)
            
    if not found:
        fail_text = (
            f"⚠️ <b>Ник по маске <code>{mask}</code> не найден за {max_tries} проверок.</b>\n\n"
            f"Все сгенерированные комбинации заняты или маска слишком специфична.\n"
            f"Попробуйте изменить маску или запустить поиск снова."
        )
        bot.delete_message(message.chat.id, loading_msg.message_id)
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔁 Попробовать снова", callback_data="menu_filter"))
        markup.add(types.InlineKeyboardButton("Назад в меню", callback_data="main_menu"))
        
        bot.send_message(message.chat.id, fail_text, parse_mode="HTML", reply_markup=markup)

# Process Trap Input
def process_trap_username(message):
    user_id = message.from_user.id
    target_username = message.text.strip().replace("@", "").lower()
    
    # Check if command
    if message.text.strip().startswith("/"):
        bot.clear_step_handler_by_chat_id(message.chat.id)
        if message.text.strip() == "/start":
            send_welcome(message)
        return
        
    # Validate username length
    if not (5 <= len(target_username) <= 32) or not re.match(r'^[a-z0-9_]+$', target_username):
        bot.send_message(
            message.chat.id,
            "❌ <b>Ошибка:</b> Неверный формат юзернейма.\n"
            "Юзернейм должен содержать от 5 до 32 символов (латиница, цифры, нижнее подчеркивание).\n"
            "Пожалуйста, пришлите корректный ник или нажмите /start.",
            parse_mode="HTML"
        )
        bot.register_next_step_handler(message, process_trap_username)
        return
        
    # Add trap to DB
    success = db.add_trap(user_id, target_username)
    
    if success:
        confirm_text = (
            f"✅ <b>Ловушка успешно установлена!</b>\n\n"
            f"Бот будет автоматически мониторить статус юзернейма <b>@{target_username}</b> на серверах Telegram и Fragment в фоновом режиме.\n\n"
            f"Как только он освободится, вы моментально получите уведомление в этот чат!"
        )
    else:
        confirm_text = f"⚠️ Ловушка на юзернейм <b>@{target_username}</b> уже активна в вашем списке!"
        
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📦 К ловушкам", callback_data="menu_trap"))
    markup.add(types.InlineKeyboardButton("Назад в меню", callback_data="main_menu"))
    
    bot.send_message(message.chat.id, confirm_text, parse_mode="HTML", reply_markup=markup)

def process_admin_broadcast(message):
    if message.text == '/cancel':
        bot.send_message(message.chat.id, "Рассылка отменена.")
        return
    users = db.get_all_users()
    count = 0
    bot.send_message(message.chat.id, "Начинаю рассылку...")
    for uid in users:
        try:
            bot.copy_message(uid, message.chat.id, message.message_id)
            count += 1
            time.sleep(0.05)
        except Exception:
            pass
    bot.send_message(message.chat.id, f"Рассылка завершена. Доставлено: {count} / {len(users)}")

def process_admin_premium(message):
    if message.text == '/cancel':
        bot.send_message(message.chat.id, "Отменено.")
        return
    try:
        target_id = int(message.text.strip())
        user = db.get_user(target_id)
        if not user:
            bot.send_message(message.chat.id, "Пользователь с таким ID не найден в БД.")
            return
        new_status = 0 if user['is_premium'] == 1 else 1
        if new_status == 1:
            db.set_premium(target_id, True, premium_source='admin')
        else:
            db.set_premium(target_id, False, premium_source='none')
        status_text = "ВЫДАН ⭐" if new_status == 1 else "ЗАБРАН ❌"
        bot.send_message(message.chat.id, f"Premium статус для пользователя {target_id} успешно {status_text}.")
        
        try:
            if new_status == 1:
                bot.send_message(target_id, "🎉 Администратор выдал вам Premium подписку!")
            else:
                bot.send_message(target_id, "❌ Ваш Premium статус был аннулирован администратором.")
        except Exception:
            pass
    except ValueError:
        bot.send_message(message.chat.id, "Ошибка: Неверный формат ID. Отправьте число.")

@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True,
                                  error_message="Произошла ошибка при оплате. Попробуйте позже.")

@bot.message_handler(content_types=['successful_payment'])
def got_payment(message):
    db.set_premium(message.from_user.id, True, premium_source='payment', duration_days=config.PREMIUM_DURATION_DAYS)
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔎 Перейти к поиску", callback_data="main_menu"))
    bot.send_message(message.chat.id,
                     "🎉 <b>Оплата прошла успешно!</b>\n\nPremium активирован на 1 месяц! Теперь вам доступны все функции бота.",
                     parse_mode='HTML', reply_markup=markup)

# Handle text outside of states
@bot.message_handler(func=lambda msg: True)
def handle_text_messages(msg):
    bot.send_message(
        msg.chat.id,
        "💡 <b>Используйте интерактивное меню для навигации.</b>\n"
        "Нажмите на кнопку 'Перейти к поиску' ниже или введите команду /start.",
        parse_mode="HTML",
        reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔎 Перейти к поиску", callback_data="main_menu"))
    )

if __name__ == "__main__":
    print("Telegram Username Checker Bot is starting...")
    
    # Set bot commands to overwrite any old commands (like PC control commands)
    bot.set_my_commands([
        telebot.types.BotCommand("/start", "Перезапустить бота"),
        telebot.types.BotCommand("/admin", "Панель администратора (только для вас)")
    ])
    
    # Clean webhook before polling
    bot.remove_webhook()
    # Start bot polling
    bot.infinity_polling()
