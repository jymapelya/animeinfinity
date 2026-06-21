from db.models import get_db

async def get_collection_bonuses(player_id: int):
    """Возвращает бонусы от количества уникальных собранных героев."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT COUNT(DISTINCT base_char_id) as unique_chars FROM player_characters WHERE player_id=?",
            (player_id,)
        )
        row = await cursor.fetchone()
        unique = row['unique_chars'] if row else 0
    finally:
        await db.close()

    bonuses = {"hp": 0, "atk": 0, "crit": 0}
    if unique >= 10:
        bonuses["hp"] += 1
    if unique >= 25:
        bonuses["hp"] += 2
    if unique >= 50:
        bonuses["hp"] += 3
    if unique >= 10:
        bonuses["atk"] += 1
    if unique >= 25:
        bonuses["atk"] += 2
    if unique >= 50:
        bonuses["atk"] += 3
    if unique >= 10:
        bonuses["crit"] += 0.5
    if unique >= 25:
        bonuses["crit"] += 1
    if unique >= 50:
        bonuses["crit"] += 2

    return bonuses, unique