from aiogram import Router, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from db.models import get_player, get_db
from engine.data_loader import data_cache
from handlers.utils import edit_or_answer

router = Router()

@router.callback_query(lambda c: c.data == "profile")
async def profile(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    player = await get_player(user_id)
    if not player:
        await callback.answer("Профиль не найден.")
        return

    # Статистика
    db = await get_db()
    try:
        hero_cursor = await db.execute("SELECT COUNT(*) as cnt FROM player_characters WHERE player_id=?", (user_id,))
        hero_count = (await hero_cursor.fetchone())['cnt']
        relic_cursor = await db.execute("SELECT COUNT(*) as cnt FROM player_relics WHERE player_id=?", (user_id,))
        relic_count = (await relic_cursor.fetchone())['cnt']
        bg_cursor = await db.execute("SELECT COUNT(DISTINCT background_id) as cnt FROM player_backgrounds WHERE player_id=?", (user_id,))
        bg_count = (await bg_cursor.fetchone())['cnt']
    finally:
        await db.close()

    # Стилизованный ник
    nickname = f"⭐ {callback.from_user.full_name}"

    # Кликабельный ID
    user_link = f"<a href='tg://user?id={user_id}'>{user_id}</a>"

    text = (
        f"👤 <b>Профиль {nickname}</b>\n"
        f"🆔 ID: {user_link}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🌍 Кампания: Мир {player.get('max_world',1)}-{player.get('max_wave',1)}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"💰 Gold: {player.get('gold',0):,}\n"
        f"💎 Gems: {player.get('gems',0):,}\n"
        f"🎫 Tickets: {player.get('tickets',0):,}\n"
        f"💨 Relic Dust: {player.get('relic_dust',0):,}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"👥 Героев: {hero_count}\n"
        f"📦 Реликвий: {relic_count}\n"
        f"🖼 Фонов: {bg_count}\n"
        f"🏆 Ascension: {player.get('ascension_level',0)}\n"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="🖼 Мои фоны", callback_data="backgrounds")
    builder.button(text="🔙 Назад", callback_data="menu")

    # Если есть активный фон — отправляем медиа
    active_bg_id = player.get('active_background_id')
    if active_bg_id:
        bg = data_cache.backgrounds.get(active_bg_id)
        if bg and bg.get('media_url'):
            try:
                if bg['media_type'] == 'video':
                    await callback.message.answer_video(
                        video=bg['media_url'],
                        caption=text,
                        reply_markup=builder.as_markup(),
                        parse_mode="HTML"
                    )
                else:
                    await callback.message.answer_photo(
                        photo=bg['media_url'],
                        caption=text,
                        reply_markup=builder.as_markup(),
                        parse_mode="HTML"
                    )
                # Удаляем предыдущее сообщение (если было)
                try:
                    await callback.message.delete()
                except:
                    pass
                await callback.answer()
                return
            except:
                pass  # fallback к тексту

    await edit_or_answer(callback.message, text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()