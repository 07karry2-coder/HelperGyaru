import asyncio
from datetime import datetime, timedelta
import logging
import os
import random
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiohttp import web
import asyncpg

# ==================== НАСТРОЙКИ ====================
BOT_TOKEN = "9104618099:AAEq2o4dUJpTNHw2eKQNXq6locc2NW6ZTRU"
DATABASE_URL = "postgresql://neondb_owner:npg_iv0Dn6jWHRVY@ep-empty-frog-bdv03t7y-pooler.c-8.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

ADMIN_IDS = {5806323165, 6070207785}
CHANNEL_ID = -1002885280675  # ID канала для постов, топов и подгонов
CHAT_ID = -1004323082027  # ID суперчата с топиками
TOPIC_BROADCAST = 25  # Тема для рассылки
TOPIC_STOP = 26  # Тема для стопа

PODGON_LIST = [
    "Слабонервным лучше НЕ ОТКРЫВАТЬ!!! Серьезно, мы предупредили.",
    "Скрывать больше нет смысла. Вся подноготная уже здесь.",
    "Они думали, что никто не заметит. Но тайное всё-таки стало явным.",
    "Этот канал изменит ваш день 👍",
    "Лучше один раз увидеть. Хотя поверить в это всё равно сложно.",
    "Они публикуют то, что другие боятся даже обсуждать. Ссылочка внутри.",
    "Сливаем секретные материалы",
    "Здесь делятся тем, о чем обычно молчат. Залетай, пока доступ открыт.",
    "Нашел то, что ты так долго искал. Забирай, пока не заблокировали.",
    "Твое новое любимое место в телеграме. Жми и зацени вайб.",
    "Эту информацию больше нигде не найдешь. Только тсс...🤫",
    "Просто посмотри на первый пост.",
    "Твоя лента станет в разы интереснее. Залетай!",
    "Нашел клад для тех, кто понимает. Зацени сам 👇",
    "После этого ты удалишь половину своих подписок. Останется только этот канал.",
    "Тайное общество для своих. Дверь приоткрыта, но ненадолго.",
    "Вся соль в этом канале. Остальные просто копируют.",
]

logging.basicConfig(level=logging.INFO)
router = Router()
db_pool = None


class OrderState(StatesGroup):
    waiting_for_custom_value = State()
    waiting_for_post = State()


