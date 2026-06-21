import aiosqlite
from datetime import datetime, timezone, timedelta
from engine.data_loader import data_cache
import random

DB_PATH = "anime_infinity.db"

async def get_db():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    return db

async def init_db():
    """Создаёт таблицы, если их нет."""
    db = await get_db()
    try:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS players (
            user_id INTEGER PRIMARY KEY,
            nickname TEXT NOT NULL,
            gold INTEGER DEFAULT 0,
            gems INTEGER DEFAULT 0,
            tickets INTEGER DEFAULT 0,
            relic_dust INTEGER DEFAULT 0,
            ascension_points INTEGER DEFAULT 0,
            guild_id INTEGER,
            max_world INTEGER DEFAULT 1,
            max_wave INTEGER DEFAULT 1,
            team_power INTEGER DEFAULT 0,
            last_afk_time TEXT DEFAULT (datetime('now')),
            last_daily_claim TEXT,
            energy INTEGER DEFAULT 100,
            last_energy_update TEXT DEFAULT (datetime('now')),
            raid_attempts INTEGER DEFAULT 3,
            next_raid_reset TEXT DEFAULT (datetime('now')),
            season_pass_level INTEGER DEFAULT 0,
            ascension_level INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            pity_legendary INTEGER DEFAULT 0,
            pity_mythic INTEGER DEFAULT 0,
            pity_secret INTEGER DEFAULT 0,
            awakening_cores INTEGER DEFAULT 0,
            active_background_id INTEGER DEFAULT NULL
        );

        CREATE TABLE IF NOT EXISTS player_characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            base_char_id TEXT NOT NULL,
            level INTEGER DEFAULT 1,
            xp INTEGER DEFAULT 0,
            variant TEXT DEFAULT 'Normal',
            trait TEXT,
            destiny TEXT,
            iv_hp INTEGER CHECK(iv_hp BETWEEN 80 AND 120),
            iv_atk INTEGER CHECK(iv_atk BETWEEN 80 AND 120),
            iv_def INTEGER CHECK(iv_def BETWEEN 80 AND 120),
            iv_spd INTEGER CHECK(iv_spd BETWEEN 80 AND 120),
            iv_crit INTEGER CHECK(iv_crit BETWEEN 80 AND 120),
            awakening_stars INTEGER DEFAULT 0,
            expedition_end_time TEXT,
            equipped_relic_id INTEGER DEFAULT NULL,
            copy_number INTEGER DEFAULT 1,
            FOREIGN KEY (player_id) REFERENCES players(user_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS player_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            item_type TEXT CHECK(item_type IN ('relic','weapon','armor','ring','amulet')),
            item_id TEXT NOT NULL,
            quantity INTEGER DEFAULT 1,
            equipped_on_char INTEGER,
            FOREIGN KEY (player_id) REFERENCES players(user_id),
            FOREIGN KEY (equipped_on_char) REFERENCES player_characters(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS expeditions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            char_instance_id INTEGER NOT NULL,
            end_time TEXT NOT NULL,
            duration_hours INTEGER NOT NULL,
            claimed INTEGER DEFAULT 0,
            FOREIGN KEY (player_id) REFERENCES players(user_id),
            FOREIGN KEY (char_instance_id) REFERENCES player_characters(id)
        );

        CREATE TABLE IF NOT EXISTS guilds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            level INTEGER DEFAULT 1,
            exp INTEGER DEFAULT 0,
            gold_boost INTEGER DEFAULT 0,
            hp_boost INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS guild_members (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            rank TEXT DEFAULT 'member',
            joined_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (guild_id, user_id),
            FOREIGN KEY (guild_id) REFERENCES guilds(id),
            FOREIGN KEY (user_id) REFERENCES players(user_id)
        );

        CREATE TABLE IF NOT EXISTS tower_progress (
            player_id INTEGER PRIMARY KEY,
            highest_floor INTEGER DEFAULT 1,
            current_floor INTEGER DEFAULT 1,
            FOREIGN KEY (player_id) REFERENCES players(user_id)
        );

        CREATE TABLE IF NOT EXISTS server_announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS player_teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            team_slot INTEGER DEFAULT 1,
            char_instance_id INTEGER NOT NULL,
            position INTEGER DEFAULT 0,
            FOREIGN KEY (player_id) REFERENCES players(user_id),
            FOREIGN KEY (char_instance_id) REFERENCES player_characters(id)
        );

        CREATE TABLE IF NOT EXISTS player_relics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            relic_id TEXT NOT NULL,
            quantity INTEGER DEFAULT 1,
            equipped INTEGER DEFAULT 0,
            FOREIGN KEY (player_id) REFERENCES players(user_id)
        );

        CREATE TABLE IF NOT EXISTS player_backgrounds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            background_id TEXT NOT NULL,
            quantity INTEGER DEFAULT 1,
            equipped INTEGER DEFAULT 0,
            FOREIGN KEY (player_id) REFERENCES players(user_id)
        );

        CREATE TABLE IF NOT EXISTS player_hero_awakening (
            player_id INTEGER NOT NULL,
            base_char_id TEXT NOT NULL,
            stars INTEGER DEFAULT 0,
            PRIMARY KEY (player_id, base_char_id),
            FOREIGN KEY (player_id) REFERENCES players(user_id)
        );

        CREATE TABLE IF NOT EXISTS player_auto_dismantle (
            player_id INTEGER PRIMARY KEY,
            enabled INTEGER DEFAULT 0,
            dismantle_rare INTEGER DEFAULT 0,
            dismantle_epic INTEGER DEFAULT 0,
            dismantle_legendary INTEGER DEFAULT 0,
            keep_if_trait INTEGER DEFAULT 0,
            keep_if_destiny INTEGER DEFAULT 0,
            min_iv_atk INTEGER DEFAULT 0,
            min_iv_hp INTEGER DEFAULT 0,
            min_iv_def INTEGER DEFAULT 0,
            min_iv_spd INTEGER DEFAULT 0,
            min_iv_crit INTEGER DEFAULT 0,
            keep_factions TEXT DEFAULT '',
            keep_roles TEXT DEFAULT '',
            FOREIGN KEY (player_id) REFERENCES players(user_id)
        );

        CREATE TABLE IF NOT EXISTS player_shared_chats (
            player_id INTEGER PRIMARY KEY,
            chat_id INTEGER NOT NULL,
            FOREIGN KEY (player_id) REFERENCES players(user_id)
        );

        """)
        await db.commit()
    finally:
        await db.close()

# ---------- Игроки ----------
async def create_player(user_id: int, nickname: str):
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO players (user_id, nickname, max_world, max_wave) VALUES (?, ?, 1, 1)",
            (user_id, nickname)
        )
        await db.commit()
        return True
    except:
        return False
    finally:
        await db.close()

async def get_player(user_id: int):
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM players WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()

async def get_team_characters(user_id: int, team_slot: int = 1):
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT pc.* FROM player_characters pc
            JOIN player_teams pt ON pc.id = pt.char_instance_id
            WHERE pt.player_id = ? AND pt.team_slot = ?""",
            (user_id, team_slot)
        )
        rows = await cursor.fetchall()
        if not rows:
            cursor = await db.execute(
                "SELECT * FROM player_characters WHERE player_id = ? LIMIT 5",
                (user_id,)
            )
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()

