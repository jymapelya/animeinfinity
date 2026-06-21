from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from db.models import create_player, add_character, set_player_currency, update_player
from engine.data_loader import data_cache
from config import START_GEMS, START_TICKETS
import random

router = Router()

def get_main_reply_keyboard():
    """Постоянная клавиатура главного меню."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎁 AFK Награды"), KeyboardButton(text="🎴 Гача")],
            [KeyboardButton(text="⚔ Кампания"), KeyboardButton(text="⚔ Команда")],
            [KeyboardButton(text="📚 Коллекция"), KeyboardButton(text="👤 Профиль")],
            [KeyboardButton(text="📦 Реликвии"), KeyboardButton(text="🗺 Экспедиции")],
            [KeyboardButton(text="🗼 Башня"), KeyboardButton(text="📚 Вики")],
        ],
        resize_keyboard=True,
        persistent=True
    )

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    created = await create_player(user_id, message.from_user.full_name)

    if created:
        # Выдаём стартовый набор
        rare_chars = [c for c in data_cache.characters.values() if c['rarity'] == 'Rare']
        chosen_rares = random.sample(rare_chars, min(3, len(rare_chars)))
        for rc in chosen_rares:
            await add_character(user_id, rc['id'], variant='Normal',
                                iv_hp=100, iv_atk=100, iv_def=100, iv_spd=100, iv_crit=100)

        epic_chars = [c for c in data_cache.characters.values() if c['rarity'] == 'Epic']
        if epic_chars:
            ep = random.choice(epic_chars)
            await add_character(user_id, ep['id'], variant='Normal',
                                iv_hp=100, iv_atk=100, iv_def=100, iv_spd=100, iv_crit=100)

        await set_player_currency(user_id, START_GEMS, START_TICKETS)
        await message.answer(
            "🎉 Добро пожаловать в Anime Infinity: Ascension!\n"
            "Ты получил стартовый отряд из 3 Rare и 1 Epic героя, а также 1000 гемов и 10 билетов."
        )
    else:
        await message.answer("С возвращением!")

    # Всегда отправляем постоянную клавиатуру
    await message.answer("Используй кнопки ниже для навигации:", reply_markup=get_main_reply_keyboard())