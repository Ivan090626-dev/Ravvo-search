import time
from datetime import datetime, timezone
from typing import Optional

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY,
    username TEXT,
    name TEXT,
    joined INTEGER,
    premium_until INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS usage(
    user_id INTEGER, day TEXT, key TEXT, cnt INTEGER DEFAULT 0,
    PRIMARY KEY(user_id, day, key)
);
CREATE TABLE IF NOT EXISTS traps(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER, username TEXT, created INTEGER,
    UNIQUE(user_id, username)
);
CREATE TABLE IF NOT EXISTS auto(
    user_id INTEGER PRIMARY KEY,
    length INTEGER, max_price REAL, active INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS auto_notified(
    user_id INTEGER, username TEXT, PRIMARY KEY(user_id, username)
);
CREATE TABLE IF NOT EXISTS cards(
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER
);
CREATE TABLE IF NOT EXISTS channels(
    chat_id INTEGER PRIMARY KEY, title TEXT, link TEXT, added INTEGER
);
CREATE TABLE IF NOT EXISTS limit_hits(
    user_id INTEGER PRIMARY KEY, day TEXT
);
CREATE TABLE IF NOT EXISTS payments(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER, charge_id TEXT, amount INTEGER, ts INTEGER
);
"""


def today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class DB:
    def __init__(self, path: str) -> None:
        self.path = path
        self.conn: Optional[aiosqlite.Connection] = None

    async def init(self) -> None:
        self.conn = await aiosqlite.connect(self.path)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.executescript(SCHEMA)
        await self.conn.commit()

    async def close(self) -> None:
        if self.conn:
            await self.conn.close()

    async def _q(self, sql: str, args: tuple = (), commit: bool = False):
        cur = await self.conn.execute(sql, args)
        rows = await cur.fetchall()
        if commit:
            await self.conn.commit()
        return rows

    # ---------- пользователи ----------
    async def upsert_user(self, uid: int, username: Optional[str], name: str) -> None:
        await self._q(
            "INSERT INTO users(id, username, name, joined) VALUES(?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET username=excluded.username, name=excluded.name",
            (uid, username, name, int(time.time())), commit=True,
        )

    async def premium_until(self, uid: int) -> int:
        rows = await self._q("SELECT premium_until FROM users WHERE id=?", (uid,))
        return int(rows[0]["premium_until"]) if rows else 0

    async def set_premium_until(self, uid: int, ts: int) -> None:
        await self._q(
            "INSERT INTO users(id, joined, premium_until) VALUES(?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET premium_until=excluded.premium_until",
            (uid, int(time.time()), ts), commit=True,
        )

    async def add_premium_days(self, uid: int, days: int) -> int:
        cur = max(await self.premium_until(uid), int(time.time()))
        new = cur + days * 86400
        await self.set_premium_until(uid, new)
        return new

    async def all_user_ids(self) -> list[int]:
        return [r["id"] for r in await self._q("SELECT id FROM users")]

    async def stats(self) -> dict:
        now = int(time.time())
        u = (await self._q("SELECT COUNT(*) c FROM users"))[0]["c"]
        p = (await self._q("SELECT COUNT(*) c FROM users WHERE premium_until>?", (now,)))[0]["c"]
        t = (await self._q("SELECT COUNT(*) c FROM traps"))[0]["c"]
        a = (await self._q("SELECT COUNT(*) c FROM auto WHERE active=1"))[0]["c"]
        s = (await self._q("SELECT COALESCE(SUM(amount),0) s FROM payments"))[0]["s"]
        return {"users": u, "premium": p, "traps": t, "auto": a, "stars": s}

    # ---------- лимиты ----------
    async def usage_get(self, uid: int, key: str) -> int:
        rows = await self._q(
            "SELECT cnt FROM usage WHERE user_id=? AND day=? AND key=?", (uid, today(), key)
        )
        return int(rows[0]["cnt"]) if rows else 0

    async def usage_inc(self, uid: int, key: str) -> None:
        await self._q(
            "INSERT INTO usage(user_id, day, key, cnt) VALUES(?,?,?,1) "
            "ON CONFLICT(user_id, day, key) DO UPDATE SET cnt=cnt+1",
            (uid, today(), key), commit=True,
        )

    # ---------- ловушки ----------
    async def traps_list(self, uid: int) -> list[aiosqlite.Row]:
        return await self._q("SELECT * FROM traps WHERE user_id=? ORDER BY id", (uid,))

    async def traps_count(self, uid: int) -> int:
        return (await self._q("SELECT COUNT(*) c FROM traps WHERE user_id=?", (uid,)))[0]["c"]

    async def trap_add(self, uid: int, name: str) -> bool:
        rows = await self._q(
            "INSERT OR IGNORE INTO traps(user_id, username, created) VALUES(?,?,?) RETURNING id",
            (uid, name, int(time.time())), commit=True,
        )
        return bool(rows)

    async def trap_del(self, uid: int, trap_id: int) -> None:
        await self._q("DELETE FROM traps WHERE id=? AND user_id=?", (trap_id, uid), commit=True)

    async def trap_clear(self, uid: int) -> None:
        await self._q("DELETE FROM traps WHERE user_id=?", (uid,), commit=True)

    async def trap_names(self) -> list[str]:
        return [r["username"] for r in await self._q("SELECT DISTINCT username FROM traps")]

    async def trap_users(self, name: str) -> list[int]:
        return [r["user_id"] for r in await self._q("SELECT user_id FROM traps WHERE username=?", (name,))]

    async def trap_remove_name(self, name: str) -> None:
        await self._q("DELETE FROM traps WHERE username=?", (name,), commit=True)

    # ---------- автопоиск ----------
    async def auto_get(self, uid: int):
        rows = await self._q("SELECT * FROM auto WHERE user_id=?", (uid,))
        return rows[0] if rows else None

    async def auto_set(self, uid: int, length: int, max_price: float, active: int = 1) -> None:
        await self._q(
            "INSERT INTO auto(user_id, length, max_price, active) VALUES(?,?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET length=excluded.length, "
            "max_price=excluded.max_price, active=excluded.active",
            (uid, length, max_price, active), commit=True,
        )

    async def auto_stop(self, uid: int) -> None:
        await self._q("UPDATE auto SET active=0 WHERE user_id=?", (uid,), commit=True)

    async def auto_active(self) -> list[aiosqlite.Row]:
        return await self._q("SELECT * FROM auto WHERE active=1")

    async def auto_was_notified(self, uid: int, name: str) -> bool:
        return bool(await self._q(
            "SELECT 1 FROM auto_notified WHERE user_id=? AND username=?", (uid, name)))

    async def auto_mark(self, uid: int, name: str) -> None:
        await self._q("INSERT OR IGNORE INTO auto_notified VALUES(?,?)", (uid, name), commit=True)

    # ---------- номера карточек ----------
    async def next_card_no(self) -> int:
        cur = await self.conn.execute("INSERT INTO cards(ts) VALUES(?)", (int(time.time()),))
        await self.conn.commit()
        return int(cur.lastrowid)

    # ---------- платежи ----------
    async def payment_add(self, uid: int, charge_id: str, amount: int) -> None:
        await self._q(
            "INSERT INTO payments(user_id, charge_id, amount, ts) VALUES(?,?,?,?)",
            (uid, charge_id, amount, int(time.time())), commit=True,
        )

    # ---------- обязательные каналы ----------
    async def channels_list(self) -> list[aiosqlite.Row]:
        return await self._q("SELECT * FROM channels ORDER BY added")

    async def channel_add(self, chat_id: int, title: str, link: str) -> None:
        await self._q(
            "INSERT INTO channels(chat_id, title, link, added) VALUES(?,?,?,?) "
            "ON CONFLICT(chat_id) DO UPDATE SET title=excluded.title, link=excluded.link",
            (chat_id, title, link, int(time.time())), commit=True,
        )

    async def channel_del(self, chat_id: int) -> None:
        await self._q("DELETE FROM channels WHERE chat_id=?", (chat_id,), commit=True)

    # ---------- уведомления «лимиты сброшены» ----------
    async def limit_hit(self, uid: int) -> None:
        await self._q(
            "INSERT INTO limit_hits(user_id, day) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET day=excluded.day",
            (uid, today()), commit=True,
        )

    async def limit_hits_due(self) -> list[int]:
        return [r["user_id"] for r in await self._q("SELECT user_id FROM limit_hits WHERE day<?", (today(),))]

    async def limit_hit_clear(self, uid: int) -> None:
        await self._q("DELETE FROM limit_hits WHERE user_id=?", (uid,), commit=True)
