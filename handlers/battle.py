from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from db.models import get_player, get_team_characters, update_player, add_inventory_item, add_relic, get_equipped_relic
from engine.battle_system import simulate_battle
from engine.data_loader import data_cache
from handlers.utils import edit_or_answer
from aiogram.types import BufferedInputFile
import random, json, os, tempfile

router = Router()

def load_worlds():
    with open(os.path.join('data', 'worlds.json'), 'r', encoding='utf-8') as f:
        return json.load(f)

worlds = load_worlds()

def generate_wave(world: int, wave: int):
    world_mult = data_cache.world_mult.get(str(world), 1.0)
    world_data = worlds.get(str(world), {})
    is_boss = (wave == 9)
    enemies = []

    if is_boss:
        boss_id = world_data.get('boss_id', 'boss_leviathan')
        boss_conf = data_cache.enemies.get(boss_id, {})
        if boss_conf:
            boss_skills = []
            for sid in boss_conf.get('skills', ['basic_attack']):
                skill = data_cache.skills.get(sid)
                if skill:
                    boss_skills.append(skill)
                else:
                    boss_skills.append({'id': sid, 'type': 'damage', 'target': 'single', 'cooldown': 0, 'multiplier': 1.0})
            enemies.append({
                'name': boss_conf.get('name', 'Босс'),
                'hp': boss_conf.get('hp', 5000),
                'atk': boss_conf.get('atk', 150),
                'def': boss_conf.get('def', 30),
                'spd': boss_conf.get('spd', 80),
                'skills': boss_skills
            })
        else:
            enemies.append({
                'name': world_data.get('boss_name', 'Босс'),
                'hp': int(500 * (1.2 ** wave)),
                'atk': int(40 * (1.12 ** wave)),
                'def': 15 + (world - 1) * 5,
                'spd': 80 + wave * 2,
                'skills': [{'id': 'basic_attack', 'type': 'damage', 'target': 'single', 'multiplier': 1.0}]
            })
    else:
        enemy_types = world_data.get('enemy_types', [])
        if enemy_types:
            count = random.randint(1, 3)
            for _ in range(count):
                eid = random.choice(enemy_types)
                econ = data_cache.enemies.get(eid, {})
                if econ:
                    e_skills = []
                    for sid in econ.get('skills', ['basic_attack']):
                        skill = data_cache.skills.get(sid)
                        if skill:
                            e_skills.append(skill)
                        else:
                            e_skills.append({'id': sid, 'type': 'damage', 'target': 'single', 'cooldown': 0, 'multiplier': 1.0})
                    enemies.append({
                        'name': econ.get('name', 'Монстр'),
                        'hp': int(econ.get('hp', 100) * world_mult),
                        'atk': int(econ.get('atk', 20) * world_mult),
                        'def': int(econ.get('def', 5) * world_mult),
                        'spd': econ.get('spd', 70),
                        'skills': e_skills
                    })
        else:
            base_hp = 100 * (1.2 ** wave) * world_mult
            base_atk = 25 * (1.1 ** wave) * world_mult
            count = random.randint(1, 3)
            for _ in range(count):
                enemies.append({
                    'name': 'Монстр',
                    'hp': int(base_hp * random.uniform(0.8, 1.2)),
                    'atk': int(base_atk * random.uniform(0.9, 1.1)),
                    'def': int(10 * world_mult),
                    'spd': 70 + wave,
                    'skills': [{'id': 'basic_attack', 'type': 'damage', 'target': 'single', 'cooldown': 0, 'multiplier': 1.0}]
                })
    return enemies

