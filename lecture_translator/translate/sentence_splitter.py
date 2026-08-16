"""Розбиття німецького тексту на речення (чиста функція, без зовнішніх залежностей).

Правила:
  - кінець речення: «.», «!», «?» у кінці токена (після можливих закривних лапок/дужок),
    якщо наступний токен починається з великої літери, цифри чи є кінцем тексту;
  - крапка НЕ є кінцем після абревіатур (z.B., bzw., Prof. ...) та ініціалів/
    порядкових номерів («A.», «5.»);
  - фолбек: речення довше 80 слів ріжеться на межі токена.
Помилка розбиття впливає лише на момент появи перекладу — жоден токен не губиться.
"""
from __future__ import annotations

import re

_TOKEN = re.compile(r"\S+")

# Абревіатури (нижній регістр), після яких крапка не завершує речення
_ABBREV = {
    "z.b.", "z.b", "bzw.", "d.h.", "d.h", "u.a.", "u.a", "usw.", "u.s.w.",
    "u.v.m.", "uvm.", "dr.", "prof.", "nr.", "abb.", "bd.", "s.", "ca.",
    "vgl.", "etc.", "ggf.", "inkl.", "evtl.", "mind.", "max.", "tel.",
    "hr.", "fr.", "mio.", "mrd.", "art.", "abs.", "sog.", "allg.", "jew.",
}


def _stripped(token: str) -> str:
    return token.rstrip("»«\"'“”‘’)]};:")


def _ends_sentence(token: str) -> bool:
    core = _stripped(token)
    if not core:
        return False
    last = core[-1]
    if last in "!?":
        return True
    if last != ".":
        return False
    low = core.lower()
    if low in _ABBREV:
        return False
    bare = core.rstrip(".")
    if bare.isdigit():  # порядковий номер: "Kapitel 5."
        return False
    if len(bare) == 1 and bare.isupper():  # ініціал: "Punkt A."
        return False
    return True


def _next_starts_sentence(next_token: str | None) -> bool:
    if next_token is None:
        return True
    s = next_token.lstrip("„“\"'«(")
    if not s:
        return True
    return s[0].isupper() or s[0].isdigit()


def split_german(text: str, max_words: int = 80) -> list[str]:
    """Повертає список речень. join(sentences, " ") == нормалізований вхідний текст."""
    if not text:
        return []
    normalized = " ".join(text.split())
    tokens = _TOKEN.findall(normalized)
    if not tokens:
        return []

    sentences: list[str] = []
    cur: list[str] = []
    cur_words = 0

    for i, tok in enumerate(tokens):
        cur.append(tok)
        cur_words += 1
        nxt = tokens[i + 1] if i + 1 < len(tokens) else None
        if _ends_sentence(tok) and _next_starts_sentence(nxt):
            sentences.append(" ".join(cur))
            cur = []
            cur_words = 0
        elif cur_words >= max_words:
            sentences.append(" ".join(cur))
            cur = []
            cur_words = 0

    if cur:
        sentences.append(" ".join(cur))
    return sentences
