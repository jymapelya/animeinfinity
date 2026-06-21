import os
from aiogram import Router, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from db.models import get_db, get_awakening_cost, get_awakening_level, awaken_hero, calculate_team_power, get_shared_chat
from engine.data_loader import data_cache
from aiogram.types import InlineQuery, InlineQueryResultArticle, InputTextMessageContent, Message
from aiogram import F
import html

router = Router()

class CollectionStates(StatesGroup):
    browsing = State()
    searching = State()

RARITY_EMOJI = {'Rare':'🔵','Epic':'🟣','Legendary':'🟡','Mythic':'🔴','Secret':'🌈'}
VARIANT_EMOJI = {'Normal':'','Shiny':'✨','Golden':'🌟','Prismatic':'💫','Celestial':'☄️'}
RARITY_ORDER = ['Secret','Mythic','Legendary','Epic','Rare']
FACTION_LIST = ['Flame','Ocean','Storm','Shadow','Light','Guardian','Dragon','Void']
FACTION_EMOJI = {
    'Flame': '🔥', 'Ocean': '🌊', 'Storm': '⚡', 'Shadow': '🌑',
    'Light': '✨', 'Guardian': '🛡', 'Dragon': '🐉', 'Void': '☠'
}
ROLE_EMOJI = {
    'Tank': '🛡️', 'Warrior': '⚔️', 'Assassin': '🗡️',
    'Mage': '🔮', 'Support': '💚', 'Summoner': '🐉'
}

# Глобальный кэш file_id
image_cache = {}

