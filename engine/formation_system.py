SLOT_EFFECTS = {
    0: {"name": "Авангард", "taunt_bonus": 0.3, "hp_bonus": 0.25, "desc": "+30% шанс быть атакованным, +25% HP"},
    1: {"name": "Фланг", "damage_bonus": 0.15, "desc": "+15% к урону"},
    2: {"name": "Центр", "heal_bonus": 0.2, "desc": "+20% к лечению и щитам"},
    3: {"name": "Тыл", "taunt_reduction": 0.3, "desc": "-30% шанс быть атакованным"},
    4: {"name": "Резерв", "all_stats": 0.1, "desc": "+10% ко всем статам"},
}

def get_slot_effect(slot_index: int):
    """Возвращает эффект слота по индексу (0-4)."""
    return SLOT_EFFECTS.get(slot_index, {})

def apply_slot_effects(units, team_ids):
    """
    Применяет эффекты слотов к юнитам.
    team_ids: словарь {позиция_в_команде: char_instance_id}
    """
    id_to_position = {}
    for pos, char_id in team_ids.items():
        id_to_position[char_id] = pos

    for u in units:
        pos = id_to_position.get(u.get('char_id'))
        if pos is None:
            continue
        effect = get_slot_effect(pos)
        if not effect:
            continue
        if 'taunt_bonus' in effect:
            u['taunt_chance'] = 1.0 + effect['taunt_bonus']
        if 'taunt_reduction' in effect:
            u['taunt_chance'] = 1.0 - effect['taunt_reduction']
        if 'damage_bonus' in effect:
            u['atk'] = round(u['atk'] * (1 + effect['damage_bonus']))
        if 'heal_bonus' in effect:
            u['heal_bonus'] = effect['heal_bonus']
        if 'hp_bonus' in effect:
            u['hp'] = round(u['hp'] * (1 + effect['hp_bonus']))
            u['max_hp'] = u['hp']
        if 'all_stats' in effect:
            u['hp'] = round(u['hp'] * (1 + effect['all_stats']))
            u['max_hp'] = u['hp']
            u['atk'] = round(u['atk'] * (1 + effect['all_stats']))
            u['def'] = round(u['def'] * (1 + effect['all_stats']))
            u['spd'] = round(u['spd'] * (1 + effect['all_stats']))
        # Инициализируем taunt_chance для всех, у кого нет явного
        if 'taunt_chance' not in u:
            u['taunt_chance'] = 1.0