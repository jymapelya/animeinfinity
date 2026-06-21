from aiogram import Router, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import Command
from handlers.utils import edit_or_answer
from datetime import datetime, timezone
from db.models import get_active_expeditions, get_player

router = Router()

def get_main_menu():
    """Возвращает клавиатуру главного меню со всеми разделами."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🎁 AFK Награды", callback_data="afk_rewards")
    builder.button(text="🎴 Гача", callback_data="gacha_menu")
    builder.button(text="⚔ Кампания", callback_data="campaign")
    builder.button(text="⚔ Команда", callback_data="team")
    builder.button(text="📚 Коллекция", callback_data="collection")
    builder.button(text="👤 Профиль", callback_data="profile")
    builder.button(text="📦 Реликвии", callback_data="relics")
    builder.button(text="🗺 Экспедиции", callback_data="expeditions")
    builder.button(text="🗼 Башня", callback_data="tower")


    builder.button(text="📚 Вики", callback_data="wiki")
    # Опционально: кнопка фонов
    # builder.button(text="🖼 Фоны", callback_data="backgrounds")
    builder.adjust(2)
    return builder

async def check_notifications(user_id: int) -> str:
    """Возвращает текст уведомлений, если они есть."""
    notes = []
    # AFK-лимит (12 часов)
    player = await get_player(user_id)
    if player:
        last_afk = player.get('last_afk_time')
        if last_afk:
            last_time = datetime.fromisoformat(last_afk)
            if last_time.tzinfo is None:
                last_time = last_time.replace(tzinfo=timezone.utc)
            delta = (datetime.now(timezone.utc) - last_time).total_seconds()
            max_sec = 12 * 3600
            if delta >= max_sec:
                notes.append("🎁 AFK-награды достигли лимита! Соберите их как можно скорее.")

    # Завершённые экспедиции
    active = await get_active_expeditions(user_id)
    if active:
        for exp in active:
            end_time = datetime.fromisoformat(exp['end_time'])
            if datetime.now(timezone.utc) >= end_time:
                notes.append("🗺 Одна из ваших экспедиций завершена! Заберите награды.")
                break  # одного сообщения достаточно

    return "\n".join(notes) if notes else ""

@router.message(Command("menu"))
async def main_menu(message: types.Message):
    notification = await check_notifications(message.from_user.id)
    if notification:
        await message.answer(notification)
    builder = get_main_menu()
    await message.answer("🏠 Главное меню:", reply_markup=builder.as_markup())

@router.callback_query(lambda c: c.data == "menu")
async def back_to_menu(callback: types.CallbackQuery):
    notification = await check_notifications(callback.from_user.id)
    if notification:
        await callback.message.answer(notification)
    builder = get_main_menu()
    await edit_or_answer(callback.message, "🏠 Главное меню:", reply_markup=builder.as_markup())
    await callback.answer()