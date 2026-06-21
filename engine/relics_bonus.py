from db.models import get_player_relics
from engine.data_loader import data_cache
from engine.collection_bonuses import get_collection_bonuses

async def get_relic_bonuses(player_id: int):
    bonuses = {"hp": 0, "atk": 0, "def": 0, "spd": 0, "crit": 0, "gold": 0}
    relics_data = await get_player_relics(player_id)
    for relic_id, count in relics_data.items():
        relic = data_cache.relics.get(relic_id)
        if relic:
            bonuses[relic['effect']] += relic['value'] * count
    return bonuses

async def get_total_account_bonuses(player_id: int):
    """Суммирует бонусы реликвий и коллекции."""
    relic_bonuses = await get_relic_bonuses(player_id)
    collection_bonuses, _ = await get_collection_bonuses(player_id)
    total = {}
    for key in set(list(relic_bonuses.keys()) + list(collection_bonuses.keys())):
        total[key] = relic_bonuses.get(key, 0) + collection_bonuses.get(key, 0)
    return total