async def init_db():
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL)
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS active_tasks (
                id SERIAL PRIMARY KEY,
                task_type TEXT,
                details TEXT,
                chat_id BIGINT,
                message_id BIGINT,
                top_seconds INT DEFAULT 0,
                expires_at TIMESTAMP,
                status TEXT DEFAULT 'active'
            );
        """)


# --- Клавиатуры ---
def main_menu_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📦 Услуги", callback_data="menu_usugi"),
                InlineKeyboardButton(text="💎 Кф", callback_data="menu_kf"),
            ],
            [
                InlineKeyboardButton(text="➕ Допы", callback_data="menu_dops"),
                InlineKeyboardButton(
                    text="📊 Активные задачи", callback_data="menu_active"
                ),
            ],
        ]
    )


def usugi_menu_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Мини пакет (350₽ / 250⭐)", callback_data="pkg_mini"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Базовый пакет (440₽ / 325⭐)", callback_data="pkg_base"
                )
            ],
            [
                InlineKeyboardButton(
                    text="VIP пакет (550₽ / 400⭐)", callback_data="pkg_vip"
                )
            ],
            [
                InlineKeyboardButton(text="« Назад", callback_data="menu_back")
            ],
        ]
    )


def kf_menu_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Стандартный (135₽ / 100⭐)", callback_data="pkg_standart"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Улучшенный (165₽ / 125⭐)", callback_data="pkg_improved"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Премиум (230₽ / 165⭐)", callback_data="pkg_premium"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Продвинутый (330₽ / 250⭐)",
                    callback_data="pkg_advanced",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Максимальный (375₽ / 275⭐)", callback_data="pkg_max"
                )
            ],
            [
                InlineKeyboardButton(text="« Назад", callback_data="menu_back")
            ],
        ]
    )


def dops_menu_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Рт вашего поста (20₽)", callback_data="dop_rt"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Закреп 1 день (50₽)", callback_data="dop_pin"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Топ 1 час (50₽)", callback_data="dop_top"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Рассылка в боте (50₽)", callback_data="dop_broadcast"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Подгон (20₽)", callback_data="dop_podgon"
                )
            ],
            [
                InlineKeyboardButton(text="« Назад", callback_data="menu_back")
            ],
        ]
    )


def confirm_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Подтвердить и запустить", callback_data="confirm_yes"
                ),
                InlineKeyboardButton(
                    text="❌ Отмена", callback_data="confirm_no"
                ),
            ]
        ]
    )


# --- Обработчики ---
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ У вас нет доступа к этому боту.")
        return
    await state.clear()
    await message.answer(
        "👋 Привет! Панель управления рекламными размещениями.\nВыберите раздел:",
        reply_markup=main_menu_kb(),
    )


@router.callback_query(F.data == "menu_back")
async def back_to_main(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(
        "Выберите раздел:", reply_markup=main_menu_kb()
    )
    await call.answer()


@router.callback_query(F.data == "menu_usugi")
async def show_usugi(call: CallbackQuery):
    await call.message.edit_text("Выберите услугу:", reply_markup=usugi_menu_kb())
    await call.answer()


@router.callback_query(F.data == "menu_kf")
async def show_kf(call: CallbackQuery):
    await call.message.edit_text("Выберите пакет Кф:", reply_markup=kf_menu_kb())
    await call.answer()


@router.callback_query(F.data == "menu_dops")
async def show_dops(call: CallbackQuery):
    await call.message.edit_text(
        "Выберите доп. услугу:", reply_markup=dops_menu_kb()
    )
    await call.answer()


@router.callback_query(
    F.data.startswith("pkg_") | F.data.startswith("dop_")
)
async def select_action(call: CallbackQuery, state: FSMContext):
    action = call.data
    presets = {
        "pkg_mini": {
            "desc": "Мини пакет: Закреп 7 дней, Топ 5 часов, 2 рассылки, 2 подгона.",
            "top_hours": 5,
        },
        "pkg_base": {
            "desc": "Базовый пакет: Рт поста, Закреп 14 дней, Топ 7 часов, 3 рассылки, 3 подгона.",
            "top_hours": 7,
        },
        "pkg_vip": {
            "desc": "VIP пакет: Рт поста, Закреп 30 дней, Топ 16 часов, 6 рассылок, 4 подгона, Сторис 48ч.",
            "top_hours": 16,
        },
        "pkg_standart": {
            "desc": "Стандартный пакет: Рт поста, Закреп 3 дня, Топ 1.5 часа.",
            "top_hours": 1.5,
        },
        "pkg_improved": {
            "desc": "Улучшенный пакет: Рт поста, Закреп 1 неделя, Топ 3 часа, 1 рассылка.",
            "top_hours": 3,
        },
        "pkg_premium": {
            "desc": "Премиум пакет: Рт поста, Закреп 10 дней, Топ 6 часов, 2 рассылки, 2 подгона.",
            "top_hours": 6,
        },
        "pkg_advanced": {
            "desc": "Продвинутый пакет: Рт поста, Закреп 15 дней, Топ 9 часов, 4 рассылки, 3 подгона.",
            "top_hours": 9,
        },
        "pkg_max": {
            "desc": "Максимальный пакет: Рт поста, Закреп 20 дней, 5 рассылок, Топ 17 часов, 5 подгонов.",
            "top_hours": 17,
        },
        "dop_rt": {"desc": "Доп: Рт вашего поста.", "top_hours": 0},
        "dop_broadcast": {
            "desc": "Доп: Рассылка в боте.",
            "top_hours": 0,
        },
    }

    if action in presets:
        await state.update_data(
            action=action,
            description=presets[action]["desc"],
            top_seconds=int(presets[action]["top_hours"] * 3600),
        )
        await call.message.answer(
            f"Вы выбрали:\n<b>{presets[action]['desc']}</b>\n\n👉 Теперь перешлите мне пост для работы:"
        )
        await state.set_state(OrderState.waiting_for_post)
    else:
        dop_names = {
            "dop_pin": "Закреп (укажите количество дней)",
            "dop_top": "Топ (укажите количество часов)",
            "dop_podgon": "Подгон (укажите количество штук)",
        }
        await state.update_data(action=action, base_desc=dop_names[action])
        await call.message.answer(
            f"Вы выбрали: {dop_names[action]}\n👉 Введите числовое значение:"
        )
        await state.set_state(OrderState.waiting_for_custom_value)

    await call.answer()


@router.message(OrderState.waiting_for_custom_value)
async def get_custom_value(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    val = message.text.strip()
    data = await state.get_data()
    action = data["action"]

    top_sec = 0
    if action == "dop_top":
        try:
            top_sec = int(float(val) * 3600)
        except:
            top_sec = 0

    desc = f"Доп: {data['base_desc']} — {val}"
    await state.update_data(
        description=desc, top_seconds=top_sec, custom_val=val
    )

    await message.answer(
        f"Значение принято: {val}\n\n👉 Теперь перешлите мне пост для работы:"
    )
    await state.set_state(OrderState.waiting_for_post)


@router.message(OrderState.waiting_for_post)
async def get_post_for_action(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return

    await state.update_data(
        forward_from_chat=message.chat.id, forward_message_id=message.message_id
    )
    data = await state.get_data()

    preview_text = (
        f"📋 **Предпросмотр заказа:**\n\n"
        f"{data['description']}\n\n"
        f"Сообщение для пересылки прикреплено ✅\n"
        f"Всё верно? Нажмите кнопку ниже."
    )

    await message.answer(
        preview_text, reply_markup=confirm_kb(), parse_mode="Markdown"
    )


@router.callback_query(F.data.in_(["confirm_yes", "confirm_no"]))
async def confirm_order(call: CallbackQuery, state: FSMContext):
    if call.data == "confirm_no":
        await state.clear()
        await call.message.edit_text("❌ Заказ отменен.", reply_markup=None)
        return

    data = await state.get_data()
    chat_id = data.get("forward_from_chat")
    msg_id = data.get("forward_message_id")
    desc = data.get("description", "Задача")
    top_seconds = data.get("top_seconds", 0)

    try:
        bot = call.bot
        await call.message.edit_text(
            "🚀 Заказ подтвержден! Задача принята в работу...",
            reply_markup=None,
        )

        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO active_tasks (task_type, details, chat_id, message_id, top_seconds, status)
                VALUES ($1, $2, $3, $4, $5, 'active')
            """,
                desc,
                desc,
                chat_id,
                msg_id,
                top_seconds,
            )

        asyncio.create_task(
            execute_workflow(bot, chat_id, msg_id, top_seconds)
        )

    except Exception as e:
        logging.error(f"Ошибка выполнения: {e}")
        for admin_id in ADMIN_IDS:
            await bot.send_message(
                admin_id,
                f"⚠️ **Ошибка при выполнении задачи:**\n`{str(e)}`",
                parse_mode="Markdown",
            )

    await state.clear()
    await call.answer()


