import random
from engine.data_loader import data_cache
from db.models import get_equipped_relic, get_awakening_level

async def simulate_battle(team_chars, wave_enemies, player_id: int, mutations=None):
    units = []
    for pc in team_chars:
        base = data_cache.characters.get(pc['base_char_id'])
        if not base:
            continue

        # Базовые параметры с учётом IV
        hp = 100 * (pc.get('iv_hp', 100) / 100)
        atk = 50 * (pc.get('iv_atk', 100) / 100)
        def_ = 30 * (pc.get('iv_def', 100) / 100)
        spd = 80 * (pc.get('iv_spd', 100) / 100)
        crit = 5 * (pc.get('iv_crit', 100) / 100)

        # Реликвия
        relic_data = await get_equipped_relic(pc['id'])
        if relic_data:
            relic = data_cache.relics[relic_data['relic_id']]
            effect = relic['effect']
            value = relic['value']
            if effect == 'hp': hp *= (1 + value / 100)
            elif effect == 'atk': atk *= (1 + value / 100)
            elif effect == 'def': def_ *= (1 + value / 100)
            elif effect == 'spd': spd *= (1 + value / 100)
            elif effect == 'crit': crit += value

        # Звёзды пробуждения
        stars = await get_awakening_level(player_id, pc['base_char_id'])
        star_mult = 1 + (stars * 0.05)
        hp = round(hp * star_mult)
        atk = round(atk * star_mult)
        def_ = round(def_ * star_mult)
        spd = round(spd * star_mult)

        # Инициализация особых эффектов
        lifesteal = 0
        reflect = 0
        regen = 0
        double_first = False
        ignore_def = 0
        rebirth = 0
        rebirth_used = False
        dodge = 0
        first_strike_done = False
        skill_damage_bonus = 0
        atk_when_low_hp = 0
        execute_damage = 0
        magic_damage = 0
        heal_power = 0
        shield_heal_power = 0
        revenge_atk = 0
        survive_lethal = False
        first_strike_spd = 0
        boss_damage = 0

        # Трейт
        trait_data = data_cache.traits.get(pc.get('trait'))
        if trait_data:
            effect = trait_data['effect']
            bonus = trait_data['bonus']
            if effect == 'spd': spd *= (1 + bonus / 100)
            elif effect == 'skill_damage': skill_damage_bonus = bonus / 100
            elif effect == 'atk_when_low_hp': atk_when_low_hp = bonus / 100
            elif effect == 'crit': crit += bonus
            elif effect == 'def': def_ *= (1 + bonus / 100)
            elif effect == 'lifesteal': lifesteal = bonus / 100
            elif effect == 'execute_damage': execute_damage = bonus / 100
            elif effect == 'magic_damage': magic_damage = bonus / 100
            elif effect == 'def_up_spd_down': def_ *= (1 + bonus / 100); spd *= 0.9
            elif effect == 'atk_up_hp_down': atk *= (1 + bonus / 100); hp *= 0.8
            elif effect == 'spd_crit_up': spd *= (1 + bonus / 100); crit += 5
            elif effect == 'heal_power': heal_power = bonus / 100
            elif effect == 'reflect_damage': reflect = bonus / 100
            elif effect == 'dodge': dodge = bonus / 100
            elif effect == 'revenge_atk': revenge_atk = bonus / 100
            elif effect == 'hp': hp *= (1 + bonus / 100)
            elif effect == 'first_strike_spd': first_strike_spd = bonus / 100
            elif effect == 'magic_def': pass  # сопротивление магии (пока не реализовано)
            elif effect == 'boss_damage': boss_damage = bonus / 100
            elif effect == 'survive_lethal': survive_lethal = True

        # Судьба
        destiny_data = data_cache.destinies.get(pc.get('destiny'))
        if destiny_data:
            if 'bonus_hp' in destiny_data: hp *= (1 + destiny_data['bonus_hp'] / 100)
            if 'bonus_atk' in destiny_data: atk *= (1 + destiny_data['bonus_atk'] / 100)
            if 'bonus_crit' in destiny_data: crit += destiny_data['bonus_crit']
            if 'bonus_dmg' in destiny_data: atk *= (1 + destiny_data['bonus_dmg'] / 100)
            if 'regen_per_turn' in destiny_data: regen = max(regen, destiny_data['regen_per_turn'] / 100)
            if 'dragon_damage' in destiny_data: boss_damage = max(boss_damage, destiny_data['dragon_damage'] / 100)
            if 'double_first_strike' in destiny_data: double_first = True
            if 'shield_heal_power' in destiny_data: shield_heal_power = destiny_data['shield_heal_power'] / 100
            if 'ignore_def' in destiny_data: ignore_def = max(ignore_def, destiny_data['ignore_def'] / 100)
            if 'rebirth' in destiny_data: rebirth = max(rebirth, destiny_data['rebirth'] / 100)
            if 'bonus_spd' in destiny_data: spd *= (1 + destiny_data['bonus_spd'] / 100)
            if 'bonus_dodge' in destiny_data: dodge = max(dodge, destiny_data['bonus_dodge'] / 100)
            if 'bonus_all' in destiny_data:
                bonus_all = destiny_data['bonus_all'] / 100
                hp *= (1 + bonus_all)
                atk *= (1 + bonus_all)
                def_ *= (1 + bonus_all)
                spd *= (1 + bonus_all)

        # Округляем итоговые статы
        hp, atk, def_, spd = round(hp), round(atk), round(def_), round(spd)
        crit = round(crit)

        skills = [data_cache.skills[sid] for sid in base.get('skills', []) if sid in data_cache.skills]
        units.append({
            'name': base.get('name', 'Unknown'),
            'hp': hp, 'max_hp': hp,
            'atk': atk, 'def': def_, 'spd': spd,
            'crit': crit,
            'skills': skills,
            'cooldowns': {s['id']: 0 for s in skills},
            'buffs': {}, 'shield': 0, 'alive': True,
            'damage_dealt': 0, 'damage_taken': 0, 'healing_done': 0,
            'lifesteal': lifesteal,
            'reflect': reflect,
            'regen': regen,
            'double_first': double_first,
            'ignore_def': ignore_def,
            'rebirth': rebirth,
            'rebirth_used': rebirth_used,
            'dodge': dodge,
            'first_strike_done': first_strike_done,
            'skill_damage_bonus': skill_damage_bonus,
            'atk_when_low_hp': atk_when_low_hp,
            'execute_damage': execute_damage,
            'magic_damage': magic_damage,
            'heal_power': heal_power,
            'shield_heal_power': shield_heal_power,
            'revenge_atk': revenge_atk,
            'survive_lethal': survive_lethal,
            'first_strike_spd': first_strike_spd,
            'boss_damage': boss_damage,
        })

    # Враги
    enemies = []
    for e in wave_enemies:
        enemies.append({
            'name': e.get('name', 'Monster'),
            'hp': e.get('hp', 100), 'max_hp': e.get('hp', 100),
            'atk': e.get('atk', 10), 'def': e.get('def', 0), 'spd': e.get('spd', 50),
            'crit': 0,
            'skills': e.get('skills', [{'id': 'basic', 'type': 'damage', 'target': 'single', 'cooldown': 0, 'multiplier': 1.0}]),
            'cooldowns': {}, 'buffs': {}, 'shield': 0, 'alive': True,
            'damage_dealt': 0, 'damage_taken': 0, 'healing_done': 0,
        })

    # Применяем мутации (если есть)
    if mutations:
        if 'damage_multiplier' in mutations:
            for u in units + enemies:
                u['atk'] *= mutations['damage_multiplier']
        if 'heal_per_turn' in mutations:
            for u in units + enemies:
                u['regen'] = max(u.get('regen', 0), mutations['heal_per_turn'])

    log = []
    turn = 0
    max_turns = 100

    while (any(u['alive'] for u in units) and any(e['alive'] for e in enemies)) and turn < max_turns:
        turn += 1
        all_combatants = [c for c in units + enemies if c['alive']]
        all_combatants.sort(key=lambda x: x['spd'], reverse=True)

        # Регенерация в начале хода
        for entity in all_combatants:
            if entity.get('regen', 0) > 0:
                heal_amount = entity['max_hp'] * entity['regen']
                entity['hp'] = min(entity['max_hp'], entity['hp'] + heal_amount)
                entity['healing_done'] += heal_amount
                log.append(f"💚 {entity['name']} regenerated {int(heal_amount)} HP")

        for combatant in all_combatants:
            if not combatant['alive']:
                continue

            if combatant in units:
                team_list = units
                enemy_list = enemies
            else:
                team_list = enemies
                enemy_list = units

            live_enemies = [e for e in enemy_list if e['alive']]
            live_allies = [u for u in team_list if u['alive']]

            if not live_enemies:
                break

            # Выбор навыка
            available_skill = None
            for skill in combatant['skills']:
                if combatant['cooldowns'].get(skill['id'], 0) == 0:
                    available_skill = skill
                    break
            if available_skill is None:
                available_skill = {'id': 'basic', 'type': 'damage', 'target': 'single', 'multiplier': 1.0}

            skill = available_skill
            target = random.choice(live_enemies) if live_enemies else None
            if target is None:
                continue

            # Двойной первый удар
            if combatant.get('double_first') and not combatant.get('first_strike_done'):
                combatant['first_strike_done'] = True
                if skill['type'] == 'damage':
                    skill = skill.copy()
                    skill['multiplier'] = skill.get('multiplier', 1.0) * 2
                    log.append(f"💥 {combatant['name']} Double First Strike!")

            # Бонус скорости первого удара
            if combatant.get('first_strike_spd') and not combatant.get('first_strike_done'):
                combatant['first_strike_done'] = True
                combatant['spd'] *= (1 + combatant['first_strike_spd'])
                log.append(f"⚡ {combatant['name']} acts faster with first strike!")

            if skill['type'] == 'damage':
                # Модификатор урона от навыков
                skill_mult = skill.get('multiplier', 1.0) * (1 + combatant.get('skill_damage_bonus', 0))
                # Бонус магического урона
                if skill.get('id') in ['explosion', 'shadow_slash', 'amaterasu', 'zanka_no_tachi']:  # магические скиллы
                    skill_mult *= (1 + combatant.get('magic_damage', 0))

                raw_dmg = (combatant['atk'] * skill_mult * random.uniform(0.9, 1.1)) - (target['def'] * 0.5)

                # Игнорирование защиты
                if combatant.get('ignore_def', 0) > 0:
                    raw_dmg += target['def'] * combatant['ignore_def']

                # Бонус против боссов
                if 'boss' in target.get('name', '').lower() or 'босс' in target.get('name', '').lower():
                    raw_dmg *= (1 + combatant.get('boss_damage', 0))

                # Атака при низком HP
                if combatant['hp'] < combatant['max_hp'] * 0.5:
                    raw_dmg *= (1 + combatant.get('atk_when_low_hp', 0))

                # Добивание целей с низким HP
                if target['hp'] < target['max_hp'] * 0.3:
                    raw_dmg *= (1 + combatant.get('execute_damage', 0))

                dmg = max(1, int(raw_dmg))

                # Крит
                if random.random() < combatant['crit'] / 100:
                    dmg = int(dmg * random.uniform(1.5, 2.0))
                    log.append(f"💥 {combatant['name']} CRIT {dmg} to {target['name']}")
                else:
                    log.append(f"⚔️ {combatant['name']} dealt {dmg} to {target['name']}")

                # Уклонение цели
                if target.get('dodge', 0) > 0 and random.random() < target['dodge']:
                    log.append(f"🌀 {target['name']} dodged the attack!")
                    dmg = 0

                if dmg > 0:
                    # Вампиризм
                    if combatant.get('lifesteal', 0) > 0:
                        heal_amount = dmg * combatant['lifesteal']
                        combatant['hp'] = min(combatant['max_hp'], combatant['hp'] + heal_amount)
                        combatant['healing_done'] += heal_amount
                        log.append(f"🩸 {combatant['name']} healed {int(heal_amount)} from lifesteal")

                    # Отражение урона
                    if target.get('reflect', 0) > 0:
                        reflect_dmg = dmg * target['reflect']
                        combatant['hp'] -= reflect_dmg
                        target['damage_dealt'] += reflect_dmg
                        log.append(f"🛡️ {target['name']} reflected {int(reflect_dmg)} damage")
                        if combatant['hp'] <= 0:
                            combatant['hp'] = 0
                            combatant['alive'] = False
                            log.append(f"💀 {combatant['name']} killed by reflect")

                    if target['shield'] > 0:
                        absorbed = min(target['shield'], dmg)
                        target['shield'] -= absorbed
                        dmg -= absorbed
                    target['hp'] -= dmg
                    target['damage_taken'] += dmg
                    combatant['damage_dealt'] += dmg

                    if target['hp'] <= 0:
                        target['hp'] = 0
                        target['alive'] = False
                        log.append(f"💀 {target['name']} defeated")

                    # AoE
                    if skill.get('target') == 'aoe':
                        extra_targets = [e for e in live_enemies if e != target][:2]
                        for et in extra_targets:
                            dmg_aoe = max(1, int(dmg * 0.6))
                            if et['shield'] > 0:
                                absorbed = min(et['shield'], dmg_aoe)
                                et['shield'] -= absorbed
                                dmg_aoe -= absorbed
                            et['hp'] -= dmg_aoe
                            et['damage_taken'] += dmg_aoe
                            combatant['damage_dealt'] += dmg_aoe
                            if et['hp'] <= 0:
                                et['hp'] = 0
                                et['alive'] = False
                                log.append(f"💀 {et['name']} defeated by AoE")
                else:
                    log.append(f"🌀 {target['name']} dodged all damage!")

            elif skill['type'] == 'heal':
                heal_power = 1 + combatant.get('heal_power', 0) + combatant.get('shield_heal_power', 0)
                if skill.get('target') == 'self':
                    heal_targets = [combatant]
                elif skill.get('target') == 'ally_all':
                    heal_targets = live_allies
                else:
                    heal_targets = [random.choice(live_allies)] if live_allies else []
                for ht in heal_targets:
                    heal = combatant['atk'] * skill.get('multiplier', 0.2) * heal_power
                    ht['hp'] = min(ht['max_hp'], ht['hp'] + heal)
                    combatant['healing_done'] += heal
                log.append(f"💚 {combatant['name']} healed {len(heal_targets)} target(s)")

            elif skill['type'] == 'buff':
                stat = skill.get('stat', 'atk')
                value = skill.get('value', 0.1)
                duration = skill.get('duration', 2)
                if skill.get('target') == 'self':
                    combatant['buffs'][stat] = (value, turn + duration)
                    log.append(f"✨ {combatant['name']} buffed self {stat} +{value*100}%")
                elif skill.get('target') == 'ally_all':
                    for u in live_allies:
                        u['buffs'][stat] = (value, turn + duration)
                    log.append(f"✨ {combatant['name']} buffed team {stat} +{value*100}%")

            elif skill['type'] == 'debuff':
                stat = skill.get('stat', 'spd')
                value = skill.get('value', -0.2)
                duration = skill.get('duration', 2)
                if skill.get('target') == 'aoe':
                    for e in live_enemies:
                        e['buffs'][stat] = (value, turn + duration)
                    log.append(f"🌀 {combatant['name']} debuffed all enemies {stat} {value*100}%")
                else:
                    target['buffs'][stat] = (value, turn + duration)
                    log.append(f"🌀 {combatant['name']} debuffed {target['name']} {stat} {value*100}%")

            elif skill['type'] == 'summon':
                dmg = combatant['atk'] * 1.5
                target['hp'] -= dmg
                target['damage_taken'] += dmg
                combatant['damage_dealt'] += dmg
                log.append(f"🐉 {combatant['name']} summoned creature dealing {int(dmg)} to {target['name']}")
                if target['hp'] <= 0:
                    target['alive'] = False
                    log.append(f"💀 {target['name']} defeated by summon")

            # Откат скиллов
            for sid, cd in combatant['cooldowns'].items():
                if cd > 0:
                    combatant['cooldowns'][sid] -= 1
            if skill['id'] != 'basic' and 'cooldown' in skill:
                combatant['cooldowns'][skill['id']] = skill['cooldown']

        # Обработка выживания при смертельном ударе (Immortal)
        for entity in all_combatants:
            if entity.get('survive_lethal') and not entity['alive'] and entity.get('hp') <= 0:
                entity['hp'] = 1
                entity['alive'] = True
                entity['survive_lethal'] = False  # одноразово
                log.append(f"🛡️ {entity['name']} survived with 1 HP!")

        # Возрождение (Rebirth)
        for entity in all_combatants:
            if not entity['alive'] and entity.get('rebirth', 0) > 0 and not entity.get('rebirth_used', False):
                entity['hp'] = entity['max_hp'] * entity['rebirth']
                entity['alive'] = True
                entity['rebirth_used'] = True
                log.append(f"✨ {entity['name']} revived with {int(entity['hp'])} HP!")

        # Снятие баффов/дебаффов
        for entity in all_combatants:
            expired = [stat for stat, (val, end) in entity['buffs'].items() if end <= turn]
            for stat in expired:
                del entity['buffs'][stat]

    # Аналитика
    survivors = [u for u in units if u['alive']]
    defeated = [u for u in units if not u['alive']]
    mvp = max(units, key=lambda u: u['damage_dealt']) if units else None

    suggestions = []
    roles = [data_cache.characters[pc['base_char_id']]['role'] for pc in team_chars if pc['base_char_id'] in data_cache.characters]
    if 'Tank' not in roles:
        suggestions.append("🛡️ В команде нет танка — враги быстро убивают ваших бойцов.")
    if 'Support' not in roles and 'Healer' not in roles:
        suggestions.append("💚 Нет поддержки — команда не восстанавливает здоровье.")
    if 'Mage' not in roles:
        suggestions.append("🔮 Без мага сложно справляться с группами врагов.")
    if not any(u['alive'] for u in units) and defeated:
        first_dead = defeated[0]
        suggestions.append(f"💔 Первым погиб {first_dead['name']} — улучшите его защиту или поставьте танка.")

    return {
        'victory': any(u['alive'] for u in units) and not any(e['alive'] for e in enemies),
        'log': log,
        'survivors': [u['name'] for u in survivors],
        'defeated': [u['name'] for u in defeated],
        'mvp': mvp['name'] if mvp else None,
        'mvp_damage': mvp['damage_dealt'] if mvp else 0,
        'total_turns': turn,
        'suggestions': suggestions[:3]
    }