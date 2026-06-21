from aiogram import Router, types
from aiogram.filters import Command
from config import ADMIN_IDS
from db.models import update_player, add_character
from engine.data_loader import data_cache

router = Router()

@router.message(Command("give_gems"))
async def give_gems(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        _, user_id, amount = message.text.split()
        user_id = int(user_id)
        amount = int(amount)
        await update_player(user_id, gems=amount)  # нужно доработать функцию для инкремента
        await message.answer(f"✅ Выдано {amount} гемов игроку {user_id}")
    except:
        await message.answer("Использование: /give_gems user_id amount")

@router.message(Command("give_cores"))
async def give_cores(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    _, user_id, amount = message.text.split()
    user_id = int(user_id)
    amount = int(amount)
    await update_player(user_id, awakening_cores=amount)
    await message.answer(f"✅ Выдано {amount} ядер игроку {user_id}")

@router.message(Command("give_gold"))
async def give_gold(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        _, user_id, amount = message.text.split()
        user_id = int(user_id)
        amount = int(amount)
        await update_player(user_id, gold=amount)
        await message.answer(f"✅ Выдано {amount} золота игроку {user_id}")
    except:
        await message.answer("Использование: /give_gold user_id amount")

@router.message(Command("give_dust"))
async def give_dust(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return await message.answer("⛔ У вас нет прав администратора.")
    
    try:
        _, user_id, amount = message.text.split()
        user_id = int(user_id)
        amount = int(amount)
    except ValueError:
        return await message.answer("❌ Формат: /give_dust user_id количество")
    
    await update_player(user_id, relic_dust=amount)
    await message.answer(f"✅ Выдано {amount}💨 пыли игроку `{user_id}`", parse_mode="Markdown")

@router.message(Command("simulate_rimuru"))
async def simulate_rimuru(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    rimuru = data_cache.characters.get('rimuru_tempest')
    if not rimuru:
        await message.answer("❌ Римуру не найден в базе.")
        return

    # Имитируем трейт/судьбу для теста (можно поставить None для проверки отсутствия)
    trait_id = None   # или "swift" для примера
    destiny_id = None # или "monarch"

    card = (
        f"🌈 <b>{rimuru['name']}</b> (Secret)\n"
        f"━━━━━━━━━━━━━━━━\n"
    )
    if trait_id:
        trait_data = data_cache.traits.get(trait_id)
        trait_desc = f"{trait_data['name']} — {trait_data['desc']}" if trait_data else trait_id
        card += f"🧬 Trait: {trait_desc}\n"
    else:
        card += "🧬 Trait: —\n"

    if destiny_id:
        destiny_data = data_cache.destinies.get(destiny_id)
        destiny_desc = f"{destiny_data['name']} — {destiny_data['desc']}" if destiny_data else destiny_id
        card += f"🔮 Destiny: {destiny_desc}\n"
    else:
        card += "🔮 Destiny: —\n"

    card += (
        f"━━━━━━━━━━━━━━━━\n"
        f"❤️ HP: {rimuru['hp']} | ⚔️ ATK: {rimuru['atk']}\n"
        f"🛡️ DEF: {rimuru['def']} | 💨 SPD: {rimuru['spd']}\n"
        f"💥 CRIT: {rimuru['crit']}%\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"⚔️ Навыки:\n"
    )
    for sid in rimuru.get('skills', []):
        skill = data_cache.skills.get(sid)
        if skill:
            cd = skill.get('cooldown', 0)
            cd_text = f" (CD: {cd})" if cd else ""
            card += f"• {skill['name']}{cd_text}: {skill.get('type','')}\n"
    card += "\n🎉 Поздравляем! Вы получили Римуру Темпеста!"

    animation_url = rimuru.get('animation_url')
    image_url = rimuru.get('image_url')
    try:
        if animation_url:
            await message.answer_video(video=animation_url, caption=card, parse_mode="HTML")
        elif image_url:
            await message.answer_photo(photo=image_url, caption=card, parse_mode="HTML")
        else:
            await message.answer(card, parse_mode="HTML")
    except Exception:
        await message.answer(card, parse_mode="HTML")