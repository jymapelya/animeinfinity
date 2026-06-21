from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from db.models import get_player, get_team_characters, update_player, add_relic, calculate_team_power, get_equipped_relic
from engine.battle_system import simulate_battle
from engine.data_loader import data_cache
from handlers.utils import edit_or_answer
import random, json, os

router = Router()

def load_mutations():
    with open(os.path.join('data', 'tower_mutations.json'), 'r', encoding='utf-8') as f:
        return json.load(f)

mutations = load_mutations()

def get_active_mutation(floor: int):
    for m in mutations:
        if m['floor'] == floor:
            return m
    return None

def generate_tower_enemies(floor: int):
    base_hp = 100 * (1.08 ** floor)
    base_atk = 20 * (1.06 ** floor)
    base_def = 10 + floor // 10
    base_spd = 80 + floor // 5
    enemies = []
    count = random.randint(1, min(3, 1 + floor // 100))
    for _ in range(count):
        enemies.append({
            'name': f'Страж башни (ур.{floor})',
            'hp': int(base_hp * random.uniform(0.9, 1.1)),
            'atk': int(base_atk * random.uniform(0.9, 1.1)),
            'def': int(base_def * random.uniform(0.9, 1.1)),
            'spd': base_spd + random.randint(-10, 10),
            'skills': [{'id': 'basic', 'type': 'damage', 'target': 'single', 'cooldown': 0, 'multiplier': 1.0}]
        })
    return enemies

async def get_tower_progress(user_id: int):
    from db.models import get_db
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT highest_floor, current_floor FROM tower_progress WHERE player_id=?",
            (user_id,)
        )
        row = await cursor.fetchone()
        if row:
            return row['highest_floor'], row['current_floor']
        else:
            await db.execute(
                "INSERT INTO tower_progress (player_id, highest_floor, current_floor) VALUES (?, 1, 1)",
                (user_id,)
            )
            await db.commit()
            return 1, 1
    finally:
        await db.close()

async def save_tower_progress(user_id: int, floor: int):
    from db.models import get_db
    db = await get_db()
    try:
        await db.execute(
            "UPDATE tower_progress SET current_floor=?, highest_floor=MAX(highest_floor, ?) WHERE player_id=?",
            (floor, floor, user_id)
        )
        await db.commit()
    finally:
        await db.close()

@router.callback_query(lambda c: c.data == "tower")
async def tower_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    highest, current = await get_tower_progress(user_id)
    await calculate_team_power(user_id)
    player = await get_player(user_id)

    mutation = get_active_mutation(current)
    mutation_text = ""
    if mutation:
        mutation_text = f"\n⚠️ <b>Мутация:</b> {mutation['name']} — {mutation['description']}\n"

    text = (
        f"🗼 <b>Башня Испытаний</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🏁 Текущий этаж: <b>{current}</b>\n"
        f"🏆 Рекорд: <b>{highest}</b>\n"
        f"{mutation_text}"
        f"━━━━━━━━━━━━━━━━\n"
        f"💪 Сила команды: {player['team_power']}\n"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="⚔ В бой!", callback_data="tower_fight")
    builder.button(text="🔙 Назад", callback_data="menu")
    builder.adjust(1)
    await edit_or_answer(callback.message, text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(lambda c: c.data == "tower_fight")
async def tower_fight(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    player = await get_player(user_id)
    team = await get_team_characters(user_id)
    if not team:
        await callback.answer("Нет команды! Соберите отряд.")
        return

    highest, current = await get_tower_progress(user_id)
    mutation = get_active_mutation(current)

    if mutation and 'role_restriction' in mutation:
        allowed_roles = mutation['role_restriction']
        for hero in team:
            base = data_cache.characters.get(hero['base_char_id'])
            if base and base.get('role') not in allowed_roles:
                await callback.answer(f"Мутация запрещает героев с ролью не из списка: {allowed_roles}")
                return

    if mutation and 'max_team_size' in mutation:
        team = team[:mutation['max_team_size']]

    enemies = generate_tower_enemies(current)
    battle_result = await simulate_battle(team, enemies, user_id, mutations=mutation)

    if battle_result['victory']:
        base_gold = 100 + current * 10
        # Бонус золота от реликвий команды
        gold_bonus = 0
        if team:
            for hero in team:
                relic_data = await get_equipped_relic(hero['id'])
                if relic_data:
                    relic = data_cache.relics.get(relic_data['relic_id'])
                    if relic and relic['effect'] == 'gold':
                        gold_bonus += relic['value']
        gold_earned = int(base_gold * random.uniform(0.9, 1.1) * (1 + gold_bonus / 100))
        dust_earned = current * 2
        await update_player(user_id,
                            gold=player['gold'] + gold_earned,
                            relic_dust=player['relic_dust'] + dust_earned)

        new_floor = current + 1
        await save_tower_progress(user_id, new_floor)

        msg = f"🎉 <b>Этаж {current} пройден!</b>\n"
        msg += f"💰 Золото: +{gold_earned}\n"
        msg += f"💨 Пыль: +{dust_earned}\n"

        if new_floor % 10 == 0:
            if random.random() < 0.3:
                relic = random.choice(list(data_cache.relics.values()))
                await add_relic(user_id, relic['id'])
                msg += f"📦 Реликвия: {relic['name']}\n"

        if new_floor % 50 == 0:
            msg += "🏆 <b>Пройдена веха! Особая награда ждёт!</b>\n"
    else:
        msg = f"💀 <b>Поражение на этаже {current}</b>\n"
        await save_tower_progress(user_id, current)

    msg += f"━━━━━━━━━━━━━━━━\n"
    msg += f"⏱ Ходов: {battle_result['total_turns']}\n"
    if battle_result['mvp']:
        msg += f"🏆 Лучший боец: {battle_result['mvp']} (урон: {battle_result['mvp_damage']})\n"
    if battle_result['survivors']:
        msg += f"✅ Выжили: {', '.join(battle_result['survivors'])}\n"
    if battle_result['defeated']:
        msg += f"💔 Погибли: {', '.join(battle_result['defeated'])}\n"

    if battle_result.get('suggestions'):
        msg += f"━━━━━━━━━━━━━━━━\n📝 <b>Советы:</b>\n"
        for s in battle_result['suggestions'][:2]:
            msg += f"• {s}\n"

    builder = InlineKeyboardBuilder()
    if battle_result['victory']:
        builder.button(text="▶ Следующий этаж", callback_data="tower_fight")
    else:
        builder.button(text="🔄 Попробовать снова", callback_data="tower_fight")
    builder.button(text="🔙 К башне", callback_data="tower")
    builder.adjust(1)

    await edit_or_answer(callback.message, msg, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()