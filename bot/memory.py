import json
from typing import Union


class BotMemory:
    def __init__(self, memory_store, auto_delete_after_minutes: int = 30):
        self.memory_store = memory_store
        self.auto_delete_after_minutes = auto_delete_after_minutes

    @property
    def ttl(self):
        # convert minutes to seconds
        return self.auto_delete_after_minutes * 60

    async def get(self, key: str) -> Union[dict, str]:
        val = await self.memory_store.get(key)
        if not val:
            return {}
        return json.loads(val)

    async def set(self, key: str, value: Union[dict, str]):
        val_as_str = json.dumps(value)
        await self.memory_store.set(key, val_as_str, expire=self.ttl)

    async def delete_all(self, key):
        await self.memory_store.delete(key)
