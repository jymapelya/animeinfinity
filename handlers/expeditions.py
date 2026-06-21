from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from db.models import (get_db, start_expedition, get_active_expeditions,
                       collect_expedition, get_player, calculate_team_power,
                       get_equipped_relic)
from engine.data_loader import data_cache
from handlers.utils import edit_or_answer
from datetime import datetime, timezone

router = Router()

class ExpeditionStates(StatesGroup):
    choosing_hero = State()
    choosing_duration = State()
    hero_search = State()

DURATIONS = {1: "1 час", 4: "4 часа", 8: "8 часов", 12: "12 часов", 24: "24 часа"}
HEROES_PER_PAGE = 5

ROLE_EMOJI = {
    'Tank': '🛡️', 'Warrior': '⚔️', 'Assassin': '🗡️',
    'Mage': '🔮', 'Support': '💚', 'Summoner': '🐉'
}
VARIANT_EMOJI = {'Normal':'','Shiny':'✨','Golden':'🌟','Prismatic':'💫','Celestial':'☄️'}
RARITY_EMOJI = {
    'Rare':'🔵','Epic':'🟣','Legendary':'🟡','Mythic':'🔴','Secret':'🌈'
}

# ────────────── ГЛАВНОЕ МЕНЮ ЭКСПЕДИЦИЙ ──────────────
@router.callback_query(lambda c: c.data == "expeditions")
async def expeditions_menu(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    active = await get_active_expeditions(user_id)

    text = "🗺 <b>Экспедиции</b>\n"
    if active:
        text += "\n<b>Активные:</b>\n"
        for exp in active:
            base = data_cache.characters.get(exp['base_char_id'], {})
            end_time = datetime.fromisoformat(exp['end_time'])
            remaining = end_time - datetime.now(timezone.utc)
            if remaining.total_seconds() > 0:
                hours, rem = divmod(int(remaining.total_seconds()), 3600)
                mins = rem // 60
                time_str = f"{hours}ч {mins}мин"
            else:
                time_str = "✅ Завершено"
            copy_num = exp.get('copy_number', '?')
            text += f"• {base.get('name', '???')} #{copy_num} ({DURATIONS.get(exp['duration_hours'], '?')}) — {time_str}\n"
    else:
        text += "\nНет активных экспедиций."

    builder = InlineKeyboardBuilder()
    builder.button(text="📤 Отправить героя", callback_data="exp_start")
    if active:
        builder.button(text="📥 Собрать всё", callback_data="exp_collect_all")
    builder.button(text="🔙 Назад", callback_data="menu")
    builder.adjust(2)
    await edit_or_answer(callback.message, text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()

# ────────────── ВЫБОР ГЕРОЯ (ПОКАЗЫВАЕМ РЕДКОСТЬ, ПРОБУЖДЕНИЕ, РЕЛИКВИЮ) ──────────────
@router.callback_query(lambda c: c.data == "exp_start")
async def choose_hero_start(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT char_instance_id FROM expeditions WHERE player_id=? AND claimed=0",
            (user_id,)
        )
        busy_ids = [row['char_instance_id'] for row in await cursor.fetchall()]

        cursor = await db.execute(
            "SELECT id, base_char_id, variant, iv_hp, iv_atk, iv_def, iv_spd, iv_crit, copy_number FROM player_characters WHERE player_id=?",
            (user_id,)
        )
        all_chars_raw = await cursor.fetchall()
        all_chars = [dict(c) for c in all_chars_raw]
    finally:
        await db.close()

    available = [c for c in all_chars if c['id'] not in busy_ids]
    if not available:
        await edit_or_answer(callback.message, "Нет свободных героев для экспедиции.",
                             reply_markup=InlineKeyboardBuilder().button(text="🔙 Назад", callback_data="expeditions").as_markup())
        await callback.answer()
        return

    await state.update_data(
        exp_available=available,
        exp_original=available.copy(),
        exp_page=0
    )
    await state.set_state(ExpeditionStates.choosing_hero)
    await show_exp_hero_page(callback.message, state)
    await callback.answer()

async def show_exp_hero_page(message: types.Message, state: FSMContext):
    data = await state.get_data()
    all_chars = data.get('exp_available', [])
    page = data.get('exp_page', 0)
    total_pages = max(1, (len(all_chars) + HEROES_PER_PAGE - 1) // HEROES_PER_PAGE)
    start = page * HEROES_PER_PAGE
    end = start + HEROES_PER_PAGE
    chars_on_page = all_chars[start:end]

    builder = InlineKeyboardBuilder()
    for char in chars_on_page:
        base = data_cache.characters[char['base_char_id']]
        role_icon = ROLE_EMOJI.get(base['role'], '❓')
        variant_emoji = VARIANT_EMOJI.get(char.get('variant', 'Normal'), '')
        rarity_emoji = RARITY_EMOJI.get(base['rarity'], '⚪')

        # Редкость и пробуждение
        stars = char.get('awakening_stars', 0)
        star_str = f"⭐{stars}" if stars > 0 else ""

        # Реликвия
        relic_data = await get_equipped_relic(char['id'])
        relic_str = ""
        if relic_data:
            relic = data_cache.relics.get(relic_data['relic_id'])
            if relic:
                eff_icon = {'hp':'❤️','atk':'⚔️','def':'🛡️','spd':'💨','crit':'💥','gold':'💰'}.get(relic['effect'],'')
                relic_str = f" 📦{eff_icon}"

        # Собираем строку: Роль Имя #Номер Вариант Редкость Звезды Реликвия
        label = (
            f"{role_icon} {base['name']} #{char.get('copy_number','?')} "
            f"{variant_emoji} {rarity_emoji}{base['rarity']} {star_str}{relic_str}"
        )
        builder.button(text=label, callback_data=f"exp_hero_{char['id']}")

    nav_buttons = []
    if page > 0:
        nav_buttons.append(("◀", "exp_page_prev"))
    if page < total_pages - 1:
        nav_buttons.append((f"▶ {page+1}/{total_pages}", "exp_page_next"))
    elif total_pages > 1:
        nav_buttons.append((f"📄 {page+1}/{total_pages}", "exp_page_info"))
    for text, cb in nav_buttons:
        builder.button(text=text, callback_data=cb)

    builder.button(text="🔍 Поиск", callback_data="exp_hero_search")
    builder.button(text="🔙 Назад", callback_data="expeditions")
    builder.adjust(1)

    await edit_or_answer(message, "Выберите героя для экспедиции (редкость влияет на награды):", reply_markup=builder.as_markup())

# ────────────── ПАГИНАЦИЯ И ПОИСК ──────────────
@router.callback_query(lambda c: c.data in ['exp_page_prev', 'exp_page_next'])
async def exp_page_change(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    page = data.get('exp_page', 0)
    if callback.data == 'exp_page_prev':
        page -= 1
    else:
        page += 1
    await state.update_data(exp_page=page)
    await show_exp_hero_page(callback.message, state)
    await callback.answer()

@router.callback_query(lambda c: c.data == 'exp_hero_search')
async def exp_hero_search_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("🔍 Введите имя героя:")
    await state.set_state(ExpeditionStates.hero_search)
    await callback.answer()

@router.message(ExpeditionStates.hero_search)
async def exp_hero_search_result(message: types.Message, state: FSMContext):
    query = message.text.strip().lower()
    data = await state.get_data()
    original = data.get('exp_original', [])
    results = [c for c in original if query in data_cache.characters.get(c['base_char_id'], {}).get('name', '').lower()]
    if not results:
        await message.answer("❌ Ничего не найдено.")
        await state.set_state(ExpeditionStates.choosing_hero)
        return
    await state.update_data(exp_available=results, exp_page=0)
    await state.set_state(ExpeditionStates.choosing_hero)
    await show_exp_hero_page(message, state)
    await message.delete()

# ────────────── ДЛИТЕЛЬНОСТЬ И СТАРТ ──────────────
@router.callback_query(lambda c: c.data.startswith('exp_hero_'))
async def choose_duration(callback: types.CallbackQuery, state: FSMContext):
    char_id = int(callback.data.split('_')[-1])
    await state.update_data(exp_char_id=char_id)
    builder = InlineKeyboardBuilder()
    for dur, label in DURATIONS.items():
        builder.button(text=label, callback_data=f"exp_dur_{dur}")
    builder.button(text="🔙 Назад", callback_data="exp_start")
    builder.adjust(2)
    await edit_or_answer(callback.message, "Выберите длительность:", reply_markup=builder.as_markup())
    await state.set_state(ExpeditionStates.choosing_duration)
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith('exp_dur_'))
async def start_expedition_handler(callback: types.CallbackQuery, state: FSMContext):
    duration = int(callback.data.split('_')[-1])
    data = await state.get_data()
    char_id = data['exp_char_id']
    user_id = callback.from_user.id

    success = await start_expedition(user_id, char_id, duration)
    if success:
        await edit_or_answer(callback.message, f"✅ Герой отправлен в экспедицию на {DURATIONS[duration]}!",
                             reply_markup=InlineKeyboardBuilder().button(text="🔙 К экспедициям", callback_data="expeditions").as_markup())
    else:
        await edit_or_answer(callback.message, "❌ Этот герой уже в экспедиции.",
                             reply_markup=InlineKeyboardBuilder().button(text="🔙 Назад", callback_data="expeditions").as_markup())
    await state.clear()
    await callback.answer()

# ────────────── СБОР НАГРАД ──────────────
@router.callback_query(lambda c: c.data == "exp_collect_all")
async def collect_all_expeditions(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    active = await get_active_expeditions(user_id)
    if not active:
        await callback.answer("Нет активных экспедиций.")
        return

    collected = []
    total_gold = 0
    total_gems = 0
    total_dust = 0
    total_tickets = 0
    total_cores = 0
    items_found = []

    for exp in active:
        rewards = await collect_expedition(exp['id'], user_id)
        if rewards:
            base = data_cache.characters.get(exp['base_char_id'], {})
            collected.append(base.get('name', '???'))
            total_gold += rewards.get('gold', 0)
            total_gems += rewards.get('gems', 0)
            total_dust += rewards.get('relic_dust', 0)
            total_tickets += rewards.get('tickets', 0)
            total_cores += rewards.get('awakening_cores', 0)
            items_found.extend(rewards.get('items', []))

    if collected:
        text = "📥 <b>Собраны экспедиции:</b>\n"
        text += ", ".join(collected) + "\n"
        text += f"💰 Золото: +{total_gold}\n"
        if total_gems:
            text += f"💎 Гемы: +{total_gems}\n"
        text += f"💨 Пыль: +{total_dust}\n"
        if total_tickets:
            text += f"🎫 Билеты: +{total_tickets}\n"
        if total_cores:
            text += f"💎 Ядер: +{total_cores}\n"
        if items_found:
            text += f"📦 Предметы: {', '.join(items_found)}\n"
    else:
        text = "Пока нечего собирать — все экспедиции ещё в пути."

    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 К экспедициям", callback_data="expeditions")
    await edit_or_answer(callback.message, text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await calculate_team_power(user_id)
    await callback.answer()