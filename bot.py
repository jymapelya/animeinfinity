import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN
from db.models import init_db
from engine.data_loader import data_cache

from handlers.start import router as start_router
from handlers.menu import router as menu_router
from handlers.afk import router as afk_router
from handlers.gacha import router as gacha_router
from handlers.battle import router as battle_router
from handlers.admin import router as admin_router
from handlers.profile import router as profile_router
from handlers.collection import router as collection_router
from handlers.team import router as team_router
from handlers.relics import router as relics_router
from handlers.expeditions import router as expeditions_router
from handlers.backgrounds import router as backgrounds_router
from handlers.reply_menu import router as reply_router
from handlers.wiki import router as wiki_router
from handlers.tower import router as tower_router
from handlers.auto_dismantle import router as auto_dismantle_router

async def main():
    logging.basicConfig(level=logging.INFO)
    
    await init_db()
    data_cache.load_all()
    
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    
    dp.include_router(start_router)
    dp.include_router(menu_router)
    dp.include_router(afk_router)
    dp.include_router(gacha_router)
    dp.include_router(battle_router)
    dp.include_router(admin_router)
    dp.include_router(profile_router)
    dp.include_router(collection_router)
    dp.include_router(team_router)
    dp.include_router(relics_router)
    dp.include_router(expeditions_router)
    dp.include_router(backgrounds_router)
    dp.include_router(reply_router)
    dp.include_router(wiki_router)
    dp.include_router(tower_router)
    dp.include_router(auto_dismantle_router)
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())