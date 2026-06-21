from aiogram import Router, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from db.models import get_player, update_player
from engine.data_loader import data_cache
from datetime import datetime, timezone
from handlers.utils import edit_or_answer
import random

router = Router()

AFK_MAX_HOURS = 12
WAVE_DURATION = 30  # секунд на волну

@router.callback_query(lambda c: c.data == "afk_rewards")
async def afk_rewards(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    player = await get_player(user_id)
    if not player:
        await callback.answer("Игрок не найден.")
        return

    now = datetime.now(timezone.utc)
    last_time_str = player.get('last_afk_time')
    if last_time_str:
        last_time = datetime.fromisoformat(last_time_str)
        if last_time.tzinfo is None:
            last_time = last_time.replace(tzinfo=timezone.utc)
    else:
        last_time = now

    delta = (now - last_time).total_seconds()
    max_seconds = AFK_MAX_HOURS * 3600
    if delta > max_seconds:
        delta = max_seconds

    if delta < 1:
        await callback.answer("Вы только что собирали награды.")
        return

    max_world = player.get('max_world', 1)
    max_wave = player.get('max_wave', 1)

    # Новая формула
    base_gold_per_wave = 30 + max_wave * 5
    afk_world_mult = 1.0 + (max_world - 1) * 0.4
    waves_completed = delta / WAVE_DURATION
    # Бонус золота от реликвий команды
    gold_bonus = 0
    team = await get_team_characters(user_id)
    if team:
        for hero in team:
            relic_data = await get_equipped_relic(hero['id'])
            if relic_data:
                relic = data_cache.relics.get(relic_data['relic_id'])
                if relic and relic['effect'] == 'gold':
                    gold_bonus += relic['value']
    gold_earned = int(gold_earned * (1 + gold_bonus / 100))

    gems_earned = 0
    tickets_earned = 0
    dust_earned = 0
    cores_earned = 0

    if random.random() < (delta / 600) * 0.3:
        gems_earned = random.randint(1, 3)

    if delta >= 7200 and random.random() < 0.2:
        tickets_earned = 1

    if random.random() < (delta / 300) * 0.4:
        dust_earned = random.randint(1, 5)

    if random.random() < (delta / 600) * 0.2:
        cores_earned = random.randint(1, 3)

    new_gold = player['gold'] + gold_earned
    new_gems = player['gems'] + gems_earned
    new_tickets = player['tickets'] + tickets_earned
    new_dust = player['relic_dust'] + dust_earned
    new_cores = player['awakening_cores'] + cores_earned

    await update_player(user_id,
                        gold=new_gold,
                        gems=new_gems,
                        tickets=new_tickets,
                        relic_dust=new_dust,
                        awakening_cores=new_cores,
                        last_afk_time=now.isoformat())

    hours = int(delta // 3600)
    minutes = int((delta % 3600) // 60)
    text = (f"⏳ Отсутствовал {hours} ч {minutes} мин\n"
            f"📍 Рекорд: Мир {max_world}-{max_wave}\n"
            f"💰 Золото: +{gold_earned}\n")
    if gems_earned:
        text += f"💎 Гемы: +{gems_earned}\n"
    if tickets_earned:
        text += f"🎫 Билеты: +{tickets_earned}\n"
    if dust_earned:
        text += f"💨 Пыль: +{dust_earned}\n"
    if cores_earned:
        text += f"💎 Ядер: +{cores_earned}\n"

    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="menu")
    await edit_or_answer(callback.message, text, reply_markup=builder.as_markup())
    await callback.answer()