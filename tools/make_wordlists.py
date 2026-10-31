"""Необязательно: расширяет словари для Premium-поиска.
Использование: python tools/make_wordlists.py путь/к/списку_слов.txt
Слова нужной длины (5 и 6 букв, только a-z) попадут в data/words5.txt и data/words6.txt.
"""
import re
import sys
from pathlib import Path

src = Path(sys.argv[1]).read_text(encoding="utf-8", errors="ignore").split()
out = Path(__file__).resolve().parent.parent / "data"
out.mkdir(exist_ok=True)
for n in (5, 6):
    words = sorted({w.lower() for w in src if len(w) == n and re.fullmatch(r"[A-Za-z]+", w)})
    (out / f"words{n}.txt").write_text("\n".join(words), encoding="utf-8")
    print(n, len(words))
