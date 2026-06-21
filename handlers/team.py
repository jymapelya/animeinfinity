from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from db.models import (get_db, set_team_slot, clear_team_slot, get_team_ids,
                       calculate_team_power, get_equipped_relic)
from engine.data_loader import data_cache
from engine.faction_synergy import calculate_faction_synergy
from handlers.utils import edit_or_answer

router = Router()

class TeamStates(StatesGroup):
    selecting_slot = State()
    selecting_hero = State()
    preview_hero = State()
    choosing_filter = State()
    filter_role = State()
    filter_rarity = State()
    filter_faction = State()

ROLE_EMOJI = {
    'Tank': '🛡️', 'Warrior': '⚔️', 'Assassin': '🗡️',
    'Mage': '🔮', 'Support': '💚', 'Summoner': '🐉'
}
VARIANT_EMOJI = {'Normal':'','Shiny':'✨','Golden':'🌟','Prismatic':'💫','Celestial':'☄️'}
FACTION_EMOJI = {
    'Flame': '🔥', 'Ocean': '🌊', 'Storm': '⚡', 'Shadow': '🌑',
    'Light': '✨', 'Guardian': '🛡', 'Dragon': '🐉', 'Void': '☠'
}

HEROES_PER_PAGE = 5

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

# ─────────────────────────────────────────────
# ГЛАВНОЕ ОКНО КОМАНДЫ
# ─────────────────────────────────────────────
async def show_team(message: types.Message, user_id: int, state: FSMContext):
    team_ids = await get_team_ids(user_id)
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, base_char_id, variant, iv_hp, iv_atk, iv_def, iv_spd, iv_crit, copy_number FROM player_characters WHERE player_id=?",
            (user_id,))
        rows = await cursor.fetchall()
        all_chars = [dict(r) for r in rows]
    finally:
        await db.close()

    char_by_id = {c['id']: c for c in all_chars}
    team_chars = []
    text = "⚔ <b>Ваша команда:</b>\n"
    for i in range(5):
        char_id = team_ids.get(i)
        if char_id and char_id in char_by_id:
            char = char_by_id[char_id]
            team_chars.append(char)
            base = data_cache.characters[char['base_char_id']]
            role_icon = ROLE_EMOJI.get(base['role'], '❓')
            variant_emoji = VARIANT_EMOJI.get(char.get('variant', 'Normal'), '')
            faction_icon = FACTION_EMOJI.get(base['faction'], '')
            stats = get_actual_stats(char)
            atk_str = f"{stats['iv_emoji_atk']}⚔️{stats['atk']}"
            text += f"{i+1}. {role_icon} {base['name']} #{char.get('copy_number', '?')} {variant_emoji} {faction_icon} ({atk_str})\n"
        else:
            text += f"{i+1}. 🕳 пусто\n"

    if team_chars:
        synergy_bonus, faction_counts = calculate_faction_synergy(team_chars)
        if synergy_bonus > 0:
            text += f"\n🤝 Синергия: +{int(synergy_bonus*100)}% HP/ATK\n"
            for f, cnt in faction_counts.items():
                if cnt >= 2:
                    text += f"   {FACTION_EMOJI.get(f,'')} {f}: x{cnt}\n"

    builder = InlineKeyboardBuilder()
    for i in range(5):
        builder.button(text=f"⚙ Слот {i+1}", callback_data=f"team_slot_{i}")
    builder.button(text="🔙 Назад", callback_data="menu")
    builder.adjust(2)
    await edit_or_answer(message, text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await state.set_state(TeamStates.selecting_slot)

@router.callback_query(lambda c: c.data == "team")
async def team_menu(callback: types.CallbackQuery, state: FSMContext):
    await show_team(callback.message, callback.from_user.id, state)
    await callback.answer()

# ─────────────────────────────────────────────
# ВЫБОР СЛОТА (сразу показывает описание и список героев)
# ─────────────────────────────────────────────
@router.callback_query(lambda c: c.data.startswith('team_slot_'))
async def select_slot(callback: types.CallbackQuery, state: FSMContext):
    slot = int(callback.data.split('_')[-1])
    user_id = callback.from_user.id
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, base_char_id, variant, iv_hp, iv_atk, iv_def, iv_spd, iv_crit, copy_number FROM player_characters WHERE player_id=?",
            (user_id,))
        rows = await cursor.fetchall()
        all_chars = [dict(r) for r in rows]
    finally:
        await db.close()

    if not all_chars:
        await edit_or_answer(callback.message, "У вас нет персонажей для выбора.",
                             reply_markup=InlineKeyboardBuilder().button(text="🔙 Назад", callback_data="team").as_markup())
        await callback.answer()
        return

    await state.update_data(slot=slot, all_chars=all_chars, original_all_chars=all_chars.copy(), page=0,
                            active_filters={})
    await state.set_state(TeamStates.selecting_hero)
    await show_hero_page(callback.message, state)
    await callback.answer()

