import asyncio
import logging
import sqlite3
import aiohttp
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

# --- BAZA BILAN ISHLASH ---
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


# --- INTERNETDAN AVTO-SAVOL YUKLASH ---
async def fetch_and_save_massive_questions(target_count=1000):
    logging.info("🌐 Internetdan kategoriyalar bo'yicha savollar yuklash boshlandi...")
    async with aiohttp.ClientSession() as session:
        for cat in ALL_CATEGORIES:
            url = "https://opentdb.com/api.php?amount=30&type=multiple"
            try:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        for item in data.get("results", []):
                            q_text = item.get("question")
                            correct = item.get("correct_answer")
                            incorrects = item.get("incorrect_answers")
                            if len(incorrects) < 3:
                                continue
                            options = [correct, incorrects[0], incorrects[1], incorrects[2]]
                            random.shuffle(options)
                            correct_letter = ["A", "B", "C", "D"][options.index(correct)]
                            
                            cursor.execute("SELECT id FROM questions WHERE question = ?", (q_text,))
                            if not cursor.fetchone():
                                cursor.execute(
                                    "INSERT INTO questions (category, question, option_a, option_b, option_c, option_d, correct) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                    (cat, q_text, options[0], options[1], options[2], options[3], correct_letter)
                                )
                        conn.commit()
            except Exception as e:
                logging.error(f"Xatolik: {e}")
    logging.info("✅ Savollar yuklandi!")


# --- FSM (STATE) ---
class AdminState(StatesGroup):
    waiting_for_amount = State()
    waiting_for_user_id = State()

class GiftState(StatesGroup):
    choosing_source = State()
    entering_target_id = State()
    entering_letter = State()


# --- KEYBOARDLAR ---
def get_main_menu(user_id: int):
    keyboard = [
        [KeyboardButton(text="🧠 Viktorina o'ynash"), KeyboardButton(text="👤 Mening hisobim")],
        [KeyboardButton(text="🛒 Virtual do'kon"), KeyboardButton(text="🏆 Peshqadamlar (Top 30)")],
        [KeyboardButton(text="🎁 Do'stga sovg'a yuborish")]
    ]
    if user_id == ADMIN_ID:
        keyboard.append([KeyboardButton(text="🛠 Admin panel")])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


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


# --- HANDLERLAR ---

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
        cursor.execute("INSERT INTO users (user_id, username, name, coins, selected_categories) VALUES (?, ?, ?, 100, ?)", (user_id, username, name, default_cats))
        conn.commit()
        selected_cats = ALL_CATEGORIES
    else:
        selected_cats = row[1].split(",") if row[1] else []

    if message.chat.type != "private":
        await message.answer("Salom! Guruhda viktorina o'ynash uchun /quiz buyrug'ini yuboring.")
        return

    await message.answer(
        f"Assalomu alaykum, {name}! 🤖\nKategoriyalarni tanlang:",
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


# --- VIRTUAL DO'KON ---
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
    coins = cursor.fetchone()[0]

    if coins < price:
        await callback.answer(f"❌ Coiningiz yetarli emas! Kerak: {price} coin.", show_alert=True)
        return

    cursor.execute("UPDATE users SET coins = coins - ? WHERE user_id = ?", (price, user_id))
    cursor.execute("INSERT INTO user_gifts (user_id, gift_name, quantity) VALUES (?, ?, 1) ON CONFLICT(user_id, gift_name) DO UPDATE SET quantity = quantity + 1", (user_id, gift_name))
    conn.commit()

    await callback.answer(f"✅ Muvaffaqiyatli sotib olindi: {gift_name}!", show_alert=True)


# --- DO'STGA SOVG'A YUBORISH ---
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


# --- VIKTORINA QISMI (10 SONIYA & KATEGoriya) ---
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

    asyncio.
