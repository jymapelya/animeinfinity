from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from engine.data_loader import data_cache
from handlers.utils import edit_or_answer
import math

router = Router()

ITEMS_PER_PAGE = 5

# Эмодзи
RARITY_EMOJI = {'Rare':'🔵','Epic':'🟣','Legendary':'🟡','Mythic':'🔴','Secret':'🌈'}
RARITY_EMOJI_RELIC = {'Common':'⚪','Rare':'🔵','Epic':'🟣','Legendary':'🟡'}
EFFECT_EMOJI = {'hp':'❤️','atk':'⚔️','def':'🛡️','spd':'💨','crit':'💥','gold':'💰'}
ROLE_EMOJI = {'Tank': '🛡️', 'Warrior': '⚔️', 'Assassin': '🗡️', 'Mage': '🔮', 'Support': '💚', 'Summoner': '🐉'}
FACTION_EMOJI = {
    'Flame': '🔥', 'Ocean': '🌊', 'Storm': '⚡', 'Shadow': '🌑',
    'Light': '✨', 'Guardian': '🛡', 'Dragon': '🐉', 'Void': '☠'
}

# ──────────────────────────────────────────────
# 📖 ГЛАВНОЕ МЕНЮ ВИКИ
# ──────────────────────────────────────────────
@router.callback_query(lambda c: c.data == "wiki")
async def wiki_main_menu(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="📖 Открыть канал", url="https://t.me/+jblkZbrZ2EtjOWUy")
    builder.button(text="🔍 Быстрый поиск", callback_data="wiki_characters")
    builder.button(text="🔙 Назад", callback_data="menu")
    await edit_or_answer(callback.message, "📚 Википедия доступна в нашем канале:", reply_markup=builder.as_markup())
    await callback.answer()


# ──────────────────────────────────────────────
# 👥 ПЕРСОНАЖИ — детальная карточка с навигацией
# ──────────────────────────────────────────────
@router.callback_query(lambda c: c.data == "wiki_characters")
async def wiki_characters(callback: types.CallbackQuery):
    rarity_order = {'Secret':0,'Mythic':1,'Legendary':2,'Epic':3,'Rare':4}
    all_chars = sorted(data_cache.characters.values(),
                       key=lambda c: (rarity_order.get(c.get('rarity','Rare'), 99), c.get('name','')))
    await callback.message.edit_text(
        "👥 <b>Персонажи</b>\nВыберите героя, чтобы узнать подробнее:",
        reply_markup=build_paginated_keyboard(
            all_chars,
            lambda c: f"{RARITY_EMOJI.get(c['rarity'],'')} {c['name']} ({c['rarity']})",
            "wchar",
            page=0,
            back_callback="wiki"
        ),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("wchar_"))