# ─────────────────────────────────────────────
# СТРАНИЦА СПИСКА ГЕРОЕВ (с заголовком слота)
# ─────────────────────────────────────────────
async def show_hero_page(message: types.Message, state: FSMContext):
    data = await state.get_data()
    all_chars = data.get('all_chars')
    slot = data.get('slot', 0)

    if not all_chars:
        user_id = data.get('user_id') or message.chat.id
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT id, base_char_id, variant, iv_hp, iv_atk, iv_def, iv_spd, iv_crit, copy_number FROM player_characters WHERE player_id=?",
                (user_id,))
            rows = await cursor.fetchall()
            all_chars = [dict(r) for r in rows]
        finally:
            await db.close()
        if not all_chars:
            await edit_or_answer(message, "У вас нет персонажей для выбора.",
                                 reply_markup=InlineKeyboardBuilder().button(text="🔙 Назад", callback_data="team").as_markup())
            return
        original_chars = all_chars.copy()
        await state.update_data(all_chars=all_chars, original_all_chars=original_chars, page=0)

    page = data.get('page', 0)
    total_pages = max(1, (len(all_chars) + HEROES_PER_PAGE - 1) // HEROES_PER_PAGE)
    start = page * HEROES_PER_PAGE
    end = start + HEROES_PER_PAGE
    chars_on_page = all_chars[start:end]

    # Заголовок с описанием слота
    from engine.formation_system import SLOT_EFFECTS
    slot_effect = SLOT_EFFECTS.get(slot, {})
    slot_name = slot_effect.get('name', f'Слот {slot+1}')
    slot_desc = slot_effect.get('desc', 'Обычный слот')
    role_tips = {
        0: "🛡️ Идеально для Танков",
        1: "⚔️ Идеально для Воинов и Ассасинов",
        2: "💚 Идеально для Саппортов",
        3: "🌀 Идеально для Магов и Саппортов",
        4: "⭐ Универсальный слот"
    }
    tip = role_tips.get(slot, "")

    header = (
        f"🎯 <b>{slot_name}</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"{slot_desc}\n"
        f"{tip}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"Выберите героя для этого слота:\n"
    )

    equipped_ids = set()
    for char in all_chars:
        relic = await get_equipped_relic(char['id'])
        if relic:
            equipped_ids.add(char['id'])

    builder = InlineKeyboardBuilder()
    for char in chars_on_page:
        base = data_cache.characters[char['base_char_id']]
        role_icon = ROLE_EMOJI.get(base['role'], '❓')
        relic_marker = " 📦" if char['id'] in equipped_ids else ""
        label = f"{role_icon} {base['name']} #{char.get('copy_number', '?')}{relic_marker}"
        builder.button(text=label, callback_data=f"team_preview_{char['id']}")

    nav_buttons = []
    if page > 0:
        nav_buttons.append(("◀", "page_prev"))
    if page < total_pages - 1:
        nav_buttons.append((f"▶ {page+1}/{total_pages}", "page_next"))
    elif total_pages > 1:
        nav_buttons.append((f"📄 {page+1}/{total_pages}", "page_info"))
    for text, cb in nav_buttons:
        builder.button(text=text, callback_data=cb)

    builder.button(text="🔍 Поиск", callback_data="team_hero_search")
    builder.button(text="🔽 Фильтр", callback_data="team_hero_filter")
    builder.button(text="🕳 Очистить слот", callback_data=f"team_clear_{data.get('slot', 0)}")
    builder.button(text="🔙 В команду", callback_data="team")
    builder.adjust(1)

    await edit_or_answer(message, header, reply_markup=builder.as_markup(), parse_mode="HTML")


# ─────────────────────────────────────────────
# ПРЕВЬЮ ГЕРОЯ (полная инфа + реликвия + навыки)
# ─────────────────────────────────────────────
@router.callback_query(lambda c: c.data.startswith('team_preview_'))
async def preview_hero(callback: types.CallbackQuery, state: FSMContext):
    char_id = int(callback.data.split('_')[-1])
    data = await state.get_data()
    all_chars = data.get('all_chars', [])
    slot = data.get('slot', 0)

    hero = next((c for c in all_chars if c['id'] == char_id), None)
    if not hero:
        await callback.answer("Герой не найден.")
        return

    base = data_cache.characters.get(hero['base_char_id'], {})
    role_icon = ROLE_EMOJI.get(base.get('role', ''), '❓')
    faction_icon = FACTION_EMOJI.get(base.get('faction', ''), '')
    variant_emoji = VARIANT_EMOJI.get(hero.get('variant', 'Normal'), '')
    stats = get_actual_stats(hero)

    text = (
        f"{role_icon} <b>{base.get('name', '???')} #{hero.get('copy_number', '?')}</b> {variant_emoji} {faction_icon}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🌟 Редкость: {base.get('rarity','')} | ⭐ {hero.get('awakening_stars',0)}★\n"
    )

    if hero.get('trait'):
        trait = data_cache.traits.get(hero['trait'])
        if trait:
            text += f"🧬 Trait: {trait.get('name', hero['trait'])} — {trait.get('desc', '')}\n"
        else:
            text += f"🧬 Trait: {hero['trait']}\n"

    if hero.get('destiny'):
        destiny = data_cache.destinies.get(hero['destiny'])
        if destiny:
            text += f"🔮 Destiny: {destiny.get('name', hero['destiny'])} — {destiny.get('desc', '')}\n"
        else:
            text += f"🔮 Destiny: {hero['destiny']}\n"

    relic_data = await get_equipped_relic(hero['id'])
    if relic_data:
        relic = data_cache.relics.get(relic_data['relic_id'])
        if relic:
            eff_icon = {'hp':'❤️','atk':'⚔️','def':'🛡️','spd':'💨','crit':'💥','gold':'💰'}.get(relic['effect'],'')
            text += f"📦 Реликвия: {relic['name']} (+{relic['value']}% {eff_icon} {relic['effect'].upper()})\n"

    # Навыки
    skills = base.get('skills', [])
    if skills:
        text += "━━━━━━━━━━━━━━━━\n<b>Навыки:</b>\n"
        for sid in skills:
            skill = data_cache.skills.get(sid)
            if skill:
                skill_name = skill.get('name', sid)
                skill_type = skill.get('type', '?')
                if skill_type == 'damage':
                    desc = f"⚔️ Урон (x{skill.get('multiplier',1.0)})"
                elif skill_type == 'heal':
                    desc = f"💚 Лечение (x{skill.get('multiplier',0.2)})"
                elif skill_type == 'buff':
                    desc = f"✨ Бафф {skill.get('stat','?')} +{int(skill.get('value',0)*100)}%"
                elif skill_type == 'debuff':
                    desc = f"🌀 Дебафф {skill.get('stat','?')} {int(skill.get('value',0)*100)}%"
                elif skill_type == 'summon':
                    desc = "🐉 Призыв"
                else:
                    desc = "Особый эффект"
                cd = skill.get('cooldown', 0)
                cd_text = f" (CD: {cd})" if cd else ""
                text += f"• {skill_name}{cd_text}: {desc}\n"

    text += (
        f"━━━━━━━━━━━━━━━━\n"
        f"❤️ HP: {stats['hp']} ({stats['iv_emoji_hp']} {hero['iv_hp']}%)\n"
        f"⚔️ ATK: {stats['atk']} ({stats['iv_emoji_atk']} {hero['iv_atk']}%)\n"
        f"🛡️ DEF: {stats['def']} ({stats['iv_emoji_def']} {hero['iv_def']}%)\n"
        f"💨 SPD: {stats['spd']} ({stats['iv_emoji_spd']} {hero['iv_spd']}%)\n"
        f"💥 CRIT: {stats['crit']} ({stats['iv_emoji_crit']} {hero['iv_crit']}%)\n"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text=f"✅ Надеть в слот {slot+1}", callback_data=f"team_equip_{char_id}")
    builder.button(text="🔙 Назад к списку", callback_data="team_back_to_list")
    builder.adjust(1)

    await callback.message.delete()
    await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await state.set_state(TeamStates.preview_hero)

@router.callback_query(lambda c: c.data.startswith('team_equip_'))
async def equip_hero(callback: types.CallbackQuery, state: FSMContext):
    char_id = int(callback.data.split('_')[-1])
    data = await state.get_data()
    slot = data['slot']
    user_id = callback.from_user.id
    await set_team_slot(user_id, slot, char_id)
    await calculate_team_power(user_id)
    await callback.message.delete()
    await show_team(callback.message, user_id, state)
    await callback.answer("Герой добавлен!")

@router.callback_query(lambda c: c.data == 'team_back_to_list')
async def back_to_hero_list(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    original = data.get('original_all_chars', [])
    if not original:
        user_id = callback.from_user.id
        db = await get_db()
        try:
            cursor = await db.execute(
                "SELECT id, base_char_id, variant, iv_hp, iv_atk, iv_def, iv_spd, iv_crit, copy_number FROM player_characters WHERE player_id=?",
                (user_id,))
            rows = await cursor.fetchall()
            original = [dict(r) for r in rows]
        finally:
            await db.close()
        await state.update_data(original_all_chars=original)
    await state.update_data(all_chars=original, active_filters={}, page=0)
    await state.set_state(TeamStates.selecting_hero)
    await callback.message.delete()
    await show_hero_page(callback.message, state)
    await callback.answer()

# ─────────────────────────────────────────────
# ПАГИНАЦИЯ И ПОИСК
# ─────────────────────────────────────────────
@router.callback_query(lambda c: c.data in ['page_prev', 'page_next'])
async def change_page(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    page = data.get('page', 0)
    if callback.data == 'page_prev': page -= 1
    else: page += 1
    await state.update_data(page=page)
    await show_hero_page(callback.message, state)
    await callback.answer()

@router.callback_query(lambda c: c.data == 'team_hero_search')
async def hero_search_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("🔍 Введите имя героя:")
    await state.set_state(TeamStates.selecting_hero)
    await callback.answer()

@router.message(TeamStates.selecting_hero)
async def hero_search_result(message: types.Message, state: FSMContext):
    query = message.text.strip().lower()
    data = await state.get_data()
    original = data.get('original_all_chars', [])
    results = [c for c in original if query in data_cache.characters.get(c['base_char_id'], {}).get('name', '').lower()]
    if not results:
        await message.answer("❌ Ничего не найдено.")
        await state.set_state(TeamStates.selecting_hero)
        return
    await state.update_data(all_chars=results, page=0)
    await state.set_state(TeamStates.selecting_hero)
    await show_hero_page(message, state)
    await message.delete()

# ─────────────────────────────────────────────
# ФИЛЬТРЫ (роль, редкость, фракция) с комбинированием
# ─────────────────────────────────────────────
FILTER_ROLES = {
    'Tank': '🛡️', 'Warrior': '⚔️', 'Assassin': '🗡️',
    'Mage': '🔮', 'Support': '💚', 'Summoner': '🐉'
}
FILTER_RARITIES = {
    'Secret': '🌈', 'Mythic': '🔴', 'Legendary': '🟡', 'Epic': '🟣', 'Rare': '🔵'
}
FILTER_FACTIONS = {
    'Flame': '🔥', 'Ocean': '🌊', 'Storm': '⚡', 'Shadow': '🌑',
    'Light': '✨', 'Guardian': '🛡', 'Dragon': '🐉', 'Void': '☠'
}

@router.callback_query(lambda c: c.data == 'team_hero_filter')
async def hero_filter_menu(callback: types.CallbackQuery, state: FSMContext):
    builder = InlineKeyboardBuilder()
    builder.button(text="🛡️ Роль", callback_data="filter_type_role")
    builder.button(text="🌟 Редкость", callback_data="filter_type_rarity")
    builder.button(text="🏷 Фракция", callback_data="filter_type_faction")
    builder.button(text="🔄 Сбросить фильтры", callback_data="filter_reset")
    builder.button(text="🔙 К списку", callback_data="team_back_to_list")
    builder.adjust(2)
    await edit_or_answer(callback.message, "🎛 Выберите тип фильтра:", reply_markup=builder.as_markup())
    await state.set_state(TeamStates.choosing_filter)
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith('filter_type_'))
async def choose_filter_type(callback: types.CallbackQuery, state: FSMContext):
    filter_type = callback.data.split('_')[2]
    builder = InlineKeyboardBuilder()

    if filter_type == 'role':
        for role, emoji in FILTER_ROLES.items():
            builder.button(text=f"{emoji} {role}", callback_data=f"filter_role_{role}")
        await state.set_state(TeamStates.filter_role)
    elif filter_type == 'rarity':
        for rarity, emoji in FILTER_RARITIES.items():
            builder.button(text=f"{emoji} {rarity}", callback_data=f"filter_rarity_{rarity}")
        await state.set_state(TeamStates.filter_rarity)
    elif filter_type == 'faction':
        for faction, emoji in FILTER_FACTIONS.items():
            builder.button(text=f"{emoji} {faction}", callback_data=f"filter_faction_{faction}")
        await state.set_state(TeamStates.filter_faction)

    builder.button(text="🔙 Назад к фильтрам", callback_data="team_hero_filter")
    builder.adjust(2)
    await edit_or_answer(callback.message, f"Выберите значение ({filter_type}):", reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith('filter_role_'))
async def apply_role_filter(callback: types.CallbackQuery, state: FSMContext):
    role = callback.data.split('_', 2)[2]
    await _apply_filter_and_show(callback, state, 'role', role)

@router.callback_query(lambda c: c.data.startswith('filter_rarity_'))
async def apply_rarity_filter(callback: types.CallbackQuery, state: FSMContext):
    rarity = callback.data.split('_', 2)[2]
    await _apply_filter_and_show(callback, state, 'rarity', rarity)

@router.callback_query(lambda c: c.data.startswith('filter_faction_'))
async def apply_faction_filter(callback: types.CallbackQuery, state: FSMContext):
    faction = callback.data.split('_', 2)[2]
    await _apply_filter_and_show(callback, state, 'faction', faction)

async def _apply_filter_and_show(callback, state, filter_key, filter_value):
    data = await state.get_data()
    active_filters = data.get('active_filters', {})
    active_filters[filter_key] = filter_value
    await state.update_data(active_filters=active_filters)
    await _show_filtered_heroes(callback, state)

@router.callback_query(lambda c: c.data == 'filter_reset')
async def reset_filters(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(active_filters={})
    await _show_filtered_heroes(callback, state)

async def _show_filtered_heroes(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    original_chars = data.get('original_all_chars', [])
    active_filters = data.get('active_filters', {})

    filtered = original_chars.copy()
    if 'role' in active_filters:
        filtered = [c for c in filtered if data_cache.characters.get(c['base_char_id'], {}).get('role') == active_filters['role']]
    if 'rarity' in active_filters:
        filtered = [c for c in filtered if data_cache.characters.get(c['base_char_id'], {}).get('rarity') == active_filters['rarity']]
    if 'faction' in active_filters:
        filtered = [c for c in filtered if data_cache.characters.get(c['base_char_id'], {}).get('faction') == active_filters['faction']]

    filter_parts = []
    if 'role' in active_filters: filter_parts.append(f"🛡️ {active_filters['role']}")
    if 'rarity' in active_filters: filter_parts.append(f"🌟 {active_filters['rarity']}")
    if 'faction' in active_filters: filter_parts.append(f"🏷 {active_filters['faction']}")
    filter_text = " | ".join(filter_parts) if filter_parts else "без фильтров"

    if not filtered:
        builder = InlineKeyboardBuilder()
        builder.button(text="🔄 Сбросить фильтры", callback_data="filter_reset")
        builder.button(text="🔙 К списку", callback_data="team_back_to_list")
        await callback.message.edit_text(f"❌ Нет героев, соответствующих фильтрам: {filter_text}",
                                         reply_markup=builder.as_markup())
        await state.set_state(TeamStates.selecting_hero)
        await callback.answer()
        return

    await state.update_data(all_chars=filtered, page=0)
    await state.set_state(TeamStates.selecting_hero)
    await show_hero_page(callback.message, state)
    await callback.answer()

# ─────────────────────────────────────────────
# ОЧИСТКА СЛОТА
# ─────────────────────────────────────────────
@router.callback_query(lambda c: c.data.startswith('team_clear_'))
async def clear_slot(callback: types.CallbackQuery, state: FSMContext):
    slot = int(callback.data.split('_')[-1])
    user_id = callback.from_user.id
    await clear_team_slot(user_id, slot)
    await calculate_team_power(user_id)
    await show_team(callback.message, user_id, state)
    await callback.answer("Слот очищен.")