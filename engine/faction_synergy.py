from engine.data_loader import data_cache

def calculate_faction_synergy(team_chars):
    """Принимает список персонажей, возвращает множители синергии."""
    factions = []
    for pc in team_chars:
        base = data_cache.characters.get(pc['base_char_id'])
        if base:
            factions.append(base['faction'])

    # Считаем, сколько раз встречается каждая фракция
    faction_counts = {}
    for f in factions:
        faction_counts[f] = faction_counts.get(f, 0) + 1

    # Максимальное совпадение
    max_same = max(faction_counts.values()) if faction_counts else 0
    multipliers = {2: 0.05, 3: 0.15, 4: 0.25, 5: 0.40}

    bonus = multipliers.get(max_same, 0) if max_same >= 2 else 0
    return bonus, faction_counts