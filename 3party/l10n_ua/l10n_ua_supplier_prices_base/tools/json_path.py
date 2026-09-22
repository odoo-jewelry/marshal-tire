"""Простий path resolver для вкладених JSON структур.

Підтримуваний синтаксис:
    field             — простий ключ
    a.b.c             — dotted path вкладених dict
    items[0]          — індекс масиву
    items[*]          — ітерація по масиву
    items[*].price    — ітерація + nested access
    a.b[*].c.d        — комбінація

Резолвинг повертає список значень. Якщо path не містить [*], список має 0 або 1
елемент. Якщо містить [*] — стільки елементів, скільки в масиві.
"""

import re
from typing import Any


_TOKEN_RE = re.compile(r'([^.\[\]]+)|\[(\*|-?\d+)\]')


def parse_path(path: str) -> list[tuple[str, str | int]]:
    """Розбиває path на список (kind, value) токенів.

    kind: 'key' (значення — str), 'index' (int), 'iter' (значення — '*')
    Повертає [] для порожнього path.
    """
    if not path:
        return []
    tokens: list[tuple[str, str | int]] = []
    for match in _TOKEN_RE.finditer(path):
        key, idx = match.group(1), match.group(2)
        if key is not None:
            tokens.append(('key', key))
        elif idx == '*':
            tokens.append(('iter', '*'))
        else:
            tokens.append(('index', int(idx)))
    return tokens


def resolve(data: Any, path: str) -> list[Any]:
    """Резолвить path у data, повертає список знайдених значень.

    Якщо ключ/індекс не існує — пропускає (не raise). Це навмисно: відсутність
    треба обробляти у viewer (default_value, required check), а не в resolver.
    """
    tokens = parse_path(path)
    if not tokens:
        return [data] if data is not None else []
    current: list[Any] = [data]
    for kind, value in tokens:
        next_values: list[Any] = []
        for item in current:
            if kind == 'key':
                if isinstance(item, dict) and value in item:
                    next_values.append(item[value])
            elif kind == 'index':
                if isinstance(item, list) and -len(item) <= value < len(item):
                    next_values.append(item[value])
            elif kind == 'iter':
                if isinstance(item, list):
                    next_values.extend(item)
        current = next_values
    return current


def resolve_first(data: Any, path: str, default: Any = None) -> Any:
    """Зручний хелпер: повертає перший знайдений елемент або default."""
    values = resolve(data, path)
    return values[0] if values else default