async def update_player(user_id: int, **kwargs):
    if not kwargs:
        return
    set_parts = []
    values = []
    for key, value in kwargs.items():
        set_parts.append(f"{key} = ?")
        values.append(value)
    values.append(user_id)
    query = f"UPDATE players SET {', '.join(set_parts)} WHERE user_id = ?"
    db = await get_db()
    try:
        await db.execute(query, values)
        await db.commit()
    finally:
        await db.close()

# ---------- Персонажи ----------
async def get_next_copy_number(player_id: int, base_char_id: str) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT MAX(copy_number) as max_num FROM player_characters WHERE player_id=? AND base_char_id=?",
            (player_id, base_char_id)
        )
        row = await cursor.fetchone()
        return (row['max_num'] or 0) + 1
    finally:
        await db.close()

async def add_character(user_id: int, base_char_id: str, variant: str = 'Normal',
                        trait: str = None, destiny: str = None,
                        iv_hp: int = 100, iv_atk: int = 100, iv_def: int = 100,
                        iv_spd: int = 100, iv_crit: int = 100):
    db = await get_db()
    try:
        copy_number = await get_next_copy_number(user_id, base_char_id)
        await db.execute(
            """INSERT INTO player_characters 
            (player_id, base_char_id, variant, trait, destiny, 
            iv_hp, iv_atk, iv_def, iv_spd, iv_crit, copy_number)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, base_char_id, variant, trait, destiny,
            iv_hp, iv_atk, iv_def, iv_spd, iv_crit, copy_number)
        )
        await db.commit()
    finally:
        await db.close()

# ---------- Инвентарь ----------
async def add_inventory_item(user_id: int, item_type: str, item_id: str, quantity: int = 1):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, quantity FROM player_inventory WHERE player_id=? AND item_type=? AND item_id=?",
            (user_id, item_type, item_id)
        )
        existing = await cursor.fetchone()
        if existing:
            await db.execute(
                "UPDATE player_inventory SET quantity = quantity + ? WHERE id = ?",
                (quantity, existing['id'])
            )
        else:
            await db.execute(
                "INSERT INTO player_inventory (player_id, item_type, item_id, quantity) VALUES (?,?,?,?)",
                (user_id, item_type, item_id, quantity)
            )
        await db.commit()
    finally:
        await db.close()

# ---------- Пити ----------
async def get_pity_counter(user_id: int):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT pity_legendary, pity_mythic, pity_secret FROM players WHERE user_id=?",
            (user_id,)
        )
        row = await cursor.fetchone()
        if row:
            return row['pity_legendary'], row['pity_mythic'], row['pity_secret']
        return 0, 0, 0
    finally:
        await db.close()

async def update_pity_counter(user_id: int, leg: int, myth: int, sec: int):
    db = await get_db()
    try:
        await db.execute(
            "UPDATE players SET pity_legendary=?, pity_mythic=?, pity_secret=? WHERE user_id=?",
            (leg, myth, sec, user_id)
        )
        await db.commit()
    finally:
        await db.close()

# ---------- Стартовая валюта ----------
async def set_player_currency(user_id: int, gems: int, tickets: int):
    db = await get_db()
    try:
        await db.execute(
            "UPDATE players SET gems = ?, tickets = ? WHERE user_id = ?",
            (gems, tickets, user_id)
        )
        await db.commit()
    finally:
        await db.close()

# ---------- Управление командой ----------
async def set_team_slot(user_id: int, slot: int, char_instance_id: int, team_slot: int = 1):
    db = await get_db()
    try:
        await db.execute(
            "DELETE FROM player_teams WHERE player_id=? AND team_slot=? AND position=?",
            (user_id, team_slot, slot)
        )
        await db.execute(
            "INSERT INTO player_teams (player_id, team_slot, char_instance_id, position) VALUES (?,?,?,?)",
            (user_id, team_slot, char_instance_id, slot)
        )
        await db.commit()
    finally:
        await db.close()

async def clear_team_slot(user_id: int, slot: int, team_slot: int = 1):
    db = await get_db()
    try:
        await db.execute(
            "DELETE FROM player_teams WHERE player_id=? AND team_slot=? AND position=?",
            (user_id, team_slot, slot)
        )
        await db.commit()
    finally:
        await db.close()

async def get_team_ids(user_id: int, team_slot: int = 1):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT position, char_instance_id FROM player_teams WHERE player_id=? AND team_slot=?",
            (user_id, team_slot)
        )
        rows = await cursor.fetchall()
        return {row['position']: row['char_instance_id'] for row in rows}
    finally:
        await db.close()

# ---------- Реликвии ----------
async def add_relic(player_id: int, relic_id: str, quantity: int = 1):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, quantity FROM player_relics WHERE player_id=? AND relic_id=?",
            (player_id, relic_id)
        )
        existing = await cursor.fetchone()
        if existing:
            await db.execute(
                "UPDATE player_relics SET quantity = quantity + ? WHERE id = ?",
                (quantity, existing['id'])
            )
        else:
            await db.execute(
                "INSERT INTO player_relics (player_id, relic_id, quantity) VALUES (?,?,?)",
                (player_id, relic_id, quantity)
            )
        await db.commit()
    finally:
        await db.close()

async def get_player_relics(player_id: int):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT relic_id, quantity FROM player_relics WHERE player_id=?",
            (player_id,)
        )
        rows = await cursor.fetchall()
        return {row['relic_id']: row['quantity'] for row in rows}
    finally:
        await db.close()

# ---------- Экспедиции ----------
async def start_expedition(player_id: int, char_instance_id: int, duration_hours: int):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id FROM expeditions WHERE char_instance_id=? AND claimed=0",
            (char_instance_id,)
        )
        if await cursor.fetchone():
            return False
        end_time = datetime.now(timezone.utc) + timedelta(hours=duration_hours)
        await db.execute(
            "INSERT INTO expeditions (player_id, char_instance_id, end_time, duration_hours) VALUES (?,?,?,?)",
            (player_id, char_instance_id, end_time.isoformat(), duration_hours)
        )
        await db.commit()
        return True
    finally:
        await db.close()

async def get_active_expeditions(player_id: int):
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT e.id, e.char_instance_id, e.end_time, e.duration_hours,
                      pc.base_char_id, pc.variant, pc.iv_hp, pc.iv_atk, pc.iv_def, pc.iv_spd, pc.iv_crit,
                      pc.copy_number
               FROM expeditions e
               JOIN player_characters pc ON e.char_instance_id = pc.id
               WHERE e.player_id=? AND e.claimed=0
               ORDER BY e.end_time""",
            (player_id,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()

async def collect_expedition(expedition_id: int, player_id: int):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM expeditions WHERE id=? AND player_id=? AND claimed=0",
            (expedition_id, player_id)
        )
        exp = await cursor.fetchone()
        if not exp:
            return None
        end_time = datetime.fromisoformat(exp['end_time'])
        if datetime.now(timezone.utc) < end_time:
            return None

        await db.execute("UPDATE expeditions SET claimed=1 WHERE id=?", (expedition_id,))
        await db.commit()

        char_cursor = await db.execute(
            "SELECT base_char_id FROM player_characters WHERE id=?", (exp['char_instance_id'],)
        )
        char_row = await char_cursor.fetchone()
        if not char_row:
            return None
        base_char = data_cache.characters.get(char_row['base_char_id'], {})
        rarity = base_char.get('rarity', 'Rare')
        rarity_mult = {'Rare':1, 'Epic':1.5, 'Legendary':2, 'Mythic':3, 'Secret':5}.get(rarity, 1)
        hours = exp['duration_hours']

        rewards = {
            'gold': int(100 * hours * rarity_mult * random.uniform(0.8, 1.2)),
            'gems': int(5 * hours * rarity_mult * random.uniform(0.5, 1.5)),
            'relic_dust': int(20 * hours * rarity_mult * random.uniform(0.5, 1.5)),
            'items': [],
            'tickets': 0,
            'awakening_cores': 0
        }
        if random.random() < 0.3 * rarity_mult:
            items_list = list(data_cache.items.values())
            if items_list:
                item = random.choice(items_list)
                await add_inventory_item(player_id, item['type'], item['id'])
                rewards['items'].append(item['name'])
        if random.random() < 0.2 * rarity_mult:
            rewards['tickets'] = 1
        if random.random() < 0.3 * rarity_mult:
            cores_earned = random.randint(1, 3)
            rewards['awakening_cores'] = cores_earned

        player = await get_player(player_id)
        if player:
            await update_player(player_id,
                                gold=player['gold'] + rewards['gold'],
                                relic_dust=player['relic_dust'] + rewards['relic_dust'],
                                gems=player['gems'] + rewards['gems'],
                                tickets=player['tickets'] + rewards['tickets'],
                                awakening_cores=player['awakening_cores'] + rewards['awakening_cores'])
        return rewards
    finally:
        await db.close()

# ---------- Экипировка реликвий ----------
async def equip_relic(player_id: int, char_instance_id: int, relic_instance_id: int):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id FROM player_relics WHERE id=? AND player_id=? AND equipped=0",
            (relic_instance_id, player_id)
        )
        if not await cursor.fetchone():
            return False
        await db.execute(
            "UPDATE player_relics SET equipped=0 WHERE id=(SELECT equipped_relic_id FROM player_characters WHERE id=?)",
            (char_instance_id,)
        )
        await db.execute(
            "UPDATE player_characters SET equipped_relic_id=? WHERE id=? AND player_id=?",
            (relic_instance_id, char_instance_id, player_id)
        )
        await db.execute("UPDATE player_relics SET equipped=1 WHERE id=?", (relic_instance_id,))
        await db.commit()
        return True
    finally:
        await db.close()

async def unequip_relic(player_id: int, char_instance_id: int):
    db = await get_db()
    try:
        await db.execute(
            "UPDATE player_relics SET equipped=0 WHERE id=(SELECT equipped_relic_id FROM player_characters WHERE id=?)",
            (char_instance_id,)
        )
        await db.execute(
            "UPDATE player_characters SET equipped_relic_id=NULL WHERE id=? AND player_id=?",
            (char_instance_id, player_id)
        )
        await db.commit()
        return True
    finally:
        await db.close()

async def get_equipped_relic(char_instance_id: int):
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT pr.id, pr.relic_id
               FROM player_relics pr
               JOIN player_characters pc ON pc.equipped_relic_id = pr.id
               WHERE pc.id=?""",
            (char_instance_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()

# ---------- Фоны профиля ----------
async def add_background(player_id: int, background_id: str, quantity: int = 1):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, quantity FROM player_backgrounds WHERE player_id=? AND background_id=?",
            (player_id, background_id)
        )
        existing = await cursor.fetchone()
        if existing:
            await db.execute(
                "UPDATE player_backgrounds SET quantity = quantity + ? WHERE id = ?",
                (quantity, existing['id'])
            )
        else:
            await db.execute(
                "INSERT INTO player_backgrounds (player_id, background_id, quantity) VALUES (?,?,?)",
                (player_id, background_id, quantity)
            )
        await db.commit()
    finally:
        await db.close()

async def get_player_backgrounds(player_id: int):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, background_id, quantity, equipped FROM player_backgrounds WHERE player_id=?",
            (player_id,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()

async def set_active_background(player_id: int, background_instance_id: int):
    db = await get_db()
    try:
        await db.execute("UPDATE player_backgrounds SET equipped=0 WHERE player_id=?", (player_id,))
        await db.execute("UPDATE player_backgrounds SET equipped=1 WHERE id=? AND player_id=?", 
                        (background_instance_id, player_id))
        cursor = await db.execute("SELECT background_id FROM player_backgrounds WHERE id=?", (background_instance_id,))
        row = await cursor.fetchone()
        if row:
            await db.execute("UPDATE players SET active_background_id=? WHERE user_id=?", 
                            (row['background_id'], player_id))
        await db.commit()
    finally:
        await db.close()

# ---------- Awakening Stars ----------
async def get_awakening_level(player_id: int, base_char_id: str) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT stars FROM player_hero_awakening WHERE player_id=? AND base_char_id=?",
            (player_id, base_char_id)
        )
        row = await cursor.fetchone()
        return row['stars'] if row else 0
    finally:
        await db.close()

async def awaken_hero(player_id: int, base_char_id: str):
    db = await get_db()
    try:
        cur = await get_awakening_level(player_id, base_char_id)
        if cur >= 5:
            return None, "Максимальный уровень пробуждения (5★)."

        costs = {0: (5000, 1), 1: (15000, 2), 2: (30000, 3), 3: (50000, 5), 4: (100000, 8)}
        gold_cost, core_cost = costs[cur]

        player_cursor = await db.execute("SELECT gold, awakening_cores FROM players WHERE user_id=?", (player_id,))
        player = await player_cursor.fetchone()
        if not player or player['gold'] < gold_cost or player['awakening_cores'] < core_cost:
            return None, f"Недостаточно ресурсов (нужно {gold_cost}💰 и {core_cost}🔮)."

        count_cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM player_characters WHERE player_id=? AND base_char_id=?",
            (player_id, base_char_id)
        )
        count_row = await count_cursor.fetchone()
        if not count_row or count_row['cnt'] < 2:
            return None, "Нужен дубликат этого героя (минимум 2 копии)."

        char_cursor = await db.execute(
            "SELECT id FROM player_characters WHERE player_id=? AND base_char_id=? LIMIT 1",
            (player_id, base_char_id)
        )
        char_row = await char_cursor.fetchone()
        if char_row:
            await db.execute("DELETE FROM player_characters WHERE id=?", (char_row['id'],))

        await db.execute(
            "UPDATE players SET gold = gold - ?, awakening_cores = awakening_cores - ? WHERE user_id=?",
            (gold_cost, core_cost, player_id)
        )

        new_stars = cur + 1
        await db.execute(
            "INSERT INTO player_hero_awakening (player_id, base_char_id, stars) VALUES (?,?,?) "
            "ON CONFLICT(player_id, base_char_id) DO UPDATE SET stars = ?",
            (player_id, base_char_id, new_stars, new_stars)
        )
        await db.commit()
        return new_stars, None
    finally:
        await db.close()

async def get_awakening_cost(stars: int):
    costs = {0: (5000, 1), 1: (15000, 2), 2: (30000, 3), 3: (50000, 5), 4: (100000, 8)}
    return costs.get(stars, (0, 0))

# ---------- Инвентарь реликвий для экипировки ----------
async def get_unequipped_relics(player_id: int):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, relic_id, quantity FROM player_relics WHERE player_id=? AND equipped=0 ORDER BY id",
            (player_id,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()

async def get_relic_count_by_id(player_id: int, relic_id: str) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT SUM(quantity) as cnt FROM player_relics WHERE player_id=? AND relic_id=?",
            (player_id, relic_id)
        )
        row = await cursor.fetchone()
        return row['cnt'] if row else 0
    finally:
        await db.close()

async def calculate_team_power(user_id: int):
    team = await get_team_characters(user_id)
    if not team:
        await update_player(user_id, team_power=0)
        return 0

    total_power = 0
    for hero in team:
        base = data_cache.characters.get(hero['base_char_id'], {})
        stars = await get_awakening_level(user_id, hero['base_char_id'])
        star_mult = 1 + stars * 0.05

        hp = round(base.get('hp', 100) * (hero.get('iv_hp', 100) / 100) * star_mult)
        atk = round(base.get('atk', 50) * (hero.get('iv_atk', 100) / 100) * star_mult)
        def_ = round(base.get('def', 30) * (hero.get('iv_def', 100) / 100) * star_mult)
        spd = round(base.get('spd', 80) * (hero.get('iv_spd', 100) / 100) * star_mult)
        crit = round(base.get('crit', 5) * (hero.get('iv_crit', 100) / 100))

        relic_data = await get_equipped_relic(hero['id'])
        if relic_data:
            relic = data_cache.relics.get(relic_data['relic_id'])
            if relic:
                effect = relic['effect']
                value = relic['value']
                if effect == 'hp': hp *= (1 + value / 100)
                elif effect == 'atk': atk *= (1 + value / 100)
                elif effect == 'def': def_ *= (1 + value / 100)
                elif effect == 'spd': spd *= (1 + value / 100)
                elif effect == 'crit': crit += value

        hero_power = round(hp / 10 + atk + def_ + spd + crit * 2)
        total_power += hero_power

    await update_player(user_id, team_power=total_power)
    return total_power

async def get_auto_dismantle(player_id: int):
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM player_auto_dismantle WHERE player_id=?", (player_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()

async def update_auto_dismantle(player_id: int, **kwargs):
    if not kwargs:
        return
    db = await get_db()
    try:
        # Значения по умолчанию для IV (80)
        defaults = {
            'min_iv_atk': 80,
            'min_iv_hp': 80,
            'min_iv_def': 80,
            'min_iv_spd': 80,
            'min_iv_crit': 80,
        }
        for key, default_val in defaults.items():
            if key not in kwargs:
                kwargs[key] = default_val

        cursor = await db.execute("SELECT player_id FROM player_auto_dismantle WHERE player_id=?", (player_id,))
        exists = await cursor.fetchone()
        if exists:
            set_parts = []
            values = []
            for key, value in kwargs.items():
                set_parts.append(f"{key}=?")
                values.append(value)
            values.append(player_id)
            query = f"UPDATE player_auto_dismantle SET {', '.join(set_parts)} WHERE player_id=?"
            await db.execute(query, values)
        else:
            columns = ', '.join(kwargs.keys())
            placeholders = ', '.join(['?'] * len(kwargs))
            values = list(kwargs.values())
            query = f"INSERT INTO player_auto_dismantle (player_id, {columns}) VALUES (?, {placeholders})"
            await db.execute(query, [player_id] + values)
        await db.commit()
    finally:
        await db.close()

async def save_shared_chat(player_id: int, chat_id: int):
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO player_shared_chats (player_id, chat_id) VALUES (?,?) ON CONFLICT(player_id) DO UPDATE SET chat_id=?",
            (player_id, chat_id, chat_id))
        await db.commit()
    finally:
        await db.close()

async def get_shared_chat(player_id: int):
    db = await get_db()
    try:
        cursor = await db.execute("SELECT chat_id FROM player_shared_chats WHERE player_id=?", (player_id,))
        row = await cursor.fetchone()
        return row['chat_id'] if row else None
    finally:
        await db.close()