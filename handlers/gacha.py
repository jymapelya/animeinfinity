from aiogram import Router, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from db.models import (get_player, update_player, add_character, get_pity_counter,
                       update_pity_counter, add_relic, add_background, get_auto_dismantle)
from engine.gacha_system import pull_character, pull_event_character, pull_event_reward
from engine.data_loader import data_cache
from config import GACHA_COST, GACHA_10_COST
from handlers.utils import edit_or_answer
import random

router = Router()

@router.callback_query(lambda c: c.data == "gacha_menu")
async def gacha_menu(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="1x Pull (300💎)", callback_data="gacha_1")
    builder.button(text="10x Pull (2700💎)", callback_data="gacha_10")
    builder.button(text="🎪 Ивентовый баннер", callback_data="event_gacha_menu")
    builder.button(text="⚙ Автопродажа", callback_data="auto_dismantle")
    builder.button(text="🔙 Назад", callback_data="menu")
    builder.adjust(2)
    await edit_or_answer(callback.message, "🎴 Баннер персонажей:", reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(lambda c: c.data in ["gacha_1", "gacha_10"])
async def pull_gacha(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    player = await get_player(user_id)
    times = 1 if callback.data == "gacha_1" else 10
    cost = GACHA_COST if times == 1 else GACHA_10_COST

    if player['gems'] < cost:
        await callback.answer("Недостаточно гемов!")
        return

    leg_pity, myth_pity, sec_pity = await get_pity_counter(user_id)
    results = []
    sold = []
    total_refund = 0

    for _ in range(times):
        char = pull_character(leg_pity, myth_pity, sec_pity)
        if char['rarity'] in ('Legendary', 'Mythic', 'Secret'):
            leg_pity = 0
        else:
            leg_pity += 1
        if char['rarity'] in ('Mythic', 'Secret'):
            myth_pity = 0
        else:
            myth_pity += 1
        if char['rarity'] == 'Secret':
            sec_pity = 0
        else:
            sec_pity += 1

        if await apply_auto_dismantle(user_id, char):
            base = data_cache.characters.get(char['base_char_id'], {})
            sold.append(base.get('name', char['base_char_id']))
            total_refund += 60 if char['rarity'] in ('Rare', 'Epic') else 120
        else:
            await add_character(user_id, char['base_char_id'], variant=char['variant'],
                                trait=char['trait'], destiny=char['destiny'],
                                iv_hp=char['iv_hp'], iv_atk=char['iv_atk'],
                                iv_def=char['iv_def'], iv_spd=char['iv_spd'],
                                iv_crit=char['iv_crit'])
            results.append(char)

    # Обновляем гемы один раз: списываем стоимость, возвращаем за автопродажу
    await update_player(user_id, gems=player['gems'] - cost + total_refund)
    await update_pity_counter(user_id, leg_pity, myth_pity, sec_pity)

    text = "🎴 Результаты:\n"
    for r in results:
        base = data_cache.characters[r['base_char_id']]
        variant_emoji = {'Normal':'','Shiny':'✨','Golden':'🌟','Prismatic':'💫','Celestial':'☄️'}.get(r['variant'],'')
        text += f"{variant_emoji} {base['name']} ({r['rarity']}) IV:{r['iv_atk']}%\n"

    if sold:
        text += "\n♻️ Автопродано:\n"
        for name in sold:
            text += f"• {name}\n"
        text += f"💰 Возврат: +{total_refund}💎"

    builder = InlineKeyboardBuilder()
    builder.button(text="🎴 Ещё раз", callback_data="gacha_menu")
    builder.button(text="🔙 Назад", callback_data="menu")
    await edit_or_answer(callback.message, text, reply_markup=builder.as_markup())
    await callback.answer()

# ---------- ИВЕНТОВЫЙ БАННЕР ----------
@router.callback_query(lambda c: c.data == "event_gacha_menu")
async def event_gacha_menu(callback: types.CallbackQuery, state: FSMContext):
    event = data_cache.event_banner
    if not event:
        await callback.answer("Ивентовый баннер не активен.")
        return

    user_id = callback.from_user.id
    player = await get_player(user_id)
    pulls = 0

    rates = event.get('rates', {})
    pools = event.get('pools', {})

    # Формируем текст с персонажами и их шансами
    prize_lines = []
    
    # Secret персонажи
    if 'Secret' in pools and pools['Secret']:
        rate = rates.get('Secret', 0)
        per_char_rate = rate / len(pools['Secret']) if len(pools['Secret']) > 0 else rate
        for char_id in pools['Secret']:
            char = data_cache.characters.get(char_id, {})
            name = char.get('name', char_id)
            prize_lines.append(f"🌈 {name}: {per_char_rate:.2f}%")
    
    # Mythic персонажи
    if 'Mythic' in pools and pools['Mythic']:
        rate = rates.get('Mythic', 0)
        per_char_rate = rate / len(pools['Mythic']) if len(pools['Mythic']) > 0 else rate
        for char_id in pools['Mythic']:
            char = data_cache.characters.get(char_id, {})
            name = char.get('name', char_id)
            prize_lines.append(f"🔴 {name}: {per_char_rate:.2f}%")
    
    # Остальные редкости из общего пула
    other_rates = []
    for rar in ['Legendary', 'Epic', 'Rare']:
        if rar in rates and rar not in pools:
            other_rates.append(f"• {rar}: {rates[rar]}%")
    
    prize_text = "\n".join(prize_lines)
    if other_rates:
        prize_text += "\n" + "\n".join(other_rates)

    caption = (
        f"🌪 <b>{event.get('name', 'Ивентовый баннер')}</b>\n"
        f"{event.get('description', '')}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🎰 Прокручено: {pulls}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🎁 Призы:\n"
        f"{prize_text}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"📅 Дата окончания: {event.get('end_date', '?')}\n"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="1x Ивент Pull (400💎)", callback_data="event_pull_1")
    builder.button(text="10x Ивент Pull (3600💎)", callback_data="event_pull_10")
    builder.button(text="🔙 Назад", callback_data="gacha_menu")
    builder.adjust(2)

    image_url = event.get('image_url')
    if image_url:
        try:
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=image_url,
                caption=caption,
                reply_markup=builder.as_markup(),
                parse_mode="HTML"
            )
        except:
            await edit_or_answer(callback.message, caption, reply_markup=builder.as_markup(), parse_mode="HTML")
    else:
        await edit_or_answer(callback.message, caption, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(lambda c: c.data in ["event_pull_1", "event_pull_10"])
async def pull_event_gacha(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    player = await get_player(user_id)
    times = 1 if callback.data == "event_pull_1" else 10
    cost = 400 if times == 1 else 3600

    if player['gems'] < cost:
        await callback.answer("Недостаточно гемов!")
        return

    characters = []
    sold = []
    total_refund = 0
    backgrounds_won = []
    rimuru_obtained = False
    rimuru_card = None

    for _ in range(times):
        reward = pull_event_reward()
        if not reward:
            continue

        if reward['type'] == 'background':
            await add_background(user_id, reward['background_id'])
            backgrounds_won.append(reward['background_id'])
        elif reward['type'] == 'character':
            char = reward['data']
            if char['base_char_id'] == 'rimuru_tempest':
                rimuru_obtained = True
                rimuru_card = char
            if await apply_auto_dismantle(user_id, char):
                base = data_cache.characters.get(char['base_char_id'], {})
                sold.append(base.get('name', char['base_char_id']))
                total_refund += 80
            else:
                await add_character(user_id, char['base_char_id'], variant=char['variant'],
                                    trait=char['trait'], destiny=char['destiny'],
                                    iv_hp=char['iv_hp'], iv_atk=char['iv_atk'],
                                    iv_def=char['iv_def'], iv_spd=char['iv_spd'],
                                    iv_crit=char['iv_crit'])
                characters.append(char)

    await update_player(user_id, gems=player['gems'] - cost + total_refund)

    text = "🎪 Ивентовый баннер\n"
    if characters:
        text += "\n🎴 Полученные герои:\n"
        for r in characters:
            base = data_cache.characters[r['base_char_id']]
            variant_emoji = {'Normal':'','Shiny':'✨','Golden':'🌟','Prismatic':'💫','Celestial':'☄️'}.get(r['variant'],'')
            text += f"{variant_emoji} {base['name']} ({r['rarity']}) IV:{r['iv_atk']}%\n"
    if sold:
        text += "\n♻️ Автопродано:\n"
        for name in sold:
            text += f"• {name}\n"
        text += f"💰 Возврат: +{total_refund}💎"
    if backgrounds_won:
        text += "\n🖼 Получены фоны:\n"
        for bg_id in backgrounds_won:
            bg = data_cache.backgrounds.get(bg_id, {})
            text += f"• {bg.get('name', bg_id)}\n"

    builder = InlineKeyboardBuilder()
    builder.button(text="🎪 Ещё раз", callback_data="event_gacha_menu")
    builder.button(text="🔙 Назад", callback_data="menu")
    await edit_or_answer(callback.message, text, reply_markup=builder.as_markup())

    if rimuru_obtained and rimuru_card:
        rimuru = data_cache.characters['rimuru_tempest']
        trait = rimuru_card.get('trait')
        destiny = rimuru_card.get('destiny')

        card = (
            f"🌈 <b>{rimuru['name']}</b> (Secret)\n"
            f"━━━━━━━━━━━━━━━━\n"
        )
        if trait:
            trait_data = data_cache.traits.get(trait)
            trait_desc = f"{trait_data['name']} — {trait_data['desc']}" if trait_data else trait
            card += f"🧬 Trait: {trait_desc}\n"
        else:
            card += "🧬 Trait: —\n"

        if destiny:
            destiny_data = data_cache.destinies.get(destiny)
            destiny_desc = f"{destiny_data['name']} — {destiny_data['desc']}" if destiny_data else destiny
            card += f"🔮 Destiny: {destiny_desc}\n"
        else:
            card += "🔮 Destiny: —\n"

        card += (
            f"━━━━━━━━━━━━━━━━\n"
            f"❤️ HP: {rimuru['hp']} | ⚔️ ATK: {rimuru['atk']}\n"
            f"🛡️ DEF: {rimuru['def']} | 💨 SPD: {rimuru['spd']}\n"
            f"💥 CRIT: {rimuru['crit']}%\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"⚔️ Навыки:\n"
        )
        for sid in rimuru.get('skills', []):
            skill = data_cache.skills.get(sid)
            if skill:
                cd = skill.get('cooldown', 0)
                cd_text = f" (CD: {cd})" if cd else ""
                card += f"• {skill['name']}{cd_text}: {skill.get('type','')}\n"
        card += "\n🎉 Поздравляем! Вы получили Римуру Темпеста!"

        animation_url = rimuru.get('animation_url')
        image_url = rimuru.get('image_url')
        try:
            if animation_url:
                await callback.message.answer_video(
                    video=animation_url,
                    caption=card,
                    parse_mode="HTML"
                )
            elif image_url:
                await callback.message.answer_photo(
                    photo=image_url,
                    caption=card,
                    parse_mode="HTML"
                )
            else:
                await callback.message.answer(card, parse_mode="HTML")
        except Exception:
            await callback.message.answer(card, parse_mode="HTML")

# ---------- БАННЕР РЕЛИКВИЙ ----------
@router.callback_query(lambda c: c.data == "relic_gacha_menu")
async def relic_gacha_menu(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="1x Реликвия (500💨)", callback_data="relic_pull_1")
    builder.button(text="10x Реликвий (4500💨)", callback_data="relic_pull_10")
    builder.button(text="⚙ Автопродажа", callback_data="auto_dismantle")
    builder.button(text="🔙 Назад", callback_data="relics")
    await edit_or_answer(callback.message, "🎴 Баннер Реликвий:", reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(lambda c: c.data in ["relic_pull_1", "relic_pull_10"])
async def pull_relic(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    player = await get_player(user_id)
    times = 1 if callback.data == "relic_pull_1" else 10
    cost = 500 if times == 1 else 4500
    if player['relic_dust'] < cost:
        await callback.answer("Недостаточно Реликвийной Пыли!")
        return

    rarities = ['Common']*60 + ['Rare']*25 + ['Epic']*10 + ['Legendary']*5
    results = []
    for _ in range(times):
        rarity = random.choice(rarities)
        candidates = [r for r in data_cache.relics.values() if r['rarity'] == rarity]
        relic = random.choice(candidates)
        await add_relic(user_id, relic['id'])
        results.append(relic)

    await update_player(user_id, relic_dust=player['relic_dust'] - cost)

    text = "🎴 Полученные реликвии:\n"
    for r in results:
        text += f"{r['name']} ({r['rarity']}): +{r['value']}% к {r['effect'].upper()}\n"

    builder = InlineKeyboardBuilder()
    builder.button(text="🎴 Ещё раз", callback_data="relic_gacha_menu")
    builder.button(text="🔙 Назад", callback_data="relics")
    await edit_or_answer(callback.message, text, reply_markup=builder.as_markup())
    await callback.answer()

# ---------- БАННЕР ФОНОВ ----------
@router.callback_query(lambda c: c.data == "bg_gacha_menu")
async def bg_gacha_menu(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="1x Фон (500💨)", callback_data="bg_pull_1")
    builder.button(text="10x Фонов (4500💨)", callback_data="bg_pull_10")
    builder.button(text="🔙 Назад", callback_data="backgrounds")
    await edit_or_answer(callback.message, "🎴 Баннер фонов:", reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(lambda c: c.data in ["bg_pull_1", "bg_pull_10"])
async def pull_background(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    player = await get_player(user_id)
    times = 1 if callback.data == "bg_pull_1" else 10
    cost = 500 if times == 1 else 4500
    if player['relic_dust'] < cost:
        await callback.answer("Недостаточно Реликвийной Пыли!")
        return

    rarities = ['Common']*55 + ['Rare']*30 + ['Epic']*10 + ['Legendary']*5
    results = []
    for _ in range(times):
        rarity = random.choice(rarities)
        candidates = [bg for bg in data_cache.backgrounds.values() if bg['rarity'] == rarity]
        if candidates:
            bg = random.choice(candidates)
            await add_background(user_id, bg['id'])
            results.append(bg)

    await update_player(user_id, relic_dust=player['relic_dust'] - cost)

    text = "🎴 Полученные фоны:\n"
    for r in results:
        text += f"{r['name']} ({r['rarity']})\n"

    builder = InlineKeyboardBuilder()
    builder.button(text="🎴 Ещё раз", callback_data="bg_gacha_menu")
    builder.button(text="🔙 Назад", callback_data="backgrounds")
    await edit_or_answer(callback.message, text, reply_markup=builder.as_markup())
    await callback.answer()

async def apply_auto_dismantle(user_id: int, char_info: dict):
    """Возвращает True, если персонаж должен быть продан."""
    settings = await get_auto_dismantle(user_id)
    if not settings or not settings.get('enabled', 0):
        return False

    rarity = char_info['rarity']
    # Проверяем редкость
    if rarity == 'Rare' and not settings.get('dismantle_rare', 0):
        return False
    if rarity == 'Epic' and not settings.get('dismantle_epic', 0):
        return False
    if rarity == 'Legendary' and not settings.get('dismantle_legendary', 0):
        return False
    if rarity in ('Mythic', 'Secret'):
        return False   # Никогда не продаём мификов и секреток

    # Если есть трейт или судьба, и настройки требуют их сохранять
    if settings.get('keep_if_trait', 0) and char_info.get('trait'):
        return False
    if settings.get('keep_if_destiny', 0) and char_info.get('destiny'):
        return False

    # Проверяем минимальные IV: если хотя бы один стат НИЖЕ порога – продаём
    iv_checks = {
        'iv_atk': settings.get('min_iv_atk', 0),
        'iv_hp': settings.get('min_iv_hp', 0),
        'iv_def': settings.get('min_iv_def', 0),
        'iv_spd': settings.get('min_iv_spd', 0),
        'iv_crit': settings.get('min_iv_crit', 0)
    }
    for iv_field, min_val in iv_checks.items():
        if min_val > 0 and char_info.get(iv_field, 0) < min_val:
            return True   # Стат ниже порога → продаём

    # Если все проверки пройдены, то персонаж НЕ продаётся
    return False

