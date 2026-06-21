import os
import aiohttp
import aiofiles
from PIL import Image, ImageOps
import tempfile

# Цвета рамок по редкости (RGB)
BORDER_COLORS = {
    'Rare': (90, 156, 245),        # синий
    'Epic': (179, 92, 245),        # фиолетовый
    'Legendary': (245, 197, 66),   # золотой
    'Mythic': (245, 59, 59),       # красный
    'Secret': (245, 107, 255)      # розовый/радужный
}

async def download_image(url):
    """Скачивает изображение во временный файл и возвращает путь."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                raise Exception("Не удалось скачать изображение")
            data = await resp.read()
    # Сохраняем во временный файл с правильным расширением
    ext = os.path.splitext(url)[1] or '.jpg'
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
    async with aiofiles.open(tmp.name, 'wb') as f:
        await f.write(data)
    return tmp.name

def add_rarity_border(image_path, rarity):
    """Добавляет рамку соответствующего цвета и возвращает путь к новому файлу."""
    img = Image.open(image_path).convert("RGB")
    width, height = img.size
    border_size = max(8, min(width, height) // 20)  # адаптивная толщина рамки
    color = BORDER_COLORS.get(rarity, (100, 100, 100))
    # Расширяем холст и заливаем цветом рамки
    bordered = ImageOps.expand(img, border=border_size, fill=color)
    # Сохраняем результат во временный файл
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
    bordered.save(tmp.name, 'PNG')
    return tmp.name