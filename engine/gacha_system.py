import random
from engine.data_loader import data_cache

RARITY_WEIGHTS = {
    'Rare': 70,
    'Epic': 20,
    'Legendary': 8,
    'Mythic': 1.8,
    'Secret': 0.2
}
VARIANTS = ['Normal', 'Shiny', 'Golden', 'Prismatic', 'Celestial']
VARIANT_WEIGHTS = [100, 20, 5, 1, 0.2]  # примерные шансы

def pull_character(pity_counter_legendary, pity_counter_mythic, pity_counter_secret):
    """
    Возвращает словарь с данными о новом персонаже (base_char_id, rarity, variant, trait, destiny, IVs)
    """
    # Определяем редкость с учётом пити
    rarity = roll_rarity(pity_counter_legendary, pity_counter_mythic, pity_counter_secret)
    # Выбираем случайного персонажа нужной редкости
    candidates = [c for c in data_cache.characters.values() if c['rarity'] == rarity]
    if not candidates:
        candidates = list(data_cache.characters.values())
    base_char = random.choice(candidates)
    # Вариант
    variant = random.choices(VARIANTS, weights=VARIANT_WEIGHTS, k=1)[0]
    # Трейт (если не Normal, может быть всегда)
    trait_id = random.choice(list(data_cache.traits.keys())) if random.random() < 0.5 else None
    destiny_id = random.choice(list(data_cache.destinies.keys())) if random.random() < 0.05 else None  # очень редко
    # IV
    iv = {
        'hp': random.randint(80, 120),
        'atk': random.randint(80, 120),
        'def': random.randint(80, 120),
        'spd': random.randint(80, 120),
        'crit': random.randint(80, 120)
    }
    return {
        'base_char_id': base_char['id'],
        'rarity': rarity,
        'variant': variant,
        'trait': trait_id,
        'destiny': destiny_id,
        'iv_hp': iv['hp'],
        'iv_atk': iv['atk'],
        'iv_def': iv['def'],
        'iv_spd': iv['spd'],
        'iv_crit': iv['crit']
    }

def roll_rarity(leg_counter, myth_counter, sec_counter):
    weights = RARITY_WEIGHTS.copy()
    # Soft pity с 40
    if leg_counter >= 40:
        extra = (leg_counter - 39) * 2
        weights['Mythic'] += extra
        # пересчёт остальных
    total = sum(weights.values())
    r = random.uniform(0, total)
    cumulative = 0
    for rarity, w in weights.items():
        cumulative += w
        if r <= cumulative:
            return rarity
    return 'Rare'

def pull_event_character():
    event = data_cache.event_banner
    if not event:
        return None

    rates = event.get('rates', {})
    rarities = list(rates.keys())
    weights = list(rates.values())

    rarity = random.choices(rarities, weights=weights, k=1)[0]

    # Если для этой редкости есть собственный пул (как Secret, Mythic)
    pools = event.get('pools', {})
    if rarity in pools and pools[rarity]:
        char_id = random.choice(pools[rarity])
        base_char = data_cache.characters.get(char_id)
    else:
        # Берем из общего пула персонажей данной редкости
        candidates = [c for c in data_cache.characters.values() if c.get('rarity') == rarity]
        if not candidates:
            return None
        base_char = random.choice(candidates)

    if not base_char:
        return None

    variant = random.choices(
        ['Normal', 'Shiny', 'Golden', 'Prismatic', 'Celestial'],
        weights=[100, 20, 5, 1, 0.2], k=1
    )[0]
    trait_id = random.choice(list(data_cache.traits.keys())) if random.random() < 0.5 else None
    destiny_id = random.choice(list(data_cache.destinies.keys())) if random.random() < 0.05 else None
    iv = {
        'hp': random.randint(80, 120),
        'atk': random.randint(80, 120),
        'def': random.randint(80, 120),
        'spd': random.randint(80, 120),
        'crit': random.randint(80, 120)
    }

    return {
        'base_char_id': base_char['id'],
        'rarity': base_char.get('rarity', rarity),
        'variant': variant,
        'trait': trait_id,
        'destiny': destiny_id,
        'iv_hp': iv['hp'],
        'iv_atk': iv['atk'],
        'iv_def': iv['def'],
        'iv_spd': iv['spd'],
        'iv_crit': iv['crit']
    }

def pull_event_reward():
    """Тянет награду из ивентового баннера: персонаж или фон."""
    event = data_cache.event_banner
    if not event:
        return None

    # Шанс на фон
    if 'background_rate' in event and random.random() < event['background_rate'] / 100:
        bg_pool = event.get('background_pool', [])
        if bg_pool:
            bg_id = random.choice(bg_pool)
            return {'type': 'background', 'background_id': bg_id}

    # Иначе персонаж
    char = pull_event_character()
    if char:
        return {'type': 'character', 'data': char}
    return None