@router.callback_query(lambda c: c.data == "collection")
async def collection_start(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    user_id = callback.from_user.id
    cards = await get_player_collection(user_id)
    if not cards:
        await callback.message.answer("📭 Ваша коллекция пуста. Начните крутить гача-баннер!")
        return

    await state.update_data(cards=cards, original_cards=cards, index=0, filter_type='all', filter_value='all')
    await state.set_state(CollectionStates.browsing)
    try:
        await callback.message.delete()
    except:
        pass
    await show_card(None, callback.message.chat.id, cards, 0, 'all', 'all', state, bot)

async def show_card(message_to_edit: types.Message | None, chat_id: int, cards: list,
                    index: int, filter_type: str, filter_value: str, state: FSMContext, bot: Bot):
    filtered = filter_cards(cards, filter_type, filter_value)
    if not filtered:
        if message_to_edit and message_to_edit.text:
            try:
                await message_to_edit.edit_text("📭 Нет персонажей, соответствующих фильтру.")
            except:
                pass
        return

    total = len(filtered)
    index = max(0, min(index, total - 1))

    card = filtered[index]
    base = data_cache.characters.get(card['base_char_id'])
    if not base:
        base = {'name': '???', 'rarity': 'Rare', 'faction': '?', 'role': 'Tank'}

    rarity_emoji = RARITY_EMOJI.get(base['rarity'], '⬜')
    variant_emoji = VARIANT_EMOJI.get(card.get('variant', 'Normal'), '')
    faction_icon = FACTION_EMOJI.get(base['faction'], '')
    role_icon = ROLE_EMOJI.get(base['role'], '❓')

    # Экранируем имя и другие текстовые поля
    safe_name = html.escape(base['name'])
    safe_faction = html.escape(base['faction'])
    safe_rarity = html.escape(base['rarity'])
    safe_variant = html.escape(card.get('variant', 'Normal'))

    text = "━━━━━━━━━━━━━━━━━━━━━━\n"
    text += f"{rarity_emoji} <b>{safe_name}</b> {role_icon}\n"
    text += f"{faction_icon} {safe_faction} | {safe_rarity} | {safe_variant} {variant_emoji}\n"

    if card.get('trait'):
        trait_data = data_cache.traits.get(card['trait'])
        if trait_data:
            trait_name = html.escape(trait_data.get('name', card['trait']))
            trait_desc = html.escape(trait_data.get('desc', ''))
            text += f"🧬 Trait: {trait_name} — {trait_desc}\n"
        else:
            text += f"🧬 Trait: {html.escape(card['trait'])}\n"
    if card.get('destiny'):
        destiny_data = data_cache.destinies.get(card['destiny'])
        if destiny_data:
            destiny_name = html.escape(destiny_data.get('name', card['destiny']))
            destiny_desc = html.escape(destiny_data.get('desc', ''))
            text += f"🔮 Destiny: {destiny_name} — {destiny_desc}\n"
        else:
            text += f"🔮 Destiny: {html.escape(card['destiny'])}\n"

    # Навыки
    skills = base.get('skills', [])
    if skills:
        text += "━━━━━━━━━━━━━━━━━━━━━━\n<b>Навыки:</b>\n"
        for sid in skills:
            skill = data_cache.skills.get(sid)
            if skill:
                skill_name = html.escape(skill['name'])
                skill_type = skill.get('type', '?')
                if skill_type == 'damage':
                    desc = f"⚔️ Урон (x{skill.get('multiplier',1.0)})"
                elif skill_type == 'heal':
                    desc = f"💚 Лечение (x{skill.get('multiplier',0.2)})"
                elif skill_type == 'buff':
                    desc = f"✨ Бафф {html.escape(skill.get('stat','?'))} +{int(skill.get('value',0)*100)}%"
                elif skill_type == 'debuff':
                    desc = f"🌀 Дебафф {html.escape(skill.get('stat','?'))} {int(skill.get('value',0)*100)}%"
                elif skill_type == 'summon':
                    desc = "🐉 Призыв"
                else:
                    desc = "❓ Особая"
                cd = skill.get('cooldown', 0)
                cd_text = f" (CD: {cd})" if cd else ""
                text += f"• {skill_name}{cd_text}: {desc}\n"

    # Звёзды пробуждения
    stars = card.get('awakening_stars', 0)
    if stars > 0:
        text += f"⭐ Пробуждение: {'★'*stars}{'☆'*(5-stars)} (+{stars*5}% к статам)\n"

    # Статы с IV
    base_hp = base.get('hp', 100)
    base_atk = base.get('atk', 50)
    base_def = base.get('def', 30)
    base_spd = base.get('spd', 80)
    base_crit = base.get('crit', 5)

    actual_hp = round(base_hp * (card['iv_hp'] / 100))
    actual_atk = round(base_atk * (card['iv_atk'] / 100))
    actual_def = round(base_def * (card['iv_def'] / 100))
    actual_spd = round(base_spd * (card['iv_spd'] / 100))
    actual_crit = round(base_crit * (card['iv_crit'] / 100))

    def iv_emoji(val):
        if val < 90: return '🔴'
        if val < 100: return '🟡'
        if val < 110: return '🟢'
        return '🔵'

    text += (
        f"❤️ HP: {actual_hp} ({iv_emoji(card['iv_hp'])} {card['iv_hp']}%)  "
        f"⚔️ ATK: {actual_atk} ({iv_emoji(card['iv_atk'])} {card['iv_atk']}%)\n"
        f"🛡️ DEF: {actual_def} ({iv_emoji(card['iv_def'])} {card['iv_def']}%)  "
        f"💨 SPD: {actual_spd} ({iv_emoji(card['iv_spd'])} {card['iv_spd']}%)\n"
        f"💥 CRIT: {actual_crit}% ({iv_emoji(card['iv_crit'])} {card['iv_crit']}%)\n"
    )
    text += f"📋 Вариация: {card['obtained_count']} шт. | Всего копий: {card['total_copies']}\n"
    text += "━━━━━━━━━━━━━━━━━━━━━━\n"
    text += f"📚 {index+1}/{total}"

    builder = InlineKeyboardBuilder()
    nav_buttons = []
    if index > 0:
        nav_buttons.append(('⬅', 'coll_prev'))
    nav_buttons.append(('❌', 'coll_close'))
    if index < total - 1:
        nav_buttons.append(('➡', 'coll_next'))
    for title, cb in nav_buttons:
        builder.button(text=title, callback_data=cb)
    builder.button(text='🔍', callback_data='coll_search')
    builder.button(text='🔍 Фильтр', callback_data='coll_filter')
    builder.button(text='📤 Поделиться', callback_data=f'share_{card["base_char_id"]}')
    if filter_type != 'all':
        builder.button(text='🔄 Сброс', callback_data='coll_filter_reset')
    builder.adjust(len(nav_buttons), 2)

    if card.get('awakening_stars', 0) < 5 and card.get('total_copies', 0) >= 2:
        gold_cost, core_cost = await get_awakening_cost(card['awakening_stars'])
        builder.button(
            text=f"⚡ Пробудить ({gold_cost}💰/{core_cost}🔮)",
            callback_data=f"awaken_{card['base_char_id']}"
        )

    image_url = base.get('image_url')
    if image_url:
        if message_to_edit:
            try:
                await message_to_edit.delete()
            except:
                pass
        cached = image_cache.get(image_url)
        try:
            if cached:
                sent_msg = await bot.send_photo(chat_id, cached['file_id'], caption=text,
                                                reply_markup=builder.as_markup(), parse_mode="HTML")
            else:
                from engine.image_processor import download_image, add_rarity_border
                tmp_path = await download_image(image_url)
                bordered_path = add_rarity_border(tmp_path, base['rarity'])
                sent_msg = await bot.send_photo(chat_id, types.FSInputFile(bordered_path),
                                                caption=text, reply_markup=builder.as_markup(), parse_mode="HTML")
                if sent_msg.photo:
                    image_cache[image_url] = {'type': 'photo', 'file_id': sent_msg.photo[-1].file_id}
                os.unlink(tmp_path)
                os.unlink(bordered_path)
            return
        except Exception:
            pass

    if message_to_edit and message_to_edit.text:
        try:
            await message_to_edit.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
            return
        except:
            pass
    await bot.send_message(chat_id, text, reply_markup=builder.as_markup(), parse_mode="HTML")

# --- Поиск ---
@router.callback_query(lambda c: c.data == 'coll_search')
async def start_search(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("🔍 Введите имя персонажа:")
    await state.set_state(CollectionStates.searching)
    await callback.answer()

@router.message(CollectionStates.searching)
async def handle_search(message: types.Message, state: FSMContext, bot: Bot):
    query = message.text.strip().lower()
    data = await state.get_data()
    original_cards = data.get('original_cards', [])
    if not original_cards:
        original_cards = data.get('cards', [])
        await state.update_data(original_cards=original_cards)
    results = [c for c in original_cards if query in data_cache.characters.get(c['base_char_id'], {}).get('name', '').lower()]
    if not results:
        await message.answer("❌ Ничего не найдено.")
        await state.set_state(CollectionStates.browsing)
        return
    await state.update_data(cards=results, index=0, filter_type='all', filter_value='all')
    await state.set_state(CollectionStates.browsing)
    await show_card(message, message.chat.id, results, 0, 'all', 'all', state, bot)
    try:
        await message.delete()
    except:
        pass


@router.callback_query(lambda c: c.data in ['coll_prev','coll_next','coll_close','coll_filter','coll_filter_reset','coll_back'])
async def collection_navigation(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    cards = data.get('cards', [])
    index = data.get('index', 0)
    filter_type = data.get('filter_type', 'all')
    filter_value = data.get('filter_value', 'all')
    action = callback.data

    if action == 'coll_close':
        await callback.message.delete()
        await state.clear()
        await callback.answer("Коллекция закрыта")
        return

    if action == 'coll_filter':
        await callback.message.delete()
        builder = InlineKeyboardBuilder()
        builder.button(text="🌟 По редкости", callback_data="coll_fsel_rarity")
        builder.button(text="🏷 По фракции", callback_data="coll_fsel_faction")
        builder.button(text="🔙 Назад", callback_data="coll_back")
        builder.adjust(2)
        await callback.message.answer("Выберите тип фильтра:", reply_markup=builder.as_markup())
        await callback.answer()
        return

    if action == 'coll_filter_reset':
        original = data.get('original_cards')
        if original:
            cards = original
            await state.update_data(cards=cards, original_cards=cards)
        filter_type = 'all'
        filter_value = 'all'
        index = 0
        await state.update_data(filter_type=filter_type, filter_value=filter_value, index=index)
        await show_card(callback.message, callback.message.chat.id, cards, index, filter_type, filter_value, state, bot)
        await callback.answer()
        return

    if action == 'coll_back':
        await show_card(callback.message, callback.message.chat.id, cards, index, filter_type, filter_value, state, bot)
        await callback.answer()
        return

    if action == 'coll_prev': index -= 1
    elif action == 'coll_next': index += 1
    await state.update_data(index=index)
    filtered = filter_cards(cards, filter_type, filter_value)
    if filtered:
        await show_card(callback.message, callback.message.chat.id, cards, index, filter_type, filter_value, state, bot)
    await callback.answer()

@router.callback_query(lambda c: c.data in ['coll_fsel_rarity','coll_fsel_faction'])
async def filter_selection(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    await callback.message.delete()
    builder = InlineKeyboardBuilder()
    if callback.data == 'coll_fsel_rarity':
        values = RARITY_ORDER
        prefix = 'coll_fv_rarity:'
    else:
        values = FACTION_LIST
        prefix = 'coll_fv_faction:'
    for v in values:
        builder.button(text=v, callback_data=prefix + v)
    builder.button(text="🔙 Назад", callback_data="coll_back")
    builder.adjust(2)
    await callback.message.answer("Выберите значение фильтра:", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith('coll_fv_'))
async def apply_filter_value(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    cards = data.get('cards', [])
    parts = callback.data.split(':')
    if len(parts) < 2:
        await callback.answer("Ошибка данных")
        return
    prefix = parts[0]
    fval = parts[1]
    if prefix == 'coll_fv_rarity':
        ftype = 'rarity'
    elif prefix == 'coll_fv_faction':
        ftype = 'faction'
    else:
        await callback.answer("Неизвестный фильтр")
        return
    index = 0
    await state.update_data(filter_type=ftype, filter_value=fval, index=index)
    await callback.message.delete()
    await show_card(None, callback.message.chat.id, cards, index, ftype, fval, state, bot)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith('share_'))
async def share_character(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    chat_id = await get_shared_chat(user_id)
    
    if not chat_id:
        await callback.message.answer(
            "📤 Чтобы поделиться героем, перешлите любое сообщение из чата, куда хотите отправлять (бот должен быть в этом чате)."
        )
        await callback.answer()
        return
    
    # Получаем ID героя
    base_char_id = callback.data.split('_', 1)[1]
    base = data_cache.characters.get(base_char_id)
    if not base:
        await callback.answer("Герой не найден.")
        return
    
    # Формируем карточку
    skills_text = ""
    for sid in base.get('skills', []):
        skill = data_cache.skills.get(sid)
        if skill:
            cd = skill.get('cooldown', 0)
            cd_text = f" (CD: {cd})" if cd else ""
            skills_text += f"• {skill['name']}{cd_text}: {skill.get('type','')}\n"
    
    card_text = (
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🌈 <b>{base['name']}</b> ({base.get('rarity','')})\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"❤️ HP: {base.get('hp','?')} | ⚔️ ATK: {base.get('atk','?')}\n"
        f"🛡️ DEF: {base.get('def','?')} | 💨 SPD: {base.get('spd','?')}\n"
        f"💥 CRIT: {base.get('crit','?')}%\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Навыки:</b>\n{skills_text}"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Поделился героем из Anime Infinity!"
    )
    
    image_url = base.get('image_url')
    try:
        if image_url:
            await callback.bot.send_photo(chat_id, image_url, caption=card_text, parse_mode="HTML")
        else:
            await callback.bot.send_message(chat_id, card_text, parse_mode="HTML")
        await callback.answer("Герой отправлен в чат!")
    except Exception as e:
        await callback.answer(f"Ошибка отправки: {e}")

async def get_player_collection(user_id: int):
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT base_char_id, variant, trait, destiny, iv_hp, iv_atk, iv_def, iv_spd, iv_crit, COUNT(*) as obtained_count
               FROM player_characters WHERE player_id = ?
               GROUP BY base_char_id, variant, trait, destiny, iv_hp, iv_atk, iv_def, iv_spd, iv_crit""",
            (user_id,)
        )
        rows = await cursor.fetchall()
        cards = [dict(row) for row in rows]
        unique_ids = set(card['base_char_id'] for card in cards)
        total_counts = {}
        for bid in unique_ids:
            cnt_cursor = await db.execute(
                "SELECT COUNT(*) as cnt FROM player_characters WHERE player_id=? AND base_char_id=?",
                (user_id, bid))
            cnt_row = await cnt_cursor.fetchone()
            total_counts[bid] = cnt_row['cnt'] if cnt_row else 0
        for card in cards:
            card['total_copies'] = total_counts.get(card['base_char_id'], 0)
            stars = await get_awakening_level(user_id, card['base_char_id'])
            card['awakening_stars'] = stars
        return cards
    finally:
        await db.close()

def filter_cards(cards: list, filter_type: str, filter_value: str):
    if filter_type == 'all' or filter_value == 'all':
        return cards
    filtered = []
    for card in cards:
        base = data_cache.characters.get(card['base_char_id'])
        if not base: continue
        if filter_type == 'rarity' and base.get('rarity') == filter_value:
            filtered.append(card)
        elif filter_type == 'faction' and base.get('faction') == filter_value:
            filtered.append(card)
    return filtered


@router.callback_query(lambda c: c.data.startswith('awaken_'))
async def awaken_handler(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    base_char_id = callback.data.split('_', 1)[1]
    user_id = callback.from_user.id
    new_stars, error = await awaken_hero(user_id, base_char_id)

    if error:
        await callback.answer(error)
        return

    # Обновляем коллекцию и пересчитываем силу
    cards = await get_player_collection(user_id)
    data = await state.get_data()
    index = data.get('index', 0)
    filter_type = data.get('filter_type', 'all')
    filter_value = data.get('filter_value', 'all')

    await state.update_data(cards=cards)
    await calculate_team_power(user_id)  # <-- теперь функция определена
    await show_card(callback.message, callback.message.chat.id, cards, index, filter_type, filter_value, state, bot)
    await callback.answer(f"Уровень пробуждения повышен до {new_stars}★!")


@router.inline_query()
async def inline_share(inline_query: InlineQuery):
    base_char_id = inline_query.query.strip()
    if not base_char_id:
        return
    
    # Ищем героя в кэше
    base = data_cache.characters.get(base_char_id)
    if not base:
        await inline_query.answer([], switch_pm_text="Герой не найден", switch_pm_parameter="start")
        return
    
    # Собираем полную карточку
    skills_text = ""
    for sid in base.get('skills', []):
        skill = data_cache.skills.get(sid)
        if skill:
            cd = skill.get('cooldown', 0)
            cd_text = f" (CD: {cd})" if cd else ""
            skills_text += f"• {skill['name']}{cd_text}: {skill.get('type','')}\n"
    
    card_text = (
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🌈 <b>{base['name']}</b> ({base.get('rarity','')})\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"❤️ HP: {base.get('hp','?')} | ⚔️ ATK: {base.get('atk','?')}\n"
        f"🛡️ DEF: {base.get('def','?')} | 💨 SPD: {base.get('spd','?')}\n"
        f"💥 CRIT: {base.get('crit','?')}%\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Навыки:</b>\n{skills_text}"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Поделился героем из Anime Infinity!"
    )
    
    result = InlineQueryResultArticle(
        id=base_char_id,
        title=base['name'],
        description=f"Редкость: {base.get('rarity','')} | Роль: {base.get('role','')}",
        thumb_url=base.get('image_url', ''),
        input_message_content=InputTextMessageContent(message_text=card_text, parse_mode="HTML")
    )
    
    await inline_query.answer([result], cache_time=1)


@router.message(F.forward_from_chat | F.forward_from)
async def handle_forward(message: Message):
    chat_id = None

    # Способ 1: явно указан чат пересылки
    if message.forward_from_chat:
        chat_id = message.forward_from_chat.id
    # Способ 2: если у пересланного сообщения есть sender_chat (анонимные группы, каналы)
    elif message.forward_origin:
        # forward_origin появился в новых версиях Telegram API
        if hasattr(message.forward_origin, 'chat'):
            chat_id = message.forward_origin.chat.id
    # Способ 3: иногда forward_from_message_id содержит ID чата в скрытом виде (недокументированно)

    if not chat_id:
        await message.answer(
            "❌ Не удалось определить чат. Пожалуйста, перешлите **любое сообщение из самой группы** (не из личных сообщений).\n"
            "Убедитесь, что бот добавлен в эту группу."
        )
        return

    await save_shared_chat(message.from_user.id, chat_id)
    await message.answer(f"✅ Чат сохранён! Теперь герои будут отправляться туда при нажатии «📤 Поделиться».")
    try:
        await message.delete()
    except:
        pass


@router.message(F.forward_from)
async def handle_forward_from_user(message: Message, state: FSMContext):
    # Если переслано от пользователя, берём chat_id из forward_from (если это группа/канал)
    if message.forward_from and message.forward_from.id != message.from_user.id:
        # Не совсем точный способ, лучше использовать forward_from_chat
        pass
    await message.answer("Пожалуйста, перешлите сообщение именно из чата (группы), куда хотите отправлять героев.")