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

    async def start(self) -> None:
        timeout = aiohttp.ClientTimeout(total=12)
        self._session = aiohttp.ClientSession(
            timeout=timeout, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}
        )

    async def close(self) -> None:
        if self._session:
            await self._session.close()

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
