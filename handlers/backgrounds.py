from aiogram import Router, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from db.models import get_player_backgrounds, set_active_background, get_player
from engine.data_loader import data_cache
from handlers.utils import edit_or_answer

router = Router()

@router.callback_query(lambda c: c.data == "backgrounds")
async def backgrounds_list(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    backgrounds = await get_player_backgrounds(user_id)

    builder = InlineKeyboardBuilder()

    if not backgrounds:
        text = "🖼 У вас пока нет фонов. Крутите баннер фонов!"
    else:
        text = "🖼 <b>Ваши фоны:</b>\n"
        for entry in backgrounds:
            bg = data_cache.backgrounds.get(entry['background_id'])
            if bg:
                status = "✅" if entry['equipped'] else ""
                text += f"{status} {bg['name']} ({bg['rarity']}) x{entry['quantity']}\n"
                if not entry['equipped']:
                    builder.button(text=f"Установить: {bg['name']}", callback_data=f"bg_set_{entry['id']}")

    builder.button(text="🎴 Баннер фонов", callback_data="bg_gacha_menu")
    builder.button(text="🔙 Назад", callback_data="profile")
    builder.adjust(1)

    await edit_or_answer(callback.message, text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("bg_set_"))
async def set_background(callback: types.CallbackQuery):
    instance_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    await set_active_background(user_id, instance_id)
    await backgrounds_list(callback)
    await callback.answer("Фон установлен!")