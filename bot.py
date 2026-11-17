import asyncio
import logging
import sqlite3
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
    coins INTEGER DEFAULT 0,
    correct_answers INTEGER DEFAULT 0,
    wrong_answers INTEGER DEFAULT 0,
    total_played INTEGER DEFAULT 0
)
""")

# Namuna uchun savollar jadvali
cursor.execute("""
CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT,
    option_a TEXT,
    option_b TEXT,
    option_c TEXT,
    option_d TEXT,
    correct TEXT
)
""")
conn.commit()

# Agar bazada savollar bo'lmasa, dastlabki savollarni qo'shamiz
cursor.execute("SELECT COUNT(*) FROM questions")
if cursor.fetchone()[0] == 0:
    sample_questions = [
        ("O'zbekistonning poytaxti qaysi shahar?", "Samarqand", "Toshkent", "Buxoro", "Xiva", "B"),
        ("Python dasturlash tili qaysi yilda yaratilgan?", "1991", "1995", "2000", "1985", "A"),
        ("Dunyodagi eng katta okean?", "Atlantika", "Hind", "Tinch", "Shimoliy Muziy", "C"),
        ("Inson organizmida nechta suyak bor (kattalarda)?", "206", "210", "195", "220", "A")
    ]
    cursor.executemany("INSERT INTO questions (question, option_a, option_b, option_c, option_d, correct) VALUES (?, ?, ?, ?, ?, ?)", sample_questions)
    conn.commit()


# --- FSM (STATE) HOLATLAR ---
class AdminCoinState(StatesGroup):
    waiting_for_amount = State()
    waiting_for_user_id = State()


# --- KEYBOARDLAR ---
def get_main_menu(user_id: int):
    keyboard = [
        [KeyboardButton(text="🧠 Viktorina o'ynash"), KeyboardButton(text="👤 Mening hisobim")],
        [KeyboardButton(text="🛒 Do'kon"), KeyboardButton(text="🏆 Peshqadamlar (Top 30)")],
    ]
    if user_id == ADMIN_ID:
        keyboard.append([KeyboardButton(text="🛠 Admin panel")])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_admin_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎁 Coin berish"), KeyboardButton(text="📊 Bot statistikasi")],
            [KeyboardButton(text="⬅️ Asosiy menyuga qaytish")]
        ],
        resize_keyboard=True
    )


# --- HANDLERLAR ---

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    username = message.from_user.username or "Mavjud emas"
    name = message.from_user.first_name

    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (user_id, username, name, coins) VALUES (?, ?, ?, 10)", (user_id, username, name))
        conn.commit()

    # Agar guruhda yozilsa
    if message.chat.type != "private":
        await message.answer("Salom! Guruhda viktorina o'ynash uchun /quiz buyrug'ini yuboring.")
        return

    await message.answer(
        f"Assalomu alaykum, {name}! 🤖\n"
        "Viktorina botiga xush kelibsiz. Savollarga javob bering, coinlar yig'ing va sovrinlar yutib oling!",
        reply_markup=get_main_menu(user_id)
    )


@router.message(F.text == "⬅️ Asosiy menyuga qaytish")
async def back_to_menu(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Asosiy menyu:", reply_markup=get_main_menu(message.from_user.id))


@router.message(F.text == "👤 Mening hisobim")
async def my_profile(message: Message):
    user_id = message.from_user.id
    cursor.execute("SELECT coins, correct_answers, wrong_answers, total_played FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        await message.answer("Ro'yxatdan o'tish uchun /start ni bosing.")
        return

    coins, correct, wrong, total = row
    text = (
        f"👤 **Sizning profilingiz:**\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"💰 Coinlar: **{coins} ta**\n"
        f"🎮 Jami o'yinlar: {total} ta\n"
        f"✅ To'g'ri javoblar: {correct} ta\n"
        f"❌ Xato javoblar: {wrong} ta"
    )
    await message.answer(text, parse_mode="HTML")


@router.message(F.text == "🏆 Peshqadamlar (Top 30)")
async def top_players(message: Message):
    cursor.execute("SELECT name, username, coins FROM users ORDER BY coins DESC LIMIT 30")
    rows = cursor.fetchall()

    text = "🏆 **Top 30 Peshqadamlar:**\n\n"
    for i, row in enumerate(rows, 1):
        name, username, coins = row
        uname = f"(@{username})" if username != "Mavjud emas" else ""
        text += f"{i}. {name} {uname} — **{coins} coin**\n"

    await message.answer(text, parse_mode="HTML")


@router.message(F.text == "🛒 Do'kon")
async def shop_menu(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💡 To'g'ri javobni ochish (20 coin)", callback_data="buy_hint")],
        [InlineKeyboardButton(text="🛡 Qalqon / Xatoni o'chirish (50 coin)", callback_data="buy_shield")]
    ])
    await message.answer(
        "🛒 **Do'stlar do'koniga xush kelibsiz!**\n"
        "To'plagan coinlaringiz evaziga imkoniyatlar sotib oling:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data.in_(["buy_hint", "buy_shield"]))
async def process_shop(callback: CallbackQuery):
    user_id = callback.from_user.id
    cursor.execute("SELECT coins FROM users WHERE user_id = ?", (user_id,))
    coins = cursor.fetchone()[0]

    cost = 20 if callback.data == "buy_hint" else 50
    item_name = "To'g'ri javobni ochish" if callback.data == "buy_hint" else "Qalqon"

    if coins < cost:
        await callback.answer(f"❌ Coiningiz yetarli emas! Sizda {coins} coin bor, kerak: {cost} coin.", show_alert=True)
        return

    cursor.execute("SELECT coins FROM users WHERE user_id = ?", (user_id,))
    new_coins = coins - cost
    cursor.execute("UPDATE users SET coins = ? WHERE user_id = ?", (new_coins, user_id))
    conn.commit()

    await callback.answer(f"✅ Muvaffaqiyatli xarid qilindi: {item_name}! Qolgan coin: {new_coins}", show_alert=True)


# --- VIKTORINA QISMI ---
@router.message(F.text == "🧠 Viktorina o'ynash")
async def start_quiz_msg(message: Message):
    await send_quiz_question(message)


@router.message(Command("quiz"))
async def cmd_quiz_group(message: Message):
    await send_quiz_question(message)


async def send_quiz_question(message: Message):
    cursor.execute("SELECT id, question, option_a, option_b, option_c, option_d FROM questions ORDER BY RANDOM() LIMIT 1")
    q = cursor.fetchone()
    if not q:
        await message.answer("Hozircha savollar mavjud emas.")
        return

    q_id, text, a, b, c, d = q
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"A) {a}", callback_data=f"quiz_{q_id}_A"),
         InlineKeyboardButton(text=f"B) {b}", callback_data=f"quiz_{q_id}_B")],
        [InlineKeyboardButton(text=f"C) {c}", callback_data=f"quiz_{q_id}_C"),
         InlineKeyboardButton(text=f"D) {d}", callback_data=f"quiz_{q_id}_D")]
    ])

    await message.answer(f"❓ **Savol:**\n\n{text}", reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data.startswith("quiz_"))
async def process_quiz_answer(callback: CallbackQuery):
    parts = callback.data.split("_")
    q_id = int(parts[1])
    selected_option = parts[2]
    user_id = callback.from_user.id

    cursor.execute("SELECT correct FROM questions WHERE id = ?", (q_id,))
    res = cursor.fetchone()
    if not res:
        await callback.answer("Savol topilmadi.", show_alert=True)
        return

    correct_option = res[0]
    cursor.execute("UPDATE users SET total_played = total_played + 1 WHERE user_id = ?", (user_id,))

    if selected_option == correct_option:
        cursor.execute("UPDATE users SET coins = coins + 10, correct_answers = correct_answers + 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        await callback.answer("✅ To'g'ri! +10 coin qo'shildi 🎉", show_alert=True)
        await callback.message.edit_text(f"{callback.message.text}\n\n✅ **To'g'ri javob!** (Siz tanladingiz: {selected_option})", parse_mode="HTML")
    else:
        cursor.execute("UPDATE users SET wrong_answers = wrong_answers + 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        await callback.answer(f"❌ Xato! To'g'ri javob: {correct_option}", show_alert=True)
        await callback.message.edit_text(f"{callback.message.text}\n\n❌ **Notog'ri javob.** To'g'ri javob edi: {correct_option}", parse_mode="HTML")


# --- ADMIN PANEL & COIN YUBORISH ---
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

    # Coin qo'shish
    cursor.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (amount, target_user_id))
    conn.commit()

    await state.clear()

    # Adminga check yuborish
    check_text = (
        f"🧾 **ADMIN CHECK / O'TKAZMA**\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🎁 Miqdor: **+{amount} coin**\n"
        f"👤 Qabul qiluvchi ID: <code>{target_user_id}</code>\n"
        f"Status: **Muvaffaqiyatli ✅**"
    )
    await message.answer(check_text, reply_markup=get_admin_menu(), parse_mode="HTML")

    # Qabul qiluvchiga xabar yuborish
    try:
        await bot.send_message(target_user_id, f"🎉 Sizga {amount} coin qoʻshildi!")
    except Exception:
        pass


async def main():
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
