from aiogram import types
from typing import Optional

async def edit_or_answer(message: types.Message, text: str, reply_markup=None, parse_mode=None, **kwargs):
    """Редактирует текущее сообщение или отправляет новое, если редактирование невозможно."""
    try:
        await message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode, **kwargs)
    except Exception:
        # Если сообщение нельзя отредактировать (удалено, слишком старое), отправляем новое
        await message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode, **kwargs)