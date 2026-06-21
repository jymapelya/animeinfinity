from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from dataclasses import dataclass
from typing import Any, Optional

router = Router()

from handlers.afk import afk_rewards
from handlers.gacha import gacha_menu
from handlers.battle import campaign_menu
from handlers.team import team_menu
from handlers.collection import collection_start
from handlers.profile import profile
from handlers.relics import relic_inventory
from handlers.expeditions import expeditions_menu
from handlers.tower import tower_menu
from handlers.wiki import wiki_main_menu

# Заглушка для CallbackQuery с пустым answer()
class FakeCallback:
    def __init__(self, message: types.Message, data: str):
        self.id = "reply_fake"
        self.from_user = message.from_user
        self.message = message
        self.data = data
        self.chat_instance = str(message.chat.id)
        self.inline_message_id = None
        self.bot = None  # не используется, но присутствует

    async def answer(self, text: Optional[str] = None, show_alert: bool = False, **kwargs):
        # Ничего не делаем, просто игнорируем вызов
        return

REPLY_MAPPING = {
    "🎁 AFK Награды": ("afk_rewards", False, False),
    "🎴 Гача": ("gacha_menu", False, False),
    "⚔ Кампания": ("campaign", False, False),
    "⚔ Команда": ("team", True, False),
    "📚 Коллекция": ("collection", True, True),
    "👤 Профиль": ("profile", False, False),
    "📦 Реликвии": ("relics", True, False),
    "🗺 Экспедиции": ("expeditions", True, False),
    "🗼 Башня": ("tower", True, False),
    "📚 Вики": ("wiki", False, False),
}

@router.message(F.text.in_(REPLY_MAPPING.keys()))
async def reply_button_handler(message: types.Message, state: FSMContext, bot: Bot):
    await message.delete()
    handler_name, needs_state, needs_bot = REPLY_MAPPING[message.text]

    fake_callback = FakeCallback(message=message, data=handler_name)

    handlers_map = {
        "afk_rewards": afk_rewards,
        "gacha_menu": gacha_menu,
        "campaign": campaign_menu,
        "team": team_menu,
        "collection": collection_start,
        "profile": profile,
        "relics": relic_inventory,
        "expeditions": expeditions_menu,
        "tower": tower_menu,
        "wiki": wiki_main_menu,

    }
    handler = handlers_map.get(handler_name)
    if not handler:
        return

    if needs_state and needs_bot:
        await handler(fake_callback, state=state, bot=bot)
    elif needs_state:
        await handler(fake_callback, state=state)
    else:
        await handler(fake_callback)