async def wiki_char_detail(callback: types.CallbackQuery):
    char_id = callback.data.split("_", 1)[1]
    char = data_cache.characters.get(char_id)
    if not char:
        await callback.answer("Персонаж не найден.")
        return

    rarity_emoji = RARITY_EMOJI.get(char['rarity'], '')
    role_icon = ROLE_EMOJI.get(char.get('role',''), '')
    faction_icon = FACTION_EMOJI.get(char.get('faction',''), '')

    text = (
        f"{rarity_emoji} <b>{char['name']}</b> {role_icon} {faction_icon}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🌟 Редкость: {char['rarity']}\n"
        f"🏷 Фракция: {char['faction']}\n"
        f"⚔ Роль: {char.get('role','')}\n"
        f"━━━━━━━━━━━━━━━━\n"
    )

    hp = char.get('hp', 100)
    atk = char.get('atk', 50)
    def_ = char.get('def', 30)
    spd = char.get('spd', 80)
    crit = char.get('crit', 5)
    text += (
        f"❤️ HP: {hp}  ⚔️ ATK: {atk}\n"
        f"🛡️ DEF: {def_}  💨 SPD: {spd}\n"
        f"💥 CRIT: {crit}%\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"<b>Навыки:</b>\n"
    )

    for sid in char.get('skills', []):
        skill = data_cache.skills.get(sid)
        if skill:
            cd = skill.get('cooldown', 0)
            cd_text = f" (CD: {cd})" if cd else ""
            if skill['type'] == 'damage':
                desc = f"⚔️ Урон x{skill.get('multiplier',1.0)}"
            elif skill['type'] == 'heal':
                desc = f"💚 Лечение x{skill.get('multiplier',0.2)}"
            elif skill['type'] == 'buff':
                desc = f"✨ Бафф {skill.get('stat','?')} +{int(skill.get('value',0)*100)}%"
            elif skill['type'] == 'debuff':
                desc = f"🌀 Дебафф {skill.get('stat','?')} {int(skill.get('value',0)*100)}%"
            elif skill['type'] == 'summon':
                desc = "🐉 Призыв существ"
            else:
                desc = "Особый эффект"
            text += f"• {skill['name']}{cd_text}: {desc}\n"

    text += (
        f"━━━━━━━━━━━━━━━━\n"
        f"📋 <i>Совет:</i> {get_character_tip(char['id'])}\n"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 К списку", callback_data="wiki_characters")
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()

# ──────────────────────────────────────────────
# 📦 РЕЛИКВИИ — постраничный просмотр с деталями
# ──────────────────────────────────────────────
@router.callback_query(lambda c: c.data == "wiki_relics")
async def wiki_relics(callback: types.CallbackQuery):
    all_relics = sorted(data_cache.relics.values(), key=lambda r: (r['rarity'], r['name']))
    await callback.message.edit_text(
        "📦 <b>Реликвии</b>\nВыберите, чтобы узнать подробнее:",
        reply_markup=build_paginated_keyboard(
            all_relics,
            lambda r: f"{RARITY_EMOJI_RELIC.get(r['rarity'],'')} {r['name']} (+{r['value']}% {r['effect'].upper()})",
            "wrelic",
            page=0,
            back_callback="wiki"
        ),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("wrelic_"))
async def wiki_relic_detail(callback: types.CallbackQuery):
    relic_id = callback.data.split("_", 1)[1]
    relic = data_cache.relics.get(relic_id)
    if not relic:
        await callback.answer("Реликвия не найдена.")
        return

    eff_icon = EFFECT_EMOJI.get(relic['effect'], '')
    text = (
        f"{RARITY_EMOJI_RELIC.get(relic['rarity'],'')} <b>{relic['name']}</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🌟 Редкость: {relic['rarity']}\n"
        f"📊 Эффект: +{relic['value']}% {eff_icon} {relic['effect'].upper()}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"📋 <i>Совет:</i> {get_relic_tip(relic['id'])}\n"
    )
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 К списку", callback_data="wiki_relics")
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()

# ──────────────────────────────────────────────
# ⚔ КАМПАНИЯ — многостраничный гайд
# ──────────────────────────────────────────────
CAMPAIGN_GUIDE = [
    (
        "⚔ Кампания (1/4)",
        "В кампании ты проходишь миры, каждый состоит из 9 волн.\n"
        "8 волн — обычные враги, 9‑я — босс с уникальными способностями.\n"
        "Победа над боссом открывает следующий мир."
    ),
    (
        "⚔ Кампания (2/4) — Враги",
        "Обычные враги генерируются случайным образом из списка, определённого для каждого мира.\n"
        "Их сила растёт с номером волны и миром.\n"
        "Награды за волну: золото, опыт, иногда пыль и предметы."
    ),
    (
        "⚔ Кампания (3/4) — Боссы",
        "Боссы имеют повышенные характеристики и специальные навыки:\n"
        "🌊 Мир 2: Регенерация (10% HP раз в 3 хода)\n"
        "⚡ Мир 3: Щит (+50% DEF на 2 хода)\n"
        "🌑 Мир 4: Призыв миньонов\n"
        "☠ Мир 5: Дебафф ATK -25% на всю команду\n"
        "Совет: используйте контроль (стан, замедление) и баффы."
    ),
    (
        "⚔ Кампания (4/4) — Награды",
        "За победу над боссом даётся золото, реликвийная пыль, шанс на реликвию или предмет.\n"
        "Также открывается следующий мир.\n"
        "Если проиграли — попробуйте улучшить команду (пробуждение, реликвии, синергии)."
    ),
]

@router.callback_query(lambda c: c.data == "wiki_campaign")
async def wiki_campaign(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(guide_page=0, guide_name="campaign")
    await show_guide_page(callback.message, state, CAMPAIGN_GUIDE, "wiki")

@router.callback_query(lambda c: c.data == "guide_next")
async def guide_next(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    page = data.get('guide_page', 0)
    name = data.get('guide_name')
    guide = {"campaign": CAMPAIGN_GUIDE, "afk": AFK_GUIDE, "expeditions": EXPEDITION_GUIDE}.get(name, [])
    await state.update_data(guide_page=page + 1)
    await show_guide_page(callback.message, state, guide, "wiki")
    await callback.answer()

@router.callback_query(lambda c: c.data == "guide_prev")
async def guide_prev(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    page = data.get('guide_page', 0)
    name = data.get('guide_name')
    guide = {"campaign": CAMPAIGN_GUIDE, "afk": AFK_GUIDE, "expeditions": EXPEDITION_GUIDE}.get(name, [])
    await state.update_data(guide_page=page - 1)
    await show_guide_page(callback.message, state, guide, "wiki")
    await callback.answer()

async def show_guide_page(message: types.Message, state: FSMContext, guide: list, back_cb: str):
    data = await state.get_data()
    page = data.get('guide_page', 0)
    total = len(guide)
    title, text = guide[page]
    full_text = f"📖 <b>{title}</b>\n\n{text}\n\n📄 {page+1}/{total}"

    builder = InlineKeyboardBuilder()
    if page > 0:
        builder.button(text="◀ Назад", callback_data="guide_prev")
    if page < total - 1:
        builder.button(text="Вперёд ▶", callback_data="guide_next")
    builder.button(text="🔙 К разделам", callback_data=back_cb)
    builder.adjust(2)
    await edit_or_answer(message, full_text, reply_markup=builder.as_markup(), parse_mode="HTML")

# ──────────────────────────────────────────────
# ⏳ AFK-фарм — гайд
# ──────────────────────────────────────────────
AFK_GUIDE = [
    (
        "⏳ AFK-фарм (1/3)",
        "AFK (Away From Keyboard) — пассивный доход, который копится, пока ты不在 в боте.\n"
        "Нажми кнопку «🎁 AFK Награды», чтобы собрать накопившееся."
    ),
    (
        "⏳ AFK-фарм (2/3) — Как считается",
        "Доход зависит от твоего максимального прогресса в кампании (мир и волна).\n"
        "Формула: золото = (30 + волна*5) * волн_за_секунду * время * множитель_мира.\n"
        "Множитель мира: 1.0 + (мир-1)*0.4.\n"
        "Также есть шанс получить гемы, билеты, пыль и ядра."
    ),
    (
        "⏳ AFK-фарм (3/3) — Ограничения",
        "Максимальное время накопления — 12 часов.\n"
        "После сбора наград таймер сбрасывается.\n"
        "Совет: заходи в бот хотя бы раз в 12 часов, чтобы не терять доход!"
    ),
]

@router.callback_query(lambda c: c.data == "wiki_afk")
async def wiki_afk(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(guide_page=0, guide_name="afk")
    await show_guide_page(callback.message, state, AFK_GUIDE, "wiki")

# ──────────────────────────────────────────────
# 🗺 ЭКСПЕДИЦИИ — гайд
# ──────────────────────────────────────────────
EXPEDITION_GUIDE = [
    (
        "🗺 Экспедиции (1/3)",
        "Отправляй свободных героев на задания, чтобы получить ценные ресурсы.\n"
        "Чем дольше экспедиция и выше редкость героя, тем лучше награды."
    ),
    (
        "🗺 Экспедиции (2/3) — Как отправить",
        "Зайди в раздел «🗺 Экспедиции» → «📤 Отправить героя».\n"
        "Выбери героя и длительность (1, 4, 8, 12 или 24 часа).\n"
        "Герой исчезнет из команды до окончания экспедиции."
    ),
    (
        "🗺 Экспедиции (3/3) — Награды",
        "Базовые награды: золото, реликвийная пыль.\n"
        "Шанс получить: гемы, билеты, предметы, реликвии.\n"
        "После завершения нажми «📥 Собрать всё»."
    ),
]

@router.callback_query(lambda c: c.data == "wiki_expeditions")
async def wiki_expeditions(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(guide_page=0, guide_name="expeditions")
    await show_guide_page(callback.message, state, EXPEDITION_GUIDE, "wiki")

# ──────────────────────────────────────────────
# 🔧 ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ──────────────────────────────────────────────
def build_paginated_keyboard(items, label_func, prefix, page=0, back_callback="menu"):
    """Создаёт клавиатуру с пагинацией для списка предметов."""
    builder = InlineKeyboardBuilder()
    total_pages = math.ceil(len(items) / ITEMS_PER_PAGE)
    start = page * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    for item in items[start:end]:
        item_id = item.get('id', item.get('name',''))
        builder.button(text=label_func(item), callback_data=f"{prefix}_{item_id}")

    nav = []
    if page > 0:
        nav.append(("◀", f"{prefix}_page_{page-1}"))
    nav.append((f"📄 {page+1}/{total_pages}", "noop"))
    if page < total_pages - 1:
        nav.append(("▶", f"{prefix}_page_{page+1}"))
    for t, cb in nav:
        builder.button(text=t, callback_data=cb)

    builder.button(text="🔙 Назад", callback_data=back_callback)
    builder.adjust(ITEMS_PER_PAGE, len(nav), 1)
    return builder.as_markup()

# Обработчики пагинации для персонажей и реликвий
@router.callback_query(lambda c: c.data.startswith("wchar_page_"))
async def wiki_char_page(callback: types.CallbackQuery):
    page = int(callback.data.split("_")[-1])
    rarity_order = {'Secret':0,'Mythic':1,'Legendary':2,'Epic':3,'Rare':4}
    all_chars = sorted(data_cache.characters.values(),
                       key=lambda c: (rarity_order.get(c.get('rarity','Rare'), 99), c.get('name','')))
    await callback.message.edit_reply_markup(
        reply_markup=build_paginated_keyboard(all_chars,
            lambda c: f"{RARITY_EMOJI.get(c['rarity'],'')} {c['name']} ({c['rarity']})",
            "wchar", page=page, back_callback="wiki")
    )
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("wrelic_page_"))
async def wiki_relic_page(callback: types.CallbackQuery):
    page = int(callback.data.split("_")[-1])
    all_relics = sorted(data_cache.relics.values(), key=lambda r: (r['rarity'], r['name']))
    await callback.message.edit_reply_markup(
        reply_markup=build_paginated_keyboard(all_relics,
            lambda r: f"{RARITY_EMOJI_RELIC.get(r['rarity'],'')} {r['name']} (+{r['value']}% {r['effect'].upper()})",
            "wrelic", page=page, back_callback="wiki")
    )
    await callback.answer()

@router.callback_query(lambda c: c.data == "noop")
async def noop(callback: types.CallbackQuery):
    await callback.answer()

# ──────────────────────────────────────────────
# 📝 ПОДСКАЗКИ (можно расширять)
# ──────────────────────────────────────────────
def get_character_tip(char_id: str) -> str:
    tips = {
        "jinwoo": "Используйте его бафф «Присутствие монарха» в начале боя, чтобы усилить всю команду.",
        "ainz": "Старайтесь, чтобы он ходил первым — его «Тёмная аура» повысит атаку союзников.",
        "itachi": "Аматерасу наносит огромный урон, но долго перезаряжается. Защищайте его!",
        "escanor": "Вспышка гордости делает его неудержимым на 2 хода — используйте перед мощным ударом.",
    }
    return tips.get(char_id, "Пробуйте разные комбинации навыков и реликвий для максимальной эффективности.")

def get_relic_tip(relic_id: str) -> str:
    tips = {
        "dragon_heart": "Идеально для танков — большой запас HP спасёт в затяжных боях.",
        "eye_of_fate": "Даёт критический шанс. Наденьте на ассасина или мага с высоким уроном.",
        "ancient_crown": "Усиливает атаку. Отлично подходит дамагерам вроде Сон Джин-Ву или Итачи.",
    }
    return tips.get(relic_id, "Надевайте реликвию на героя, соответствующего её эффекту.")