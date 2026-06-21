import json
import os

class DataCache:
    def __init__(self):
        self.characters = {}
        self.skills = {}
        self.traits = {}
        self.destinies = {}
        self.relics = {}
        self.items = {}
        self.world_mult = {}
        self.backgrounds = {}
        self.event_banner = {}
        self.enemies = {}
        self.load_all()

    def _load_json(self, filename):
        path = os.path.join('data', filename)
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def load_all(self):
        # Персонажи
        chars = self._load_json('characters.json')
        for c in chars:
            self.characters[c['id']] = c

        # Навыки
        skills = self._load_json('skills.json')
        for s in skills:
            self.skills[s['id']] = s

        # Трейты
        traits = self._load_json('traits.json')
        for t in traits:
            self.traits[t['id']] = t

        # Судьбы
        dests = self._load_json('destinies.json')
        for d in dests:
            self.destinies[d['id']] = d

        # Реликвии
        relics = self._load_json('relics.json')
        for r in relics:
            self.relics[r['id']] = r

        # Предметы
        items = self._load_json('items.json')
        for i in items:
            self.items[i['id']] = i

        # Множители миров
        self.world_mult = self._load_json('world_multipliers.json')

        # Фоны
        bgs = self._load_json('backgrounds.json')
        for b in bgs:
            self.backgrounds[b['id']] = b

        # Ивентовый баннер
        event = self._load_json('event_banner.json')
        if event:
            self.event_banner = event
        else:
            self.event_banner = {}
        
        try:
            self.enemies = self._load_json('enemies.json')
            if not isinstance(self.enemies, dict):
                self.enemies = {}
        except (FileNotFoundError, json.JSONDecodeError):
            print("⚠️ enemies.json не найден или повреждён, враги не загружены.")
            self.enemies = {}

    def reload(self):
        self.load_all()

data_cache = DataCache()