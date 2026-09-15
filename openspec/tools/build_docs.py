#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

GENERATED = "<!-- GENERATED FROM OPENSPEC FEATURE CARDS. DO NOT EDIT. -->"

SECTION_TITLES = {
    "base": "Базовые возможности",
    "product": "Товары и каталог",
    "sale": "Продажи",
    "purchase": "Закупки",
    "stock": "Складской учёт",
    "mrp": "Производство",
    "repair": "Ремонты",
    "serial": "Серийные номера",
    "pricing": "Ценообразование",
    "account": "Учёт и финансы",
    "integration": "Интеграции",
}

SECTION_ORDER = [
    "base", "product", "sale", "purchase", "stock",
    "mrp", "repair", "pricing", "account", "integration",
]

CARD_RE = re.compile(
    r"(?ms)^>\s*\[!abstract\]\s*(?P<title>[^\n]+)\n"
    r"(?P<body>(?:^>.*(?:\n|$))+?)"
    r"^\^feature-card\s*$"
)


@dataclass(frozen=True)
class Feature:
    section: str
    slug: str
    title: str
    description: str
    spec_path: Path


def section_title(section: str) -> str:
    return SECTION_TITLES.get(
        section,
        section.replace("_", " ").replace("-", " ").capitalize(),
    )


def section_key(section: str) -> tuple[int, str]:
    try:
        return SECTION_ORDER.index(section), section
    except ValueError:
        return len(SECTION_ORDER), section


def parse_spec(path: Path) -> Feature:
    slug = path.parent.name
    if "-" not in slug:
        raise ValueError(
            f"{path}: имя должно иметь вид <section>-<feature>"
        )

    matches = list(CARD_RE.finditer(path.read_text(encoding="utf-8")))
    if not matches:
        raise ValueError(f"{path}: ^feature-card не найден")
    if len(matches) != 1:
        raise ValueError(f"{path}: должен быть ровно один ^feature-card")

    match = matches[0]
    body = []
    for line in match.group("body").splitlines():
        body.append(re.sub(r"^>\s?", "", line))

    description = "\n".join(body).strip()
    if not description:
        raise ValueError(f"{path}: feature-card не содержит описания")

    return Feature(
        section=slug.split("-", 1)[0],
        slug=slug,
        title=match.group("title").strip(),
        description=description,
        spec_path=path,
    )


def rel_link(from_file: Path, to_file: Path) -> str:
    return Path(os.path.relpath(to_file, from_file.parent)).as_posix()


def render_section(section: str, features: list[Feature], target: Path) -> str:
    lines = [
        GENERATED,
        "",
        f"# {section_title(section)}",
        "",
        "[← Вся документация](README.md)",
        "",
    ]

    ordered = sorted(features, key=lambda x: x.slug)
    for i, feature in enumerate(ordered):
        lines += [
            f"## {feature.title}",
            "",
            feature.description,
            "",
            f"[Полная спецификация]({rel_link(target, feature.spec_path)})",
        ]
        if i != len(ordered) - 1:
            lines += ["", "---", ""]

    lines.append("")
    return "\n".join(lines)


def render_index(grouped: dict[str, list[Feature]]) -> str:
    lines = [
        GENERATED,
        "",
        "# Документация системы",
        "",
        "Документ собран автоматически из канонических OpenSpec-спецификаций.",
        "",
        "## Функциональные разделы",
        "",
    ]

    for section in sorted(grouped, key=section_key):
        lines.append(
            f"- [{section_title(section)}]({section}.md) — "
            f"функций: {len(grouped[section])}"
        )

    lines += [
        "",
        "## Источник",
        "",
        "Краткие описания берутся из блоков `^feature-card` "
        "в `openspec/specs/*/spec.md`.",
        "",
    ]
    return "\n".join(lines)


def collect(specs_dir: Path) -> tuple[dict[str, list[Feature]], list[str]]:
    grouped: dict[str, list[Feature]] = defaultdict(list)
    errors = []

    paths = sorted(specs_dir.glob("*/spec.md"))
    if not paths:
        return grouped, [f"{specs_dir}: spec.md не найдены"]

    for path in paths:
        try:
            feature = parse_spec(path)
            grouped[feature.section].append(feature)
        except ValueError as exc:
            errors.append(str(exc))

    return grouped, errors


def expected(grouped: dict[str, list[Feature]], output: Path) -> dict[Path, str]:
    files = {output / "README.md": render_index(grouped)}
    for section, features in grouped.items():
        target = output / f"{section}.md"
        files[target] = render_section(section, features, target)
    return files


def remove_stale(output: Path, keep: set[Path]) -> None:
    if not output.exists():
        return
    for path in output.glob("*.md"):
        if path in keep:
            continue
        try:
            first = path.read_text(encoding="utf-8").splitlines()[0]
        except (OSError, IndexError):
            continue
        if first == GENERATED:
            path.unlink()


def write(files: dict[Path, str], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    remove_stale(output, set(files))
    for path, text in sorted(files.items()):
        path.write_text(text, encoding="utf-8")
        print(f"Создан: {path}")


def check(files: dict[Path, str], output: Path) -> int:
    problems = []

    for path, wanted in sorted(files.items()):
        if not path.exists():
            problems.append(f"отсутствует: {path}")
        elif path.read_text(encoding="utf-8") != wanted:
            problems.append(f"устарел: {path}")

    if output.exists():
        for path in output.glob("*.md"):
            if path in files:
                continue
            try:
                first = path.read_text(encoding="utf-8").splitlines()[0]
            except (OSError, IndexError):
                continue
            if first == GENERATED:
                problems.append(f"лишний файл: {path}")

    if problems:
        print("Документация не синхронизирована:", file=sys.stderr)
        for problem in problems:
            print(f"- {problem}", file=sys.stderr)
        return 1

    print("Документация актуальна.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--specs", type=Path, default=Path("openspec/specs"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("openspec/docs/capabilities"),
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    specs_dir = args.specs.resolve()
    output = args.output.resolve()

    grouped, errors = collect(specs_dir)
    if errors:
        print("Ошибки:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    files = expected(grouped, output)
    return check(files, output) if args.check else (write(files, output) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