async def execute_workflow(
    bot: Bot, chat_id: int, message_id: int, top_seconds: int
):
    try:
        await bot.send_message(
            chat_id=CHAT_ID,
            text="/broadcast",
            message_thread_id=TOPIC_BROADCAST,
        )
        await asyncio.sleep(random.randint(10, 15))
        await bot.forward_message(
            chat_id=CHANNEL_ID, from_chat_id=chat_id, message_id=message_id
        )

        if top_seconds > 0:
            await bot.send_message(
                chat_id=CHAT_ID,
                text=f"/stop {top_seconds}",
                message_thread_id=TOPIC_STOP,
            )

    except Exception as e:
        logging.error(f"Ошибка в воркфлоу: {e}")
        for admin_id in ADMIN_IDS:
            await bot.send_message(
                admin_id,
                f"⚠️ Ошибка автоматики рассылки/топа: `{e}`",
                parse_mode="Markdown",
            )


@router.callback_query(F.data == "menu_active")
async def show_active_tasks(call: CallbackQuery):
    async with db_pool.acquire() as conn:
        tasks = await conn.fetch(
            "SELECT id, task_type, status FROM active_tasks WHERE status = 'active'"
        )

    if not tasks:
        await call.message.edit_text(
            "✨ Все задачи полностью выполнены! Активных процессов нет.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="« Назад", callback_data="menu_back")]
                ]
            ),
        )
    else:
        text = "📊 **Текущие активные задачи:**\n\n"
        for t in tasks:
            text += f"• ID {t['id']}: {t['task_type']}\n"
        await call.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="« Назад", callback_data="menu_back")]
                ]
            ),
            parse_mode="Markdown",
        )
    await call.answer()


async def scheduler_podgons(bot: Bot):
    while True:
        now = datetime.now()
        if now.hour in [14, 20] and now.minute == 0:
            try:
                async with db_pool.acquire() as conn:
                    active_tops = await conn.fetchval(
                        "SELECT COUNT(*) FROM active_tasks WHERE top_seconds > 0 AND status = 'active'"
                    )

                if active_tops == 0:
                    podgon_text = random.choice(PODGON_LIST)
                    await bot.send_message(chat_id=CHANNEL_ID, text=podgon_text)
            except Exception as e:
                logging.error(f"Ошибка отправки подгона: {e}")

            await asyncio.sleep(60)
        await asyncio.sleep(30)


# Веб-сервер для бесплатного режима на Render (чтобы сервис не падал)
async def handle(request):
    return web.Response(text="Bot is running!")


async def web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()


async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)

    await init_db()
    logging.info("Бот запущен и подключен к Neon PostgreSQL!")

    # Запускаем веб-сервер и фоновый планировщик подгонов
    await web_server()
    asyncio.create_task(scheduler_podgons(bot))

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