@router.callback_query(lambda c: c.data == "campaign")
async def campaign_menu(callback: types.CallbackQuery):
    player = await get_player(callback.from_user.id)
    if not player:
        await callback.answer("Игрок не найден. Пожалуйста, нажмите /start")
        return
    world_id = str(player['max_world'])
    world = worlds.get(world_id, {})
    world_name = world.get('name', 'Неизвестный мир')
    boss_name = world.get('boss_name', 'Босс')
    enemy_types = world.get('enemy_types', ['Монстры'])
    
    wave = player['max_wave']
    
    if wave == 9:
        enemy_desc = f"🐉 БОСС: {boss_name}"
    else:
        # Преобразуем ID врагов в читаемые названия
        enemy_names = []
        for eid in enemy_types:
            econ = data_cache.enemies.get(eid, {})
            enemy_names.append(econ.get('name', eid))
        enemy_desc = f"⚔ Враги: {', '.join(enemy_names)}"
    
    text = (
        f"📍 {world_name}\n"
        f"🌊 Волна {wave}/9\n"
        f"{enemy_desc}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"💪 Сила команды: {player['team_power']}\n"
    )
    builder = InlineKeyboardBuilder()
    builder.button(text="⚔ В бой!", callback_data="campaign_fight")
    builder.button(text="🔙 Назад", callback_data="menu")
    await edit_or_answer(callback.message, text, reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(lambda c: c.data == "campaign_fight")
async def campaign_fight(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    player = await get_player(user_id)
    team = await get_team_characters(user_id)
    if not team:
        await callback.answer("Нет команды! Соберите отряд в разделе «Команда».")
        return

    wave_conf = generate_wave(player['max_world'], player['max_wave'])
    result = await simulate_battle(team, wave_conf, user_id)

    base_gold = 50 + player['max_wave'] * 10
    gold_earned = int(base_gold * data_cache.world_mult.get(str(player['max_world']), 1.0))
    dust_earned = 0
    relic_dropped = None
    item_dropped = None

    if result['victory']:
        new_wave = player['max_wave'] + 1
        new_world = player['max_world']
        if new_wave > 9:
            new_wave = 1
            new_world += 1
            dust_earned = new_world * 100
            if random.random() < 0.15:
                candidates = [r for r in data_cache.relics.values() if r['rarity'] != 'Secret']
                if candidates:
                    relic = random.choice(candidates)
                    await add_relic(user_id, relic['id'])
                    relic_dropped = relic['name']
        if random.random() < 0.1:
            items_list = list(data_cache.items.values())
            if items_list:
                item = random.choice(items_list)
                await add_inventory_item(user_id, item['type'], item['id'])
                item_dropped = item['name']

        await update_player(user_id,
                            max_world=new_world,
                            max_wave=new_wave,
                            gold=player['gold'] + gold_earned,
                            relic_dust=player['relic_dust'] + dust_earned)

        world_data = worlds.get(str(new_world), {"name": "Неизвестный мир"})
        msg = f"🎉 **Победа!**\n📍 {world_data.get('name', 'Мир')}, волна {new_wave}\n"
    else:
        msg = "💀 **Поражение**\n"

    msg += f"━━━━━━━━━━━━━━━━\n"
    msg += f"⏱ Ходов: {result['total_turns']}\n"
    if result['mvp']:
        msg += f"🏆 Лучший боец: {result['mvp']} (урон: {result['mvp_damage']})\n"
    if result['survivors']:
        msg += f"✅ Выжили: {', '.join(result['survivors'])}\n"
    if result['defeated']:
        msg += f"💔 Погибли: {', '.join(result['defeated'])}\n"

    if result['victory']:
        msg += f"━━━━━━━━━━━━━━━━\n"
        msg += f"💰 Золото: +{gold_earned}\n"
        if dust_earned:
            msg += f"💨 Пыль: +{dust_earned}\n"
        if relic_dropped:
            msg += f"📦 Реликвия: {relic_dropped}\n"
        if item_dropped:
            msg += f"📦 Предмет: {item_dropped}\n"

    if result['suggestions']:
        msg += f"━━━━━━━━━━━━━━━━\n📝 **Советы:**\n"
        for s in result['suggestions']:
            msg += f"• {s}\n"

    # Сохраняем лог в состоянии
    detailed_log_text = "\n".join(result.get('log', []))
    await state.update_data(last_battle_log=detailed_log_text)

    builder = InlineKeyboardBuilder()
    if result['victory']:
        builder.button(text="⚔ Продолжить", callback_data="campaign_fight")
    else:
        builder.button(text="🔄 Попробовать снова", callback_data="campaign_fight")
    builder.button(text="📜 Полный лог", callback_data="battle_log")
    builder.button(text="🔙 В меню", callback_data="menu")
    builder.adjust(2)

    await edit_or_answer(callback.message, msg, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()


@router.callback_query(lambda c: c.data == "battle_log")
async def send_battle_log(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    log_text = data.get('last_battle_log', 'Лог отсутствует.')
    # Отправляем как текстовый файл прямо из памяти
    document = BufferedInputFile(log_text.encode('utf-8'), filename='battle_log.txt')
    await callback.message.answer_document(document, caption="📜 Полный журнал боя")
    await callback.answer()