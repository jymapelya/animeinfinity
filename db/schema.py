-- Таблица игроков
CREATE TABLE IF NOT EXISTS players (
    user_id BIGINT PRIMARY KEY,
    nickname VARCHAR(64) NOT NULL,
    gold BIGINT DEFAULT 0,
    gems INT DEFAULT 0,
    tickets INT DEFAULT 0,
    relic_dust INT DEFAULT 0,
    ascension_points INT DEFAULT 0,
    guild_id INT REFERENCES guilds(id),
    current_world INT DEFAULT 1,
    current_wave INT DEFAULT 1,
    team_power INT DEFAULT 0,
    last_afk_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_daily_claim DATE,
    energy INT DEFAULT 100,
    last_energy_update TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    raid_attempts INT DEFAULT 3,
    next_raid_reset TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    season_pass_level INT DEFAULT 0,
    ascension_level INT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Персонажи игрока
CREATE TABLE IF NOT EXISTS player_characters (
    id SERIAL PRIMARY KEY,
    player_id BIGINT REFERENCES players(user_id) ON DELETE CASCADE,
    base_char_id VARCHAR(32) NOT NULL,
    level INT DEFAULT 1,
    xp INT DEFAULT 0,
    variant VARCHAR(16) DEFAULT 'Normal',
    trait VARCHAR(32),
    destiny VARCHAR(32),
    iv_hp INT CHECK (iv_hp BETWEEN 80 AND 120),
    iv_atk INT CHECK (iv_atk BETWEEN 80 AND 120),
    iv_def INT CHECK (iv_def BETWEEN 80 AND 120),
    iv_spd INT CHECK (iv_spd BETWEEN 80 AND 120),
    iv_crit INT CHECK (iv_crit BETWEEN 80 AND 120),
    awakening_stars INT DEFAULT 0,
    expedition_end_time TIMESTAMP WITH TIME ZONE,
    CONSTRAINT fk_base_character FOREIGN KEY (base_char_id) REFERENCES characters_ref(id) -- не обязательно
);

-- Универсальный инвентарь (реликвии, предметы)
CREATE TABLE IF NOT EXISTS player_inventory (
    id SERIAL PRIMARY KEY,
    player_id BIGINT REFERENCES players(user_id),
    item_type VARCHAR(16) CHECK (item_type IN ('relic','weapon','armor','ring','amulet')),
    item_id VARCHAR(32) NOT NULL,
    quantity INT DEFAULT 1,
    equipped_on_char INT REFERENCES player_characters(id) ON DELETE SET NULL
);

-- Экспедиции
CREATE TABLE IF NOT EXISTS expeditions (
    id SERIAL PRIMARY KEY,
    player_id BIGINT REFERENCES players(user_id),
    char_instance_id INT REFERENCES player_characters(id),
    end_time TIMESTAMP WITH TIME ZONE NOT NULL,
    duration_hours INT NOT NULL,
    claimed BOOLEAN DEFAULT FALSE
);

-- Гильдии
CREATE TABLE IF NOT EXISTS guilds (
    id SERIAL PRIMARY KEY,
    name VARCHAR(64) UNIQUE NOT NULL,
    level INT DEFAULT 1,
    exp BIGINT DEFAULT 0,
    gold_boost INT DEFAULT 0,
    hp_boost INT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS guild_members (
    guild_id INT REFERENCES guilds(id),
    user_id BIGINT REFERENCES players(user_id),
    rank VARCHAR(16) DEFAULT 'member',
    joined_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (guild_id, user_id)
);

-- Прогресс в башне
CREATE TABLE IF NOT EXISTS tower_progress (
    player_id BIGINT REFERENCES players(user_id) PRIMARY KEY,
    highest_floor INT DEFAULT 1,
    current_floor INT DEFAULT 1
);

-- Серверные объявления (лог)
CREATE TABLE IF NOT EXISTS server_announcements (
    id SERIAL PRIMARY KEY,
    message TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS player_relics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL,
    relic_id TEXT NOT NULL,
    quantity INTEGER DEFAULT 1,
    FOREIGN KEY (player_id) REFERENCES players(user_id)
);