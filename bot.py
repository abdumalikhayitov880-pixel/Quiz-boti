import asyncio
import logging
import sqlite3
import random
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Message,
)

TOKEN = "8878958601:AAHK4FxmTpbFNDM4LpBYiBGz8QQw_eNL_14"
ADMIN_ID = 1130978177

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()

conn = sqlite3.connect("quiz_database.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    name TEXT,
    coins INTEGER DEFAULT 100000,
    correct_answers INTEGER DEFAULT 0,
    wrong_answers INTEGER DEFAULT 0,
    total_played INTEGER DEFAULT 0,
    selected_categories TEXT DEFAULT 'Tarix,Biologiya,IT,Huquq va siyosat,Futbol,Avtomobillar'
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT DEFAULT 'Tarix',
    question TEXT,
    option_a TEXT,
    option_b TEXT,
    option_c TEXT,
    option_d TEXT,
    correct TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS user_question_history (
    user_id INTEGER,
    question_id INTEGER,
    PRIMARY KEY (user_id, question_id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS user_gifts (
    user_id INTEGER,
    gift_name TEXT,
    quantity INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, gift_name)
)
""")
conn.commit()

ALL_CATEGORIES = ["Tarix", "Biologiya", "IT", "Huquq va siyosat", "Futbol", "Avtomobillar"]

GIFTS_CONFIG = {
    "❤️": 5000,
    "⭐": 10000,
    "💌": 15000,
    "📖": 20000,
    "🖋️": 5000,
    "👑": 100000,
    "🏆": 100000
}

cursor.execute("SELECT COUNT(*) FROM questions")
if cursor.fetchone()[0] == 0:
    sample_questions = [
        ("Tarix", "O'zbekistonning poytaxti qaysi shahar?", "Samarqand", "Toshkent", "Buxoro", "Xiva", "B"),
        ("IT", "Python dasturlash tili qaysi yilda yaratilgan?", "1991", "1995", "2000", "1985", "A"),
        ("Tarix", "Dunyodagi eng katta okean?", "Atlantika", "Hind", "Tinch", "Shimoliy Muziy", "C"),
        ("Biologiya", "Inson organizmida nechta suyak bor (kattalarda)?", "206", "210", "195", "220", "A"),
        ("Futbol", "Hakim Ziyech qaysi millat vakili?", "Fransuz", "Marokashlik", "Braziliyalik", "Gollandiyalik", "B")
    ]
    cursor.executemany("INSERT INTO questions (category, question, option_a, option_b, option_c, option_d, correct) VALUES (?, ?, ?, ?, ?, ?, ?)", sample_questions)
    conn.commit()

class AdminCoinState(StatesGroup):
    waiting_for_amount = State()
    waiting_for_user_id = State()

class AddQuestionState(StatesGroup):
    waiting_for_category = State()
    waiting_for_question = State()
    waiting_for_a = State()
    waiting_for_b = State()
    waiting_for_c = State()
    waiting_for_d = State()
    waiting_for_correct = State()

class GiftState(StatesGroup):
    choosing_source = State()
    entering_target_id = State()
    entering_letter = State()

def get_main_menu(user_id: int):
    keyboard = [
        [KeyboardButton(text="🧠 Viktorina o'ynash"), KeyboardButton(text="👤 Mening hisobim")],
        [KeyboardButton(text="🛒 Virtual do'kon"), KeyboardButton(text="🏆 Peshqadamlar (Top 30)")],
        [KeyboardButton(text="🎁 Do'stga sovg'a yuborish")]
    ]
    if user_id == ADMIN_ID:
        keyboard.append([KeyboardButton(text="🛠 Admin panel")])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_admin_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎁 Coin berish"), KeyboardButton(text="➕ Savol qo'shish")],
            [KeyboardButton(text="📊 Bot statistikasi"), KeyboardButton(text="⬅️ Asosiy menyuga qaytish")]
        ],
        resize_keyboard=True
    )

def get_categories_keyboard(selected_cats: list):
    builder = []
    for cat in ALL_CATEGORIES:
        status = "✅" if cat in selected_cats else "❌"
        builder.append([InlineKeyboardButton(text=f"{status} {cat}", callback_data=f"toggle_cat_{cat}")])
    builder.append([
        InlineKeyboardButton(text="☑️ Hammasini belgilash", callback_data="cat_all"),
        InlineKeyboardButton(text="✅ Tayyor", callback_data="cat_done")
    ])
    return InlineKeyboardMarkup(inline_keyboard=builder)

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    username = message.from_user.username or "Mavjud emas"
    name = message.from_user.first_name

    cursor.execute("SELECT user_id, selected_categories FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        default_cats = ",".join(ALL_CATEGORIES)
        cursor.execute("INSERT INTO users (user_id, username, name, coins, selected_categories) VALUES (?, ?, ?, 100000, ?)", (user_id, username, name, default_cats))
        conn.commit()
        selected_cats = ALL_CATEGORIES
    else:
        selected_cats = row[1].split(",") if row[1] else []

    if message.chat.type != "private":
        await message.answer("Salom! Guruhda viktorina o'ynash uchun /quiz buyrug'ini yuboring.")
        return

    await message.answer(
        f"Assalomu alaykum, {name}! 🤖\nViktorina botiga xush kelibsiz. O'zingizga yoqqan kategoriyalarni tanlang:",
        reply_markup=get_categories_keyboard(selected_cats)
    )

@router.callback_query(F.data.startswith("toggle_cat_"))
async def toggle_category(callback: CallbackQuery):
    user_id = callback.from_user.id
    cat = callback.data.replace("toggle_cat_", "")
    
    cursor.execute("SELECT selected_categories FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    current_cats = row[0].split(",") if row[0] else []

    if cat in current_cats:
        current_cats.remove(cat)
    else:
        current_cats.append(cat)

    new_str = ",".join(current_cats)
    cursor.execute("UPDATE users SET selected_categories = ? WHERE user_id = ?", (new_str, user_id))
    conn.commit()

    await callback.message.edit_reply_markup(reply_markup=get_categories_keyboard(current_cats))
    await callback.answer()

@router.callback_query(F.data == "cat_all")
async def select_all_cats(callback: CallbackQuery):
    user_id = callback.from_user.id
    new_str = ",".join(ALL_CATEGORIES)
    cursor.execute("UPDATE users SET selected_categories = ? WHERE user_id = ?", (new_str, user_id))
    conn.commit()
    await callback.message.edit_reply_markup(reply_markup=get_categories_keyboard(ALL_CATEGORIES))
    await callback.answer("Barcha kategoriyalar tanlandi!")

@router.callback_query(F.data == "cat_done")
async def categories_done(callback: CallbackQuery):
    await callback.message.delete()
    await callback.message.answer("Muvaffaqiyatli saqlandi! Asosiy menyu:", reply_markup=get_main_menu(callback.from_user.id))

@router.message(F.text == "⬅️ Asosiy menyuga qaytish")
async def back_to_menu(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Asosiy menyu:", reply_markup=get_main_menu(message.from_user.id))

@router.message(F.text == "👤 Mening hisobim")
async def my_profile(message: Message):
    user_id = message.from_user.id
    cursor.execute("SELECT coins, correct_answers, wrong_answers, total_played, selected_categories FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        await message.answer("Ro'yxatdan o'tish uchun /start ni bosing.")
        return

    coins, correct, wrong, total, cats = row
    cursor.execute("SELECT gift_name, quantity FROM user_gifts WHERE user_id = ? AND quantity > 0", (user_id,))
    gifts = cursor.fetchall()
    gifts_text = ""
    for g_name, g_qty in gifts:
        total_val = GIFTS_CONFIG.get(g_name, 0) * g_qty
        gifts_text += f"{g_name} x{g_qty} (qiymati {total_val} coin)\n"
    if not gifts_text:
        gifts_text = "Hozircha sovg'alar yo'q.\n"

    text = (
        f"👤 **Sizning profilingiz:**\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"💰 Coinlar: **{coins} ta**\n"
        f"🏆 To'g'ri topilganlar: **{correct} ta**\n"
        f"🎮 Jami o'yinlar: {total} ta\n"
        f"❌ Xato javoblar: {wrong} ta\n\n"
        f"🎁 **Sizdagi sovg'alar:**\n{gifts_text}\n"
        f"📂 **Tanlangan kategoriyalar:** {cats}"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ Kategoriyalarni o'zgartirish", callback_data="change_cats")]
    ])
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "change_cats")
async def change_categories_btn(callback: CallbackQuery):
    user_id = callback.from_user.id
    cursor.execute("SELECT selected_categories FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    current_cats = row[0].split(",") if row and row[0] else []
    await callback.message.answer("Kategoriyalarni tanlang:", reply_markup=get_categories_keyboard(current_cats))
    await callback.answer()

@router.message(F.text == "🏆 Peshqadamlar (Top 30)")
async def top_players(message: Message):
    cursor.execute("SELECT name, username, correct_answers, user_id FROM users ORDER BY correct_answers DESC LIMIT 30")
    rows = cursor.fetchall()

    text = "🏆 **Top 30 Peshqadamlar (To'g'ri javoblar bo'yicha):**\n\n"
    for i, row in enumerate(rows, 1):
        name, username, correct, u_id = row
        uname = f"(@{username})" if username != "Mavjud emas" else ""
        text += f"{i}. {name} {uname} [ID: <code>{u_id}</code>] — **{correct} ta to'g'ri**\n"

    await message.answer(text, parse_mode="HTML")

@router.message(F.text == "🛒 Virtual do'kon")
async def shop_menu(message: Message):
    keyboard_rows = []
    for gift, price in GIFTS_CONFIG.items():
        keyboard_rows.append([InlineKeyboardButton(text=f"Sotib olish: {gift} — {price} coin", callback_data=f"buy_gift_{gift}")])
    
    await message.answer(
        "🛒 **Virtual sovg'alar do'koniga xush kelibsiz!**\nSovg'alarni sotib oling va do'stlaringizga yuboring:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("buy_gift_"))
async def process_buy_gift(callback: CallbackQuery):
    gift_name = callback.data.replace("buy_gift_", "")
    user_id = callback.from_user.id
    price = GIFTS_CONFIG.get(gift_name, 0)

    cursor.execute("SELECT coins FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    coins = row[0] if row else 0

    if coins < price:
        await callback.answer(f"❌ Coiningiz yetarli emas! Kerak: {price} coin.", show_alert=True)
        return

    cursor.execute("UPDATE users SET coins = coins - ? WHERE user_id = ?", (price, user_id))
    cursor.execute("INSERT INTO user_gifts (user_id, gift_name, quantity) VALUES (?, ?, 1) ON CONFLICT(user_id, gift_name) DO UPDATE SET quantity = quantity + 1", (user_id, gift_name))
    conn.commit()

    await callback.answer(f"✅ Muvaffaqiyatli xarid qilindi: {gift_name}!", show_alert=True)
@router.message(F.text == "🎁 Do'stga sovg'a yuborish")
async def gift_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    cursor.execute("SELECT gift_name, quantity FROM user_gifts WHERE user_id = ? AND quantity > 0", (user_id,))
    gifts = cursor.fetchall()
    
    keyboard = []
    for g_name, g_qty in gifts:
        keyboard.append([InlineKeyboardButton(text=f"{g_name} (Sizda: {g_qty} ta)", callback_data=f"send_g_{g_name}")])
    keyboard.append([InlineKeyboardButton(text="🛒 Do'kondan sotib olib yuborish", callback_data="send_g_from_shop")])

    await message.answer("Qanday usulda sovg'a yubormoqchisiz?", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    await state.set_state(GiftState.choosing_source)

@router.callback_query(GiftState.choosing_source, F.data.startswith("send_g_"))
async def gift_choose_source(callback: CallbackQuery, state: FSMContext):
    data_val = callback.data.replace("send_g_", "")
    await state.update_data(source_gift=data_val)
    
    if data_val == "from_shop":
        kb = [[InlineKeyboardButton(text=f"{g} — {p} coin", callback_data=f"shop_g_{g}")] for g, p in GIFTS_CONFIG.items()]
        await callback.message.edit_text("Do'kondan sovg'ani tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    else:
        await callback.message.edit_text(f"Tanlandi: {data_val}\nQabul qiluvchi do'stning **ID raqamini** kiriting:")
        await state.set_state(GiftState.entering_target_id)
    await callback.answer()

@router.callback_query(GiftState.choosing_source, F.data.startswith("shop_g_"))
async def gift_shop_chosen(callback: CallbackQuery, state: FSMContext):
    g_name = callback.data.replace("shop_g_", "")
    await state.update_data(source_gift=g_name, buy_from_shop=True)
    await callback.message.edit_text(f"Tanlandi: {g_name} (Do'kondan sotib olinadi)\nQabul qiluvchi do'stning **ID raqamini** kiriting:")
    await state.set_state(GiftState.entering_target_id)
    await callback.answer()

@router.message(GiftState.entering_target_id)
async def gift_enter_target(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ ID faqat raqamlardan iborat bo'lishi kerak. Qaytadan kiriting:")
        return
    target_id = int(message.text)
    
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (target_id,))
    if not cursor.fetchone():
        await message.answer("❌ Bunday ID raqamli foydalanuvchi topilmadi!")
        return

    await state.update_data(target_id=target_id)
    await message.answer("Do'stingizga yuborish uchun **maktub (tilak/xat)** yuboring (yoki 'yo'q' deb yozing):")
    await state.set_state(GiftState.entering_letter)

@router.message(GiftState.entering_letter)
async def gift_enter_letter(message: Message, state: FSMContext):
    letter = message.text
    data = await state.get_data()
    sender_id = message.from_user.id
    sender_name = message.from_user.first_name
    sender_uname = message.from_user.username or "Mavjud emas"
    target_id = data.get("target_id")
    gift_name = data.get("source_gift")
    from_shop = data.get("buy_from_shop", False)

    if from_shop:
        price = GIFTS_CONFIG.get(gift_name, 0)
        cursor.execute("SELECT coins FROM users WHERE user_id = ?", (sender_id,))
        coins = cursor.fetchone()[0]
        if coins < price:
            await message.answer(f"❌ Coiningiz yetarli emas! Kerak: {price} coin.", reply_markup=get_main_menu(sender_id))
            await state.clear()
            return
        cursor.execute("UPDATE users SET coins = coins - ? WHERE user_id = ?", (price, sender_id))
        conn.commit()
    else:
        cursor.execute("SELECT quantity FROM user_gifts WHERE user_id = ? AND gift_name = ?", (sender_id, gift_name))
        row = cursor.fetchone()
        if not row or row[0] <= 0:
            await message.answer("❌ Sizda bu sovg'a qolmagan!", reply_markup=get_main_menu(sender_id))
            await state.clear()
            return
        cursor.execute("UPDATE user_gifts SET quantity = quantity - 1 WHERE user_id = ? AND gift_name = ?", (sender_id, gift_name))
        conn.commit()

    cursor.execute("INSERT INTO user_gifts (user_id, gift_name, quantity) VALUES (?, ?, 1) ON CONFLICT(user_id, gift_name) DO UPDATE SET quantity = quantity + 1", (target_id, gift_name))
    conn.commit()
    await state.clear()

    await message.answer("✅ Sovg'a muvaffaqiyatli yuborildi!", reply_markup=get_main_menu(sender_id))

    uname_str = f"(@{sender_uname})" if sender_uname != "Mavjud emas" else ""
    target_text = (
        f"🎁 Sizga **{sender_name}** {uname_str} - (ID: <code>{sender_id}</code>) tomonidan **{gift_name}** sovg'asi yuborildi!\n\n"
        f"💌 **Maktub:** {letter}\n\n"
        f"Unga sovg'a qaytarasizmi?"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Qaytarish", callback_data=f"return_gift_{sender_id}"),
         InlineKeyboardButton(text="❌ Qaytarmaslik", callback_data="return_no")]
    ])
    try:
        await bot.send_message(target_id, target_text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass

@router.callback_query(F.data.startswith("return_gift_"))
async def gift_return_press(callback: CallbackQuery, state: FSMContext):
    target_id = int(callback.data.replace("return_gift_", ""))
    await state.update_data(target_id=target_id)
    
    user_id = callback.from_user.id
    cursor.execute("SELECT gift_name, quantity FROM user_gifts WHERE user_id = ? AND quantity > 0", (user_id,))
    gifts = cursor.fetchall()
    
    keyboard = []
    for g_name, g_qty in gifts:
        keyboard.append([InlineKeyboardButton(text=f"{g_name} (Sizda: {g_qty} ta)", callback_data=f"send_g_{g_name}")])
    keyboard.append([InlineKeyboardButton(text="🛒 Do'kondan sotib olib yuborish", callback_data="send_g_from_shop")])

    await callback.message.answer("Qaytarish uchun sovg'ani tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    await state.set_state(GiftState.choosing_source)
    await callback.answer()

@router.callback_query(F.data == "return_no")
async def gift_return_no(callback: CallbackQuery):
    await callback.message.edit_text("Xabar yopildi.")
    await callback.answer()

@router.message(F.text == "🧠 Viktorina o'ynash")
async def start_quiz_msg(message: Message):
    await send_quiz_question(message)

@router.message(Command("quiz"))
async def cmd_quiz_group(message: Message):
    await send_quiz_question(message)

async def send_quiz_question(message: Message):
    user_id = message.from_user.id
    
    cursor.execute("SELECT selected_categories FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    cats = row[0].split(",") if row and row[0] else ALL_CATEGORIES

    placeholders = ",".join(["?"] * len(cats))
    query = f"""
        SELECT id, category, question, option_a, option_b, option_c, option_d FROM questions 
        WHERE category IN ({placeholders}) AND id NOT IN (
            SELECT question_id FROM user_question_history WHERE user_id = ?
        ) 
        ORDER BY RANDOM() LIMIT 1
    """
    cursor.execute(query, (*cats, user_id))
    q = cursor.fetchone()

    if not q:
        cursor.execute("DELETE FROM user_question_history WHERE user_id = ?", (user_id,))
        conn.commit()
        cursor.execute(query, (*cats, user_id))
        q = cursor.fetchone()

    if not q:
        await message.answer("Tanlangan kategoriyalar bo'yicha hozircha savollar yo'q. Admin panel orqali savol yuklang.")
        return

    q_id, cat, text, a, b, c, d = q

    cursor.execute("INSERT OR IGNORE INTO user_question_history (user_id, question_id) VALUES (?, ?)", (user_id, q_id))
    conn.commit()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"A) {a}", callback_data=f"quiz_{q_id}_A"),
         InlineKeyboardButton(text=f"B) {b}", callback_data=f"quiz_{q_id}_B")],
        [InlineKeyboardButton(text=f"C) {c}", callback_data=f"quiz_{q_id}_C"),
         InlineKeyboardButton(text=f"D) {d}", callback_data=f"quiz_{q_id}_D")]
    ])

    sent_msg = await message.answer(f"🏷 **Kategoriya:** {cat}\n⏱ *10 soniya vaqt!*:\n\n❓ **Savol:**\n{text}", reply_markup=keyboard, parse_mode="HTML")

    asyncio.create_task(quiz_timer(sent_msg.chat.id, sent_msg.message_id, q_id, user_id))

async def quiz_timer(chat_id, message_id, q_id, user_id):
    await asyncio.sleep(10)
    try:
        cursor.execute("SELECT correct FROM questions WHERE id = ?", (q_id,))
        res = cursor.fetchone()
        if not res:
            return
        
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"❌ **Vaqt tugadi!** (10 soniya o'tdi)\nTo'g'ri javob edi: {res[0]}",
            parse_mode="HTML"
        )
        cursor.execute("UPDATE users SET wrong_answers = wrong_answers + 1, total_played = total_played + 1 WHERE user_id = ?", (user_id,))
        conn.commit()
    except Exception:
        pass

@router.callback_query(F.data.startswith("quiz_"))
async def process_quiz_answer(callback: CallbackQuery):
    parts = callback.data.split("_")
    q_id = int(parts[1])
    selected_option = parts[2]
    user_id = callback.from_user.id

    cursor.execute("SELECT correct FROM questions WHERE id = ?", (q_id,))
    res = cursor.fetchone()
    if not res:
        await callback.answer("Savol allaqachon yopilgan yoki topilmadi.", show_alert=True)
        return

    correct_option = res[0]
    cursor.execute("UPDATE users SET total_played = total_played + 1 WHERE user_id = ?", (user_id,))

    if selected_option == correct_option:
        cursor.execute("UPDATE users SET coins = coins + 10, correct_answers = correct_answers + 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        await callback.answer("✅ To'g'ri! +10 coin qo'shildi 🎉", show_alert=True)
        try:
            await callback.message.edit_text(f"{callback.message.text}\n\n✅ **To'g'ri javob!**", parse_mode="HTML")
        except Exception:
            pass
    else:
        cursor.execute("UPDATE users SET wrong_answers = wrong_answers + 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        await callback.answer(f"❌ Xato! To'g'ri javob: {correct_option}", show_alert=True)
        try:
            await callback.message.edit_text(f"{callback.message.text}\n\n❌ **Notog'ri javob.** To'g'ri javob edi: {correct_option}", parse_mode="HTML")
        except Exception:
            pass

@router.message(F.text == "🛠 Admin panel")
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("🛠 **Admin paneliga xush kelibsiz:**", reply_markup=get_admin_menu(), parse_mode="HTML")

@router.message(F.text == "📊 Bot statistikasi")
async def admin_stats(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM questions")
    total_questions = cursor.fetchone()[0]

    await message.answer(f"📊 **Statistika:**\n\n👥 Jami foydalanuvchilar: {total_users} ta\n❓ Jami savollar: {total_questions} ta", parse_mode="HTML")

@router.message(F.text == "🎁 Coin berish")
async def admin_give_coin(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("Qancha coin bermoqchisiz? (Faqat raqam kiriting):", reply_markup=ReplyKeyboardRemove())
    await state.set_state(AdminCoinState.waiting_for_amount)

@router.message(AdminCoinState.waiting_for_amount)
async def process_admin_amount(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Iltimos, faqat raqam kiriting:")
        return
    
    amount = int(message.text)
    await state.update_data(amount=amount)
    await message.answer("Qabul qiluvchi foydalanuvchining ID raqamini kiriting:")
    await state.set_state(AdminCoinState.waiting_for_user_id)

@router.message(AdminCoinState.waiting_for_user_id)
async def process_admin_userid(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Xato! ID faqat raqamlardan iborat bo'lishi kerak. Qaytadan kiriting:")
        return

    target_user_id = int(message.text)
    data = await state.get_data()
    amount = data.get("amount")

    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (target_user_id,))
    if not cursor.fetchone():
        await message.answer("❌ Bunday ID raqamli foydalanuvchi bazada topilmadi!", reply_markup=get_admin_menu())
        await state.clear()
        return

    cursor.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (amount, target_user_id))
    conn.commit()
    await state.clear()

    check_text = (
        f"🧾 **ADMIN CHECK / O'TKAZMA**\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🎁 Miqdor: **+{amount} coin**\n"
        f"👤 Qabul qiluvchi ID: <code>{target_user_id}</code>\n"
        f"Status: **Muvaffaqiyatli ✅**"
    )
    await message.answer(check_text, reply_markup=get_admin_menu(), parse_mode="HTML")

    try:
        await bot.send_message(target_user_id, f"🎉 Sizga {amount} coin qoʻshildi!")
    except Exception:
        pass

@router.message(F.text == "➕ Savol qo'shish")
async def admin_add_question(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    cats_text = ", ".join(ALL_CATEGORIES)
    await message.answer(f"Savol kategoriyasini yozing (Mavjudlar: {cats_text}):", reply_markup=ReplyKeyboardRemove())
    await state.set_state(AddQuestionState.waiting_for_category)

@router.message(AddQuestionState.waiting_for_category)
async def process_new_q_cat(message: Message, state: FSMContext):
    cat = message.text.strip()
    await state.update_data(category=cat)
    await message.answer("Yangi savol matnini kiriting:")
    await state.set_state(AddQuestionState.waiting_for_question)

@router.message(AddQuestionState.waiting_for_question)
async def process_new_q_text(message: Message, state: FSMContext):
    await state.update_data(question=message.text)
    await message.answer("A variantini kiriting:")
    await state.set_state(AddQuestionState.waiting_for_a)

@router.message(AddQuestionState.waiting_for_a)
async def process_new_q_a(message: Message, state: FSMContext):
    await state.update_data(option_a=message.text)
    await message.answer("B variantini kiriting:")
    await state.set_state(AddQuestionState.waiting_for_b)

@router.message(AddQuestionState.waiting_for_b)
async def process_new_q_b(message: Message, state: FSMContext):
    await state.update_data(option_b=message.text)
    await message.answer("C variantini kiriting:")
    await state.set_state(AddQuestionState.waiting_for_c)

@router.message(AddQuestionState.waiting_for_c)
async def process_new_q_c(message: Message, state: FSMContext):
    await state.update_data(option_c=message.text)
    await message.answer("D variantini kiriting:")
    await state.set_state(AddQuestionState.waiting_for_d)

@router.message(AddQuestionState.waiting_for_d)
async def process_new_q_d(message: Message, state: FSMContext):
    await state.update_data(option_d=message.text)
    await message.answer("To'g'ri javob qaysi biri? Faqat harfini kiriting (**A, B, C yoki D**):")
    await state.set_state(AddQuestionState.waiting_for_correct)

@router.message(AddQuestionState.waiting_for_correct)
async def process_new_q_correct(message: Message, state: FSMContext):
    correct = message.text.strip().upper()
    if correct not in ["A", "B", "C", "D"]:
        await message.answer("❌ Xato! Faqat A, B, C yoki D harflaridan birini kiriting:")
        return

    data = await state.get_data()
    cat = data.get("category")
    q_text = data.get("question")
    opt_a = data.get("option_a")
    opt_b = data.get("option_b")
    opt_c = data.get("option_c")
    opt_d = data.get("option_d")

    cursor.execute(
        "INSERT INTO questions (category, question, option_a, option_b, option_c, option_d, correct) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (cat, q_text, opt_a, opt_b, opt_c, opt_d, correct)
    )
    conn.commit()
    await state.clear()

    cursor.execute("SELECT COUNT(*) FROM questions")
    total = cursor.fetchone()[0]

    await message.answer(
        f"✅ **Yangi savol muvaffaqiyatli qo'shildi!**\n\n"
        f"📊 Bazadagi jami savollar soni: **{total} ta**",
        reply_markup=get_admin_menu(),
        parse_mode="HTML"
    )

async def main():
    dp.include_router(router)
    try:
        await bot.delete_webhook(drop_pending_updates=True, request_timeout=30)
    except Exception as e:
        print(f"Webhookni tozalashda ogohlantirish: {e}")
        
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
  
