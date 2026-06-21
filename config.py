import os
from dotenv import load_dotenv

load_dotenv()  # <-- обязательно!

BOT_TOKEN = os.getenv("BOT_TOKEN")
admin_str = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(uid) for uid in admin_str.split(",") if uid.strip().isdigit()]

# Игровые константы
START_GOLD = 0
START_GEMS = 100000
START_TICKETS = 10
MAX_AFK_HOURS = 12
PREMIUM_AFK_HOURS = 24
WAVE_TIME_SECONDS = 15
GACHA_COST = 300
GACHA_10_COST = 2700
PITY_SOFT_START = 40
PITY_LEGENDARY = 50
PITY_MYTHIC = 150
PITY_SECRET = 500