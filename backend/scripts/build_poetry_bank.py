#!/usr/bin/env python3
"""Build the compact runtime poetry catalog from chinese-poetry selections.

The service never needs OpenCC.  Only this reproducible build step converts
the traditional Chinese Tang selection to simplified Chinese.  The resulting
JSON is committed so production remains offline and dependency-free.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any


BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = BACKEND_DIR / "data" / "poetry_bank.json"
SOURCE_VERSION = "chinese-poetry npm 2.0.1"
EASY_EXTERNAL_COUNT = 420
MEDIUM_EXTERNAL_COUNT = 430
CLAUSE_SEPARATOR = re.compile(r"[，。！？；：,.!?;:\n]+")
EDGE_PUNCTUATION = " \t\r\n、·…—-（）()《》〈〉「」『』【】[]\"'"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_json(path: Path, value: Any) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as temporary:
            temporary_name = temporary.name
            json.dump(value, temporary, ensure_ascii=False, indent=2, sort_keys=True)
            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        if temporary_name:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
        raise


def read_records(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, list):
        raise ValueError(f"{path} must contain a JSON array")
    if not all(isinstance(record, dict) for record in value):
        raise ValueError(f"{path} contains a non-object record")
    return value


def clean_lines(paragraphs: Any, converter) -> tuple[str, ...]:
    def strings(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, list):
            for item in value:
                yield from strings(item)
        elif isinstance(value, dict):
            yield from strings(value.get("paragraphs"))

    lines: list[str] = []
    for paragraph in strings(paragraphs):
        for raw_clause in CLAUSE_SEPARATOR.split(converter(paragraph)):
            clause = "".join(raw_clause.split()).strip(EDGE_PUNCTUATION)
            if 2 <= len(clause) <= 28 and clause not in lines:
                lines.append(clause)
    return tuple(lines) if len(lines) >= 2 else ()


def complexity(poem: dict[str, Any]) -> tuple[int, int, int, str]:
    """Rank shorter, more regular works before long and irregular works."""
    lengths = [len(line) for line in poem["lines"]]
    spread = max(lengths) - min(lengths)
    return (max(lengths) + spread * 2, len(lengths), sum(lengths), poem["id"])


def normalize_records(
    records,
    dynasty: str,
    source_key: str,
    converter,
    *,
    title_field: str = "title",
    lines_field: str = "paragraphs",
    default_author: str = "",
) -> list[dict[str, Any]]:
    normalized = []
    seen = set()
    for record in records:
        author = converter(str(record.get("author") or default_author).strip())
        raw_title = record.get(title_field)
        title = converter(str(raw_title or "").strip())
        lines = clean_lines(record.get(lines_field), converter)
        if not author or not title or not lines:
            continue
        identity = (dynasty, author, title, lines)
        if identity in seen:
            continue
        seen.add(identity)
        source_id = str(record.get("id") or "")
        stable = source_id or hashlib.sha256("\0".join((dynasty, author, title, *lines)).encode()).hexdigest()
        normalized.append(
            {
                "id": f"{source_key}-{stable[:20]}",
                "title": title,
                "author": author,
                "dynasty": dynasty,
                "lines": list(lines),
                "source": source_key,
            }
        )
    return normalized


def flatten_qianjiashi(payload: dict[str, Any]) -> list[dict[str, Any]]:
    flattened = []
    for group in payload.get("content", []):
        if not isinstance(group, dict):
            continue
        for record in group.get("content", []):
            if not isinstance(record, dict):
                continue
            match = re.match(r"^[（(]([^）)]+)[）)](.*)$", str(record.get("author") or "").strip())
            if not match:
                continue
            dynasty, author = match.groups()
            flattened.append(
                {
                    "title": record.get("chapter"),
                    "author": author,
                    "dynasty": dynasty,
                    "paragraphs": record.get("paragraphs"),
                }
            )
    return flattened


def normalize_qianjiashi(path: Path, converter) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as source:
        payload = json.load(source)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in flatten_qianjiashi(payload):
        grouped.setdefault(converter(record["dynasty"]), []).append(record)
    poems = []
    for dynasty, records in grouped.items():
        poems.extend(normalize_records(records, dynasty, "qianjiashi", converter))
    return poems


def build(
    tang_path: Path,
    song_path: Path,
    qianjiashi_path: Path,
    shijing_path: Path,
    nalan_path: Path,
    caocao_path: Path,
    output: Path,
) -> dict[str, Any]:
    try:
        from opencc import OpenCC
    except ImportError as error:
        raise RuntimeError(
            "build dependency missing; install opencc-python-reimplemented"
        ) from error

    to_simplified = OpenCC("t2s").convert
    poems = normalize_records(read_records(tang_path), "唐", "tang300", to_simplified)
    # The Song selection is mostly simplified but still contains traditional
    # variants such as “後” and “瀋”, so normalize both sources consistently.
    poems.extend(
        normalize_records(
            read_records(song_path), "宋", "song300", to_simplified, title_field="rhythmic"
        )
    )
    poems.extend(normalize_qianjiashi(qianjiashi_path, to_simplified))
    poems.extend(
        normalize_records(
            read_records(shijing_path),
            "先秦",
            "shijing",
            to_simplified,
            lines_field="content",
            default_author="佚名",
        )
    )
    poems.extend(
        normalize_records(
            read_records(nalan_path), "清", "nalan", to_simplified, lines_field="para"
        )
    )
    poems.extend(
        normalize_records(
            read_records(caocao_path), "汉", "caocao", to_simplified, default_author="曹操"
        )
    )

    # Remove overlaps across selections before difficulty ranking.  千家诗 and
    # 唐诗三百首 intentionally share many famous works.
    unique = {}
    for poem in poems:
        identity = (poem["dynasty"], poem["author"], poem["title"], tuple(poem["lines"]))
        unique.setdefault(identity, poem)
    poems = list(unique.values())
    poems.sort(key=complexity)
    if len(poems) < EASY_EXTERNAL_COUNT + MEDIUM_EXTERNAL_COUNT:
        raise ValueError(f"only {len(poems)} valid poems after normalization")

    for index, poem in enumerate(poems):
        poem["level"] = 1 if index < EASY_EXTERNAL_COUNT else 2 if index < EASY_EXTERNAL_COUNT + MEDIUM_EXTERNAL_COUNT else 3
    poems.sort(key=lambda poem: poem["id"])

    payload = {
        "metadata": {
            "schema_version": 1,
            "generated_count": len(poems),
            "level_counts": {
                "easy": EASY_EXTERNAL_COUNT,
                "medium": MEDIUM_EXTERNAL_COUNT,
                "hard": len(poems) - EASY_EXTERNAL_COUNT - MEDIUM_EXTERNAL_COUNT,
            },
            "source_version": SOURCE_VERSION,
            "license": "MIT",
            "license_url": "https://github.com/chinese-poetry/chinese-poetry/blob/master/LICENSE",
            "sources": [
                {
                    "key": "tang300",
                    "url": "https://github.com/chinese-poetry/chinese-poetry/blob/master/全唐诗/唐诗三百首.json",
                    "sha256": sha256_file(tang_path),
                    "record_count": len(read_records(tang_path)),
                },
                {
                    "key": "song300",
                    "url": "https://github.com/chinese-poetry/chinese-poetry/blob/master/宋词/宋词三百首.json",
                    "sha256": sha256_file(song_path),
                    "record_count": len(read_records(song_path)),
                },
                {
                    "key": "qianjiashi",
                    "url": "https://github.com/chinese-poetry/chinese-poetry/blob/master/蒙学/qianjiashi.json",
                    "sha256": sha256_file(qianjiashi_path),
                    "record_count": len(flatten_qianjiashi(json.loads(qianjiashi_path.read_text(encoding="utf-8")))),
                },
                {
                    "key": "shijing",
                    "url": "https://github.com/chinese-poetry/chinese-poetry/blob/master/诗经/shijing.json",
                    "sha256": sha256_file(shijing_path),
                    "record_count": len(read_records(shijing_path)),
                },
                {
                    "key": "nalan",
                    "url": "https://github.com/chinese-poetry/chinese-poetry/blob/master/纳兰性德/纳兰性德诗集.json",
                    "sha256": sha256_file(nalan_path),
                    "record_count": len(read_records(nalan_path)),
                },
                {
                    "key": "caocao",
                    "url": "https://github.com/chinese-poetry/chinese-poetry/blob/master/曹操诗集/caocao.json",
                    "sha256": sha256_file(caocao_path),
                    "record_count": len(read_records(caocao_path)),
                },
            ],
        },
        "poems": poems,
    }
    atomic_write_json(output, payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tang", type=Path, required=True, help="唐诗三百首 JSON")
    parser.add_argument("--song", type=Path, required=True, help="宋词三百首 JSON")
    parser.add_argument("--qianjiashi", type=Path, required=True, help="千家诗 JSON")
    parser.add_argument("--shijing", type=Path, required=True, help="诗经 JSON")
    parser.add_argument("--nalan", type=Path, required=True, help="纳兰性德诗集 JSON")
    parser.add_argument("--caocao", type=Path, required=True, help="曹操诗集 JSON")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    payload = build(
        args.tang,
        args.song,
        args.qianjiashi,
        args.shijing,
        args.nalan,
        args.caocao,
        args.output,
    )
    print(
        f"wrote {len(payload['poems'])} normalized works to {args.output}; "
        f"levels={payload['metadata']['level_counts']}"
    )


if __name__ == "__main__":
    main()
