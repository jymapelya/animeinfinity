import os
from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from db.models import (get_db, get_player_relics, equip_relic, unequip_relic,
                       get_unequipped_relics, get_player, get_relic_count_by_id,
                       calculate_team_power)
from engine.data_loader import data_cache
from handlers.utils import edit_or_answer

router = Router()

class RelicStates(StatesGroup):
    browsing = State()
    choosing_char = State()
    choosing_relic = State()
    relic_search = State()
    char_search = State()
    char_filter = State()
    relic_page = State()          # новое: листание страниц с реликвиями
    relic_search_name = State()

RELICS_PER_PAGE = 5
HEROES_PER_PAGE = 5
RELICS_PER_PAGE_CHOOSE = 5

RARITY_EMOJI_RELIC = {'Common':'⚪','Rare':'🔵','Epic':'🟣','Legendary':'🟡'}
EFFECT_EMOJI = {'hp':'❤️','atk':'⚔️','def':'🛡️','spd':'💨','crit':'💥','gold':'💰'}

ROLE_EMOJI = {
    'Tank': '🛡️', 'Warrior': '⚔️', 'Assassin': '🗡️',
    'Mage': '🔮', 'Support': '💚', 'Summoner': '🐉'
}
VARIANT_EMOJI = {'Normal':'','Shiny':'✨','Golden':'🌟','Prismatic':'💫','Celestial':'☄️'}

def iv_emoji(val):
    if val < 90: return '🔴'
    if val < 100: return '🟡'
    if val < 110: return '🟢'
    return '🔵'

def get_actual_stats(char: dict):
    base = data_cache.characters.get(char['base_char_id'], {})
    base_hp = base.get('hp', 100)
    base_atk = base.get('atk', 50)
    base_def = base.get('def', 30)
    base_spd = base.get('spd', 80)
    base_crit = base.get('crit', 5)
    iv_hp = char.get('iv_hp', 100)
    iv_atk = char.get('iv_atk', 100)
    iv_def = char.get('iv_def', 100)
    iv_spd = char.get('iv_spd', 100)
    iv_crit = char.get('iv_crit', 100)
    return {
        'hp': round(base_hp * iv_hp / 100),
        'atk': round(base_atk * iv_atk / 100),
        'def': round(base_def * iv_def / 100),
        'spd': round(base_spd * iv_spd / 100),
        'crit': round(base_crit * iv_crit / 100),
        'iv_emoji_hp': iv_emoji(iv_hp),
        'iv_emoji_atk': iv_emoji(iv_atk),
        'iv_emoji_def': iv_emoji(iv_def),
        'iv_emoji_spd': iv_emoji(iv_spd),
        'iv_emoji_crit': iv_emoji(iv_crit)
    }

