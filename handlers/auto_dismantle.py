from aiogram import Router, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from db.models import get_auto_dismantle, update_auto_dismantle
from handlers.utils import edit_or_answer

router = Router()

class DismantleStates(StatesGroup):
    choosing_rarity = State()
    setting_min_iv = State()

async def _get_dismantle_text_and_keyboard(user_id: int):
    """Возвращает текст и клавиатуру для меню автопродажи."""
    settings = await get_auto_dismantle(user_id)
    if not settings:
        await update_auto_dismantle(user_id, enabled=0)
        settings = {
            'enabled': 0, 'dismantle_rare': 0, 'dismantle_epic': 0,
            'dismantle_legendary': 0, 'keep_if_trait': 0, 'keep_if_destiny': 0,
            'min_iv_atk': 0, 'min_iv_hp': 0, 'min_iv_def': 0, 'min_iv_spd': 0,
            'min_iv_crit': 0, 'keep_factions': '', 'keep_roles': ''
        }

    status = "✅ Включена" if settings.get('enabled', 0) else "❌ Выключена"
    text = (
        f"⚙ <b>Автопродажа героев</b>\n"
        f"Статус: {status}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"Продавать:\n"
        f"• Rare: {'✅' if settings.get('dismantle_rare', 0) else '❌'}\n"
        f"• Epic: {'✅' if settings.get('dismantle_epic', 0) else '❌'}\n"
        f"• Legendary: {'✅' if settings.get('dismantle_legendary', 0) else '❌'}\n"
        f"Не продавать если есть:\n"
        f"• Трейт: {'✅' if settings.get('keep_if_trait', 0) else '❌'}\n"
        f"• Судьба: {'✅' if settings.get('keep_if_destiny', 0) else '❌'}\n"
        f"Минимальный IV для сохранения:\n"
        f"• ATK: {settings.get('min_iv_atk', 0)}% | HP: {settings.get('min_iv_hp', 0)}%\n"
        f"• DEF: {settings.get('min_iv_def', 0)}% | SPD: {settings.get('min_iv_spd', 0)}%\n"
        f"• CRIT: {settings.get('min_iv_crit', 0)}%\n"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Вкл/Выкл", callback_data="dismantle_toggle")
    builder.button(text="🔵 Rare", callback_data="dismantle_rarity_Rare")
    builder.button(text="🟣 Epic", callback_data="dismantle_rarity_Epic")
    builder.button(text="🟡 Legendary", callback_data="dismantle_rarity_Legendary")
    builder.button(text="🧬 Сохранять с трейтом", callback_data="dismantle_trait")
    builder.button(text="🔮 Сохранять с судьбой", callback_data="dismantle_destiny")
    builder.button(text="📊 Мин. IV", callback_data="dismantle_miniv")
    builder.button(text="🔙 Назад", callback_data="menu")
    builder.adjust(2)

    return text, builder

@router.callback_query(lambda c: c.data == "auto_dismantle")
async def auto_dismantle_menu(callback: types.CallbackQuery):
    text, builder = await _get_dismantle_text_and_keyboard(callback.from_user.id)
    await edit_or_answer(callback.message, text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(lambda c: c.data == "dismantle_toggle")
async def toggle_dismantle(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    settings = await get_auto_dismantle(user_id)
    new_enabled = 0 if (settings and settings.get('enabled', 0)) else 1
    await update_auto_dismantle(user_id, enabled=new_enabled)
    await auto_dismantle_menu(callback)

@router.callback_query(lambda c: c.data.startswith("dismantle_rarity_"))
async def toggle_rarity(callback: types.CallbackQuery):
    rarity = callback.data.split("_")[-1]
    user_id = callback.from_user.id
    settings = await get_auto_dismantle(user_id)
    field = f"dismantle_{rarity.lower()}"
    current = settings[field] if settings else 0
    await update_auto_dismantle(user_id, **{field: 1 - current})
    await auto_dismantle_menu(callback)

@router.callback_query(lambda c: c.data == "dismantle_trait")
async def toggle_trait(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    settings = await get_auto_dismantle(user_id)
    current = settings.get('keep_if_trait', 0) if settings else 0
    await update_auto_dismantle(user_id, keep_if_trait=1 - current)
    await auto_dismantle_menu(callback)

@router.callback_query(lambda c: c.data == "dismantle_destiny")
async def toggle_destiny(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    settings = await get_auto_dismantle(user_id)
    current = settings.get('keep_if_destiny', 0) if settings else 0
    await update_auto_dismantle(user_id, keep_if_destiny=1 - current)
    await auto_dismantle_menu(callback)

@router.callback_query(lambda c: c.data == "dismantle_miniv")
async def choose_miniv_stat(callback: types.CallbackQuery, state: FSMContext):
    builder = InlineKeyboardBuilder()
    for stat in ['atk', 'hp', 'def', 'spd', 'crit']:
        builder.button(text=stat.upper(), callback_data=f"dismantle_setiv_{stat}")
    builder.button(text="🔙 Назад", callback_data="auto_dismantle")
    await edit_or_answer(callback.message, "Выберите характеристику для установки мин. IV:", reply_markup=builder.as_markup())
    await state.set_state(DismantleStates.choosing_rarity)
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("dismantle_setiv_"))
async def ask_miniv_value(callback: types.CallbackQuery, state: FSMContext):
    stat = callback.data.split("_")[-1]
    await state.update_data(iv_stat=stat)
    await callback.message.answer(f"Введите минимальное значение {stat.upper()} (80-120):")
    await state.set_state(DismantleStates.setting_min_iv)
    await callback.answer()

@router.message(DismantleStates.setting_min_iv)
async def save_miniv(message: types.Message, state: FSMContext, bot: Bot):
    try:
        value = int(message.text)
        if 80 <= value <= 120:
            data = await state.get_data()
            stat = data['iv_stat']
            await update_auto_dismantle(message.from_user.id, **{f"min_iv_{stat}": value})
            # Удаляем сообщение с числом
            try:
                await message.delete()
            except:
                pass
            # Отправляем обновлённое меню автопродажи
            text, builder = await _get_dismantle_text_and_keyboard(message.from_user.id)
            await bot.send_message(message.chat.id, text, reply_markup=builder.as_markup(), parse_mode="HTML")
            await state.clear()
        else:
            await message.answer("Введите число от 80 до 120.")
    except ValueError:
        await message.answer("Введите число от 80 до 120.")