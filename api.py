from aiohttp import web
from db.models import get_db, get_player
from engine.data_loader import data_cache

async def collection_handler(request):
    user_id = request.query.get('user_id')
    if not user_id:
        return web.json_response({'error': 'no user_id'}, status=400)
    user_id = int(user_id)

    # Получаем всех персонажей игрока из БД
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT base_char_id, variant, trait, destiny, iv_hp, iv_atk, iv_def, iv_spd, iv_crit, COUNT(*) as cnt "
            "FROM player_characters WHERE player_id = ? "
            "GROUP BY base_char_id, variant, trait, destiny, iv_hp, iv_atk, iv_def, iv_spd, iv_crit",
            (user_id,)
        )
        rows = await cursor.fetchall()
    finally:
        await db.close()

    # Формируем карточки
    cards = []
    owned_set = set()
    for row in rows:
        base = data_cache.characters.get(row['base_char_id'])
        if not base:
            continue
        owned_set.add(row['base_char_id'])
        # Эмодзи редкости и варианта
        rarity_emoji = {'Rare':'🔵','Epic':'🟣','Legendary':'🟡','Mythic':'🔴','Secret':'🌈'}.get(base['rarity'],'')
        variant_emoji = {'Normal':'','Shiny':'✨','Golden':'🌟','Prismatic':'💫','Celestial':'☄️'}.get(row['variant'],'')
        cards.append({
            'name': base['name'],
            'rarity': base['rarity'],
            'rarity_emoji': rarity_emoji,
            'faction': base['faction'],
            'role': base['role'],
            'image_url': base.get('image_url',''),
            'variant': row['variant'],
            'variant_emoji': variant_emoji,
            'trait': row['trait'] or '',
            'destiny': row['destiny'] or '',
            'iv_hp': row['iv_hp'],
            'iv_atk': row['iv_atk'],
            'iv_def': row['iv_def'],
            'iv_spd': row['iv_spd'],
            'iv_crit': row['iv_crit'],
            'obtained_count': row['cnt']
        })

    total_chars = len(data_cache.characters)
    owned = len(owned_set)
    return web.json_response({
        'cards': cards,
        'owned': owned,
        'total': total_chars
    })