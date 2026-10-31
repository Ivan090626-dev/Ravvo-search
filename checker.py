
"""Проверка занятости ника в Telegram и на Fragment.
 
Telegram: страница https://t.me/<name>. Если у ника есть владелец (профиль, канал, группа, бот),
в HTML есть блок tgme_page_title. Для свободного ника его нет. Дополнительно (опционально)
проверяем через Bot API getChat.
 
Fragment: страница https://fragment.com/username/<name>. Статус берётся из шапки страницы:
Available (продаётся), On auction, Sold, Taken, Unavailable.
Ник считаем свободным, только если в Telegram свободен и на Fragment нет ни продажи, ни аукциона.
"""
import asyncio
import itertools
import logging
import re
import time
from dataclasses import dataclass
from typing import Optional
 
import aiohttp
 
import config
 
log = logging.getLogger("checker")
 
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
 
# tg:   free | taken | error
# frag: none | sale | auction | sold | taken | error | skip
@dataclass
class Check:
    name: str
    tg: str
    frag: str = "skip"
    price: Optional[float] = None
 
    @property
    def free(self) -> bool:
        return self.tg == "free" and self.frag == "none"
 
    @property
    def has_error(self) -> bool:
        return self.tg == "error" or self.frag == "error"
 
 
# ---------------- чистые парсеры (их можно тестировать без сети) ----------------
def parse_tme(html: str) -> str:
    if "tgme_page" not in html:
        return "error"
    return "taken" if "tgme_page_title" in html else "free"
 
 
_STATUS_RE = re.compile(
    r'class="[^"]*tm-section-header-status[^"]*"[^>]*>\s*([^<]+?)\s*<', re.I
)
_PRICE_RE = re.compile(r'icon-ton[^>]*>\s*([\d][\d,\.\s]*?)\s*<', re.I)
 
 
def _status_from_text(text: str) -> str:
    t = text.lower()
    if "unavailable" in t:
        return "none"
    if "auction" in t:
        return "auction"
    if "available" in t:
        return "sale"
    if "sold" in t:
        return "sold"
    if "taken" in t:
        return "taken"
    return "none"
 
 
def _to_price(s: str) -> Optional[float]:
    try:
        return float(s.replace(",", "").replace(" ", ""))
    except ValueError:
        return None
 
 
def parse_fragment(html: str, name: str, final_path: str = "") -> tuple[str, Optional[float]]:
    """Возвращает (статус, цена в TON)."""
    m = _STATUS_RE.search(html)
    if m:
        status = _status_from_text(m.group(1))
        pm = _PRICE_RE.search(html)
        return status, (_to_price(pm.group(1)) if pm and status in ("sale", "auction") else None)
 
    # Страница поиска (Fragment перекинул с /username/<name> на /?query=<name>):
    # ищем строку именно с этим ником и статус рядом с ней.
    low = html.lower()
    idx = low.find(f"@{name.lower()}<")
    if idx == -1:
        idx = low.find(f">{name.lower()}<")
    if idx != -1:
        chunk = html[idx: idx + 1500]
        sm = re.search(r'tm-status-(\w+)[^>]*>\s*([^<]+?)\s*<', chunk)
        if sm:
            status = _status_from_text(sm.group(2))
            pm = _PRICE_RE.search(chunk)
            return status, (_to_price(pm.group(1)) if pm and status in ("sale", "auction") else None)
    return "none", None
 
 
_LISTING_ROW_RE = re.compile(r'href="/username/([a-z0-9_]{5,32})"', re.I)
 
 
def parse_listing(html: str) -> list[tuple[str, Optional[float]]]:
    """Первая страница выдачи Fragment: [(ник, цена)]."""
    out, seen = [], set()
    for m in _LISTING_ROW_RE.finditer(html):
        name = m.group(1).lower()
        if name in seen:
            continue
        seen.add(name)
        chunk = html[m.end(): m.end() + 1200]
        pm = _PRICE_RE.search(chunk)
        out.append((name, _to_price(pm.group(1)) if pm else None))
    return out
 
 
# ------------------------------ сетевой слой ----------------------------------
class Checker:
    def __init__(self) -> None:
        self._session: Optional[aiohttp.ClientSession] = None
        self._sem = asyncio.Semaphore(config.CONCURRENCY)
        self._pause_until = 0.0
        self._proxy_cycle = itertools.cycle(config.PROXIES) if config.PROXIES else None
        self._taken: dict[str, float] = {}
        self.bot = None  # выставляется в main.py для getChat
        self.tl = None   # клиент Telethon (аккаунт) для точной проверки; None, если не настроен
        self._tl_sem = asyncio.Semaphore(config.TG_CHECK_CONCURRENCY)
        self._tl_pause = 0.0
 
    async def start(self) -> None:
        timeout = aiohttp.ClientTimeout(total=12)
        self._session = aiohttp.ClientSession(
            timeout=timeout, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}
        )
 
        await self._start_telethon()
 
    async def _start_telethon(self) -> None:
        if not (config.TG_API_ID and config.TG_API_HASH):
            log.warning("Точная проверка (заблокированные ники) ВЫКЛЮЧЕНА: не заданы TG_API_ID/TG_API_HASH. "
                        "Без неё в выдачу могут попадать ники, заблокированные Telegram.")
            return
        try:
            from telethon import TelegramClient
            client = TelegramClient(config.TG_SESSION, config.TG_API_ID, config.TG_API_HASH)
            await client.connect()
            if not await client.is_user_authorized():
                log.warning("Сессия аккаунта не авторизована. Выполните: python tools/login.py")
                await client.disconnect()
                return
            me = await client.get_me()
            if getattr(me, "bot", False):
                log.warning("Сессия data/user.session создана от БОТА, а нужен обычный аккаунт. "
                            "Удалите data/user.session и выполните python3 tools/login.py с НОМЕРОМ телефона.")
                await client.disconnect()
                return
            self.tl = client
            log.info("Точная проверка ников через аккаунт Telegram включена")
        except ImportError:
            log.warning("Не установлен telethon: pip install telethon")
        except Exception as ex:
            log.warning("Не удалось запустить Telethon: %r", ex)
 
    async def close(self) -> None:
        if self.tl:
            await self.tl.disconnect()
        if self._session:
            await self._session.close()
 
    async def tl_available(self, name: str) -> str:
        """Официальная проверка account.checkUsername. Возвращает free | taken | error.
        Заблокированные, зарезервированные и продаваемые ники дают taken."""
        wait = self._tl_pause - time.time()
        if wait > 0:
            await asyncio.sleep(min(wait, 60))
        from telethon.errors import RPCError
        from telethon.tl.functions.account import CheckUsernameRequest
        async with self._tl_sem:
            try:
                ok = await self.tl(CheckUsernameRequest(name))
                return "free" if ok else "taken"
            except RPCError as ex:
                kind = type(ex).__name__
                seconds = getattr(ex, "seconds", None)
                if seconds:  # FloodWait
                    self._tl_pause = time.time() + seconds
                    log.warning("FloodWait от Telegram: пауза %s с", seconds)
                    return "error"
                if any(k in kind.upper() for k in ("USERNAMEINVALID", "USERNAMEOCCUPIED", "USERNAMEPURCHASE")):
                    return "taken"
                log.debug("checkUsername %s: %s", name, kind)
                return "error"
            except Exception as ex:
                log.debug("checkUsername %s: %r", name, ex)
                return "error"
 
    # --- кэш занятых ---
    def is_cached_taken(self, name: str) -> bool:
        ts = self._taken.get(name)
        if ts and time.time() - ts < config.TAKEN_CACHE_TTL:
            return True
        return False
 
    def _remember_taken(self, name: str) -> None:
        if len(self._taken) > 200_000:
            self._taken.clear()
        self._taken[name] = time.time()
 
    # --- HTTP ---
    async def _get(self, url: str) -> Optional[tuple[int, str, str]]:
        wait = self._pause_until - time.time()
        if wait > 0:
            await asyncio.sleep(min(wait, 30))
        proxy = next(self._proxy_cycle) if self._proxy_cycle else None
        async with self._sem:
            try:
                async with self._session.get(url, proxy=proxy) as r:
                    text = await r.text()
                    if r.status == 429:
                        retry = int(r.headers.get("Retry-After", "5"))
                        self._pause_until = time.time() + retry
                        log.warning("429 от %s, пауза %ss", url, retry)
                    return r.status, text, r.url.path
            except Exception as ex:  # сеть, таймаут
                log.debug("GET %s: %r", url, ex)
                return None
 
    async def tg_status(self, name: str) -> str:
        res = await self._get(f"https://t.me/{name}")
        if not res or res[0] != 200:
            return "error"
        status = parse_tme(res[1])
        if status == "free" and config.USE_GETCHAT and self.bot is not None:
            try:
                await self.bot.get_chat(f"@{name}")
                return "taken"  # getChat нашёл владельца
            except Exception as ex:
                msg = str(ex).lower()
                if "not found" not in msg:
                    log.debug("getChat @%s: %s", name, msg)
        return status
 
    async def fragment_status(self, name: str) -> tuple[str, Optional[float]]:
        res = await self._get(f"https://fragment.com/username/{name}")
        if not res or res[0] != 200:
            return "error", None
        return parse_fragment(res[1], name, res[2])
 
    async def check(self, name: str, use_cache: bool = True) -> Check:
        name = name.lower()
        if use_cache and self.is_cached_taken(name):
            return Check(name, "taken")
        tg = await self.tg_status(name)
        if tg == "taken":
            self._remember_taken(name)
            return Check(name, "taken")
        if tg == "error":
            return Check(name, "error")
        frag, price = await self.fragment_status(name)
        if frag in ("sale", "auction", "sold", "taken"):
            self._remember_taken(name)
        if frag == "error":
            return Check(name, "free", "error")
        if frag == "none" and self.tl is not None:
            res = await self.tl_available(name)
            if res == "taken":
                self._remember_taken(name)
                return Check(name, "taken")
            if res == "error":
                return Check(name, "error")
        return Check(name, "free", frag, price)
 
    async def check_many(self, names: list[str], use_cache: bool = True) -> list[Check]:
        return await asyncio.gather(*(self.check(n, use_cache) for n in names))
 
    async def fragment_listing(self) -> list[tuple[str, Optional[float]]]:
        """Дешёвые ники с первой страницы Fragment (best effort)."""
        out: list[tuple[str, Optional[float]]] = []
        for flt in ("sale", "auction"):
            res = await self._get(f"https://fragment.com/?filter={flt}&sort=price_asc")
            if res and res[0] == 200:
                out += parse_listing(res[1])
        return out
