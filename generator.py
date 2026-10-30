"""Генерация кандидатов: случайные буквы (моментальный) и читаемые ники (премиум)."""
import random
import string
from collections import defaultdict

import config

LETTERS = string.ascii_lowercase
VOWELS = "aeiou"
CONS = "bcdfghjklmnprstvwz"

# Небольшой встроенный набор; основной список лежит в data/words5.txt и data/words6.txt
# (его создаёт tools/make_wordlists.py или вы кладёте свой, по одному слову в строке).
BUILTIN = {
    5: "alpha angel brand brave cloud crown dream eagle early fable flame ghost happy "
       "honey hotel ivory jolly karma lemon magic noble ocean pearl pixel queen quick "
       "river royal scale smile solar sugar tiger ultra vivid water wolfy zebra bonus "
       "cyber ninja pilot robot spark storm trend urban vault world youth music money "
       "stone light night amber blaze coral delta ember frost glory haven lotus mango".split(),
    6: "anchor beauty bridge candle castle circle dragon engine falcon forest garden "
       "golden hunter island jungle knight legend magnet marble master nature orange "
       "planet rocket silver spirit summer tunnel velvet window winter wizard yellow "
       "zephyr bronze crypto coffee dollar future galaxy hammer insane kitten laptop".split(),
}

_PATTERNS = {
    5: ["CVCVC", "CVCCV", "CVCVV", "VCVCV", "CVVCV", "CCVCV", "CVCCV"],
    6: ["CVCVCV", "CVCCVC", "CVCVCC", "CCVCVC", "CVCVVC", "VCVCVC", "CVCCVV"],
}

_words: dict[int, list[str]] = {}


def _load_words() -> None:
    for n in (5, 6):
        words = set(BUILTIN[n])
        p = config.DATA_DIR / f"words{n}.txt"
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                w = line.strip().lower()
                if len(w) == n and w.isascii() and w.isalpha():
                    words.add(w)
        _words[n] = sorted(words)


_load_words()


def instant(length: int) -> str:
    """Случайный набор букв: быстро, но чаще бессмыслица."""
    return "".join(random.choices(LETTERS, k=length))


def pronounceable(length: int) -> str:
    pat = random.choice(_PATTERNS[length])
    return "".join(random.choice(CONS if ch == "C" else VOWELS) for ch in pat)


def readable(length: int) -> str:
    """Слово из словаря либо произносимая комбинация."""
    if _words[length] and random.random() < 0.5:
        return random.choice(_words[length])
    return pronounceable(length)


class Seen:
    """Чтобы не показывать одному человеку один и тот же ник дважды."""

    def __init__(self, cap: int = 4000) -> None:
        self.cap = cap
        self.data: dict[int, set[str]] = defaultdict(set)

    def has(self, uid: int, name: str) -> bool:
        return name in self.data[uid]

    def add(self, uid: int, name: str) -> None:
        s = self.data[uid]
        if len(s) > self.cap:
            s.clear()
        s.add(name)


def candidates(length: int, mode: str, count: int, seen_users: set[str] | None = None) -> list[str]:
    gen = instant if mode == "i" else readable
    out: set[str] = set()
    tries = 0
    while len(out) < count and tries < count * 20:
        tries += 1
        name = gen(length)
        if seen_users and name in seen_users:
            continue
        out.add(name)
    return list(out)


def dictionary_words(length: int) -> list[str]:
    return _words[length]
