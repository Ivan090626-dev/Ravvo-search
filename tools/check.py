"""Диагностика: что именно отвечают t.me, Fragment и Telegram (checkUsername) про ники.

Остановите бота (Ctrl+C), затем:
    python3 tools/check.py zoutu abcde
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
from checker import Checker  # noqa: E402


async def main(names: list[str]) -> None:
    c = Checker()
    await c.start()
    print(f"\nТочная проверка через аккаунт: {'ВКЛЮЧЕНА' if c.tl else 'ВЫКЛЮЧЕНА (ники не фильтруются!)'}\n")
    for name in names:
        name = name.lstrip("@").lower()
        tg = await c.tg_status(name)
        frag = await c.fragment_status(name)
        raw = "-"
        if c.tl:
            from telethon.tl.functions.account import CheckUsernameRequest
            try:
                raw = repr(await c.tl(CheckUsernameRequest(name)))
            except Exception as ex:
                raw = f"{type(ex).__name__}: {ex}"
        res = await c.check(name, use_cache=False)
        print(f"@{name}\n  t.me: {tg}\n  Fragment: {frag}\n  checkUsername: {raw}\n"
              f"  ИТОГ бота: {'СВОБОДЕН' if res.free else 'не свободен'} (tg={res.tg}, frag={res.frag})\n")
    await c.close()


if len(sys.argv) < 2:
    sys.exit("Пример: python3 tools/check.py zoutu")
asyncio.run(main(sys.argv[1:]))
