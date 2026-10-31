import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "5787410228").replace(" ", "").split(",") if x}

DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "data" / "bot.sqlite3"))
DATA_DIR = BASE_DIR / "data"

# --- Premium ---------------------------------------------------------------
PREMIUM_PRICE_STARS = int(os.getenv("PREMIUM_PRICE_STARS", "150"))
PREMIUM_PERIOD_SECONDS = 30 * 24 * 3600  # Telegram разрешает для подписки только 30 дней

# --- Ловушки ---------------------------------------------------------------
TRAP_INTERVAL = int(os.getenv("TRAP_INTERVAL", str(15 * 60)))  # 15 минут
TRAP_SLOTS = {"free": 5, "premium": 300, "admin": 300}

# --- Суточные лимиты поиска -----------------------------------------------
# ключи: i5/i6 - моментальный, p5/p6 - премиум-поиск. None = без лимита
LIMITS = {
    "free":    {"i5": 3,    "i6": 50,   "p5": 1,   "p6": 5},
    "premium": {"i5": 300,  "i6": 1000, "p5": 150, "p6": 300},
    "admin":   {"i5": None, "i6": None, "p5": None, "p6": None},
}

# --- Проверка ников ------------------------------------------------------
CONCURRENCY = int(os.getenv("CONCURRENCY", "12"))          # параллельных запросов
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "12"))            # кандидатов за один заход
SEARCH_TIMEOUT_INSTANT = int(os.getenv("SEARCH_TIMEOUT_INSTANT", "30"))
SEARCH_TIMEOUT_PREMIUM = int(os.getenv("SEARCH_TIMEOUT_PREMIUM", "90"))
TAKEN_CACHE_TTL = 3 * 3600
USE_GETCHAT = os.getenv("USE_GETCHAT", "1") == "1"         # доп. проверка через Bot API
PROXIES = [p.strip() for p in os.getenv("PROXIES", "").split(",") if p.strip()]

# --- Автопоиск -----------------------------------------------------------
AUTO_CYCLE_SECONDS = int(os.getenv("AUTO_CYCLE_SECONDS", "90"))
AUTO_PRICE_PRESETS = [50, 100, 300, 500, 1000, 5000]  # TON

# --- Премиум-эмодзи ------------------------------------------------------
USE_CUSTOM_EMOJI = os.getenv("USE_CUSTOM_EMOJI", "1") == "1"
# Наборы премиум-эмодзи (ссылка t.me/addemoji/ИМЯ -> ИМЯ), через запятую; можно добавить и командой /addpack
EMOJI_PACKS = [p.strip() for p in os.getenv("EMOJI_PACKS", "").split(",") if p.strip()]

# --- Точная проверка через аккаунт Telegram (отсеивает заблокированные/зарезервированные ники) ---
# Получить на https://my.telegram.org/apps, затем один раз выполнить: python tools/login.py
TG_API_ID = int(os.getenv("TG_API_ID", "0") or 0)
TG_API_HASH = os.getenv("TG_API_HASH", "").strip()
TG_SESSION = str(DATA_DIR / "user")
TG_CHECK_CONCURRENCY = int(os.getenv("TG_CHECK_CONCURRENCY", "3"))