# ─────────────────────────────────────────
# ИНВЕНТАРЬ РЕЛИКВИЙ
# ─────────────────────────────────────────
@router.callback_query(lambda c: c.data == "relics")
async def relic_inventory(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    relics_dict = await get_player_relics(user_id)

    if not relics_dict:
        # Пустой инвентарь, но оставляем возможность пойти в баннер
        builder = InlineKeyboardBuilder()
        builder.button(text="🎴 Баннер Реликвий", callback_data="relic_gacha_menu")
        builder.button(text="🔙 Назад", callback_data="menu")
        await edit_or_answer(callback.message, "📭 У вас пока нет реликвий.", reply_markup=builder.as_markup())
        await callback.answer()
        return

    all_relics = []
    for relic_id, qty in relics_dict.items():
        relic = data_cache.relics.get(relic_id)
        if relic:
            all_relics.append({
                'relic_id': relic_id,
                'name': relic['name'],
                'rarity': relic['rarity'],
                'effect': relic['effect'],
                'value': relic['value'],
                'quantity': qty
            })

    await state.update_data(all_relics=all_relics, original_relics=all_relics, page=0,
                            filter_type='all', filter_value='all')
    await state.set_state(RelicStates.browsing)
    await show_relic_page(callback.message, state)
    await callback.answer()

async def show_relic_page(message: types.Message, state: FSMContext):
    data = await state.get_data()
    all_relics = data.get('all_relics', [])
    page = data.get('page', 0)
    total = len(all_relics)
    total_pages = max(1, (total + RELICS_PER_PAGE - 1) // RELICS_PER_PAGE)
    start = page * RELICS_PER_PAGE
    end = start + RELICS_PER_PAGE
    relics_on_page = all_relics[start:end]

    text = f"📦 <b>Реликвии ({total} шт.)</b>\n"
    if not relics_on_page:
        text += "Нет подходящих реликвий."
    else:
        for r in relics_on_page:
            eff_icon = EFFECT_EMOJI.get(r['effect'], '❓')
            rarity_emoji = RARITY_EMOJI_RELIC.get(r['rarity'], '')
            text += f"{rarity_emoji} {r['name']}: +{r['value']}% {eff_icon} {r['effect'].upper()} (x{r['quantity']})\n"

    builder = InlineKeyboardBuilder()
    nav = []
    if page > 0:
        nav.append(('◀', 'relic_prev'))
    nav.append((f'📄 {page+1}/{total_pages}', 'relic_page_info'))
    if page < total_pages - 1:
        nav.append(('▶', 'relic_next'))
    for t, cb in nav:
        builder.button(text=t, callback_data=cb)

    builder.button(text='🔍', callback_data='relic_search')
    builder.button(text='🎛 Фильтр', callback_data='relic_filter_menu')
    if data.get('filter_type') != 'all':
        builder.button(text='🔄 Сброс', callback_data='relic_filter_reset')

    builder.button(text='🎴 Баннер', callback_data='relic_gacha_menu')
    builder.button(text='⚔ Надеть', callback_data='relic_equip')
    builder.button(text='🔙 Назад', callback_data='menu')
    builder.adjust(3, 2, 1)
    await edit_or_answer(message, text, reply_markup=builder.as_markup(), parse_mode="HTML")

# ─────────────────────────────────────────
# ПАГИНАЦИЯ, ПОИСК, ФИЛЬТРЫ ИНВЕНТАРЯ
# ─────────────────────────────────────────
@router.callback_query(lambda c: c.data in ['relic_prev','relic_next'])
async def relic_page_change(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    page = data.get('page', 0)
    if callback.data == 'relic_prev': page -= 1
    else: page += 1
    await state.update_data(page=page)
    await show_relic_page(callback.message, state)
    await callback.answer()

@router.callback_query(lambda c: c.data == 'relic_search')
async def relic_search_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("🔍 Введите название реликвии:")
    await state.set_state(RelicStates.relic_search)
    await callback.answer()

@router.message(RelicStates.relic_search)
async def relic_search_result(message: types.Message, state: FSMContext):
    query = message.text.strip().lower()
    data = await state.get_data()
    original = data.get('original_relics', [])
    results = [r for r in original if query in r['name'].lower()]
    if not results:
        await message.answer("❌ Ничего не найдено.")
        await state.set_state(RelicStates.browsing)
        return
    await state.update_data(all_relics=results, page=0)
    await state.set_state(RelicStates.browsing)
    await show_relic_page(message, state)
    await message.delete()

@router.callback_query(lambda c: c.data == 'relic_filter_menu')
async def relic_filter_menu(callback: types.CallbackQuery, state: FSMContext):
    builder = InlineKeyboardBuilder()
    for rar in ['Common','Rare','Epic','Legendary']:
        builder.button(text=rar, callback_data=f'relic_frar_{rar}')
    for eff, icon in EFFECT_EMOJI.items():
        builder.button(text=f"{icon} {eff}", callback_data=f'relic_feff_{eff}')
    builder.button(text='🔙 Назад', callback_data='relic_back')
    builder.adjust(2)
    await edit_or_answer(callback.message, "Фильтр по редкости или эффекту:", reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith('relic_frar_'))
async def apply_rarity_filter(callback: types.CallbackQuery, state: FSMContext):
    rarity = callback.data.split('_')[-1]
    data = await state.get_data()
    original = data.get('original_relics', [])
    filtered = [r for r in original if r['rarity'] == rarity]
    if not filtered:
        await callback.answer("Нет реликвий этой редкости.")
        return
    await state.update_data(all_relics=filtered, page=0, filter_type='rarity', filter_value=rarity)
    await state.set_state(RelicStates.browsing)
    await show_relic_page(callback.message, state)
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith('relic_feff_'))
async def apply_effect_filter(callback: types.CallbackQuery, state: FSMContext):
    effect = callback.data.split('_')[-1]
    data = await state.get_data()
    original = data.get('original_relics', [])
    filtered = [r for r in original if r['effect'] == effect]
    if not filtered:
        await callback.answer("Нет реликвий с этим эффектом.")
        return
    await state.update_data(all_relics=filtered, page=0, filter_type='effect', filter_value=effect)
    await state.set_state(RelicStates.browsing)
    await show_relic_page(callback.message, state)
    await callback.answer()

@router.callback_query(lambda c: c.data == 'relic_filter_reset')
async def reset_relic_filter(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    original = data.get('original_relics', [])
    await state.update_data(all_relics=original, page=0, filter_type='all', filter_value='all')
    await state.set_state(RelicStates.browsing)
    await show_relic_page(callback.message, state)
    await callback.answer()

@router.callback_query(lambda c: c.data == 'relic_back')
async def relic_back(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(RelicStates.browsing)
    await show_relic_page(callback.message, state)
    await callback.answer()

# ─────────────────────────────────────────
# НАДЕВАНИЕ РЕЛИКВИИ (с поиском и фильтром)
# ─────────────────────────────────────────
@router.callback_query(lambda c: c.data == 'relic_equip')
async def choose_character(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, base_char_id, variant, iv_hp, iv_atk, iv_def, iv_spd, iv_crit, copy_number FROM player_characters WHERE player_id=?",
            (user_id,)
        )
        rows = await cursor.fetchall()
        all_chars = [dict(r) for r in rows]
    finally:
        await db.close()

    if not all_chars:
        await callback.message.answer("У вас нет персонажей.")
        await callback.answer()
        return

    await state.update_data(all_chars=all_chars, original_chars=all_chars, char_page=0)
    await state.set_state(RelicStates.choosing_char)
    await show_char_page(callback.message, state)
    await callback.answer()

async def show_char_page(message: types.Message, state: FSMContext):
    data = await state.get_data()
    all_chars = data.get('all_chars', [])
    page = data.get('char_page', 0)
    total_pages = max(1, (len(all_chars) + HEROES_PER_PAGE - 1) // HEROES_PER_PAGE)
    start = page * HEROES_PER_PAGE
    end = start + HEROES_PER_PAGE
    chars_on_page = all_chars[start:end]

    builder = InlineKeyboardBuilder()
    for char in chars_on_page:
        base = data_cache.characters[char['base_char_id']]
        role_icon = ROLE_EMOJI.get(base['role'], '❓')
        label = f"{role_icon} {base['name']} #{char.get('copy_number', '?')}"
        builder.button(text=label, callback_data=f"relic_char_{char['id']}")

    nav = []
    if page > 0:
        nav.append(('◀', 'rchar_prev'))
    nav.append((f'📄 {page+1}/{total_pages}', 'rchar_page'))
    if page < total_pages - 1:
        nav.append(('▶', 'rchar_next'))
    for t, cb in nav:
        builder.button(text=t, callback_data=cb)

    builder.button(text='🔍 Поиск героя', callback_data='rchar_search')
    builder.button(text='🔽 Фильтр по роли', callback_data='rchar_filter')
    builder.button(text='🔙 Назад', callback_data='relics')
    builder.adjust(1)

    await edit_or_answer(message, "Выберите героя для экипировки:", reply_markup=builder.as_markup())

@router.callback_query(lambda c: c.data.startswith("relic_char_"))
async def relic_char_handler(callback: types.CallbackQuery, state: FSMContext):
    # Извлекаем char_id из callback_data (формат "relic_char_<id>")
    char_id = int(callback.data.split("_")[-1])
    await state.update_data(char_id=char_id)
    user_id = callback.from_user.id

    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, relic_id FROM player_relics WHERE player_id=? AND equipped=0",
            (user_id,)
        )
        relics_raw = await cursor.fetchall()
        relics = [dict(r) for r in relics_raw]
    finally:
        await db.close()

    if not relics:
        await callback.message.answer("Нет свободных реликвий.")
        await callback.answer()
        return

    await state.update_data(
        choose_relics=relics,
        choose_relics_original=relics.copy(),
        choose_relic_page=0
    )
    await state.set_state(RelicStates.choosing_relic)
    await show_choose_relic_page(callback.message, state)
    await callback.answer()

@router.callback_query(lambda c: c.data in ['rchar_prev','rchar_next'])
async def char_page_change(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    page = data.get('char_page', 0)
    if callback.data == 'rchar_prev': page -= 1
    else: page += 1
    await state.update_data(char_page=page)
    await show_char_page(callback.message, state)
    await callback.answer()

@router.callback_query(lambda c: c.data == 'rchar_search')
async def char_search_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("🔍 Введите имя героя:")
    await state.set_state(RelicStates.char_search)
    await callback.answer()

@router.message(RelicStates.char_search)
async def char_search_result(message: types.Message, state: FSMContext):
    query = message.text.strip().lower()
    data = await state.get_data()
    original = data.get('original_chars', [])
    results = [c for c in original if query in data_cache.characters.get(c['base_char_id'], {}).get('name', '').lower()]
    if not results:
        await message.answer("❌ Ничего не найдено.")
        await state.set_state(RelicStates.choosing_char)
        return
    await state.update_data(all_chars=results, char_page=0)
    await state.set_state(RelicStates.choosing_char)
    await show_char_page(message, state)
    await message.delete()

@router.callback_query(lambda c: c.data == 'rchar_filter')
async def char_filter_menu(callback: types.CallbackQuery, state: FSMContext):
    builder = InlineKeyboardBuilder()
    roles = ['Tank', 'Warrior', 'Assassin', 'Mage', 'Support', 'Summoner']
    for role in roles:
        builder.button(text=role, callback_data=f"rchar_frole_{role}")
    builder.button(text="🔙 Назад", callback_data="relic_equip")
    builder.adjust(2)
    await edit_or_answer(callback.message, "Фильтр по роли:", reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith('rchar_frole_'))
async def apply_char_role_filter(callback: types.CallbackQuery, state: FSMContext):
    role = callback.data.split('_')[-1]
    data = await state.get_data()
    original = data.get('original_chars', [])
    filtered = [c for c in original if data_cache.characters.get(c['base_char_id'], {}).get('role') == role]
    if not filtered:
        await callback.answer("Нет героев этой роли.")
        return
    await state.update_data(all_chars=filtered, char_page=0)
    await state.set_state(RelicStates.choosing_char)
    await show_char_page(callback.message, state)
    await callback.answer()

# ─────────────────────────────────────────
# ВЫБОР РЕЛИКВИИ И НАДЕВАНИЕ
# ─────────────────────────────────────────
async def choose_relic(callback: types.CallbackQuery, state: FSMContext):
    char_id = int(callback.data.split("_")[-1])
    await state.update_data(char_id=char_id)
    user_id = callback.from_user.id

    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, relic_id FROM player_relics WHERE player_id=? AND equipped=0",
            (user_id,)
        )
        relics_raw = await cursor.fetchall()
        relics = [dict(r) for r in relics_raw]
    finally:
        await db.close()

    if not relics:
        await callback.message.answer("Нет свободных реликвий.")
        await callback.answer()
        return

    await state.update_data(
        choose_relics=relics,
        choose_relics_original=relics.copy(),
        choose_relic_page=0
    )
    await state.set_state(RelicStates.choosing_relic)
    await show_choose_relic_page(callback.message, state)
    await callback.answer()

async def show_choose_relic_page(message: types.Message, state: FSMContext):
    data = await state.get_data()
    all_relics = data.get('choose_relics', [])
    page = data.get('choose_relic_page', 0)
    total_pages = max(1, (len(all_relics) + RELICS_PER_PAGE_CHOOSE - 1) // RELICS_PER_PAGE_CHOOSE)
    start = page * RELICS_PER_PAGE_CHOOSE
    end = start + RELICS_PER_PAGE_CHOOSE
    relics_on_page = all_relics[start:end]

    builder = InlineKeyboardBuilder()
    for r in relics_on_page:
        relic = data_cache.relics[r['relic_id']]
        eff_icon = EFFECT_EMOJI.get(relic['effect'], '')
        builder.button(
            text=f"{relic['name']} (+{relic['value']}% {eff_icon})",
            callback_data=f"relic_pick_{r['id']}"
        )

    nav_buttons = []
    if page > 0:
        nav_buttons.append(("◀", "relic_choose_page_prev"))
    if page < total_pages - 1:
        nav_buttons.append((f"▶ {page+1}/{total_pages}", "relic_choose_page_next"))
    elif total_pages > 1:
        nav_buttons.append((f"📄 {page+1}/{total_pages}", "relic_choose_page_info"))
    for text, cb in nav_buttons:
        builder.button(text=text, callback_data=cb)

    builder.button(text="🔍 Поиск", callback_data="relic_choose_search")
    builder.button(text="🔙 Назад", callback_data="relic_equip")
    builder.adjust(1)

    await edit_or_answer(message, "Выберите реликвию:", reply_markup=builder.as_markup())

# Пагинация
@router.callback_query(lambda c: c.data in ['relic_choose_page_prev', 'relic_choose_page_next'])
async def relic_choose_page_change(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    page = data.get('choose_relic_page', 0)
    if callback.data == 'relic_choose_page_prev':
        page -= 1
    else:
        page += 1
    await state.update_data(choose_relic_page=page)
    await show_choose_relic_page(callback.message, state)
    await callback.answer()

# Поиск реликвии
@router.callback_query(lambda c: c.data == 'relic_choose_search')
async def relic_choose_search_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("🔍 Введите название реликвии:")
    await state.set_state(RelicStates.relic_search_name)
    await callback.answer()

@router.message(RelicStates.relic_search_name)
async def relic_choose_search_result(message: types.Message, state: FSMContext):
    query = message.text.strip().lower()
    data = await state.get_data()
    original = data.get('choose_relics_original', [])
    results = []
    for r in original:
        relic = data_cache.relics.get(r['relic_id'])
        if relic and query in relic['name'].lower():
            results.append(r)
    if not results:
        await message.answer("❌ Ничего не найдено.")
        await state.set_state(RelicStates.choosing_relic)
        return
    await state.update_data(choose_relics=results, choose_relic_page=0)
    await state.set_state(RelicStates.choosing_relic)
    await show_choose_relic_page(message, state)
    await message.delete()


@router.callback_query(lambda c: c.data.startswith("relic_pick_"))
async def apply_relic(callback: types.CallbackQuery, state: FSMContext):
    relic_instance_id = int(callback.data.split("_")[-1])
    data = await state.get_data()
    char_id = data['char_id']
    user_id = callback.from_user.id

    success = await equip_relic(user_id, char_id, relic_instance_id)
    if success:
        await callback.message.answer("✅ Реликвия надета!")
        await calculate_team_power(user_id)
    else:
        await callback.message.answer("❌ Ошибка при надевании.")
    await state.clear()
    await callback.answer()