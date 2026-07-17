#!/usr/bin/env python3
"""Build deterministic external Sudoku and idiom banks using only stdlib.

The script does not download anything.  Supply a checked-out Sudoku Exchange
puzzle-bank directory, JioNLP's ``chinese_idiom.zip``, and an idiom JSON file
that contains definitions (for example crazywhalecc/idiom-database).  JioNLP's
archive contains frequencies only, so definitions are deliberately never
invented or inferred.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Iterable
import zipfile


BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SUDOKU_OUTPUT = BACKEND_DIR / "data" / "external_sudoku_bank.json"
DEFAULT_IDIOM_OUTPUT = BACKEND_DIR / "data" / "external_idiom_bank.json"
DIFFICULTIES = ("easy", "medium", "hard")
FULL_DIGIT_MASK = (1 << 9) - 1

SUDOKU_LINE_RE = re.compile(
    r"^(?P<source_id>[0-9a-fA-F]{12})\s+"
    r"(?P<puzzle>[0-9]{81})\s+"
    r"(?P<rating>[+-]?(?:\d+(?:\.\d*)?|\.\d+))$"
)

SUDOKU_SOURCE = {
    "name": "Sudoku Exchange Puzzle Bank",
    "url": "https://github.com/grantm/sudoku-exchange-puzzle-bank",
    "license": "CC0-1.0 / public domain",
    "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
}
JIONLP_SOURCE = {
    "name": "JioNLP chinese_idiom",
    "role": "word frequency",
    "url": "https://github.com/dongrixinyu/JioNLP",
    "license": "Apache-2.0",
    "license_url": "https://github.com/dongrixinyu/JioNLP/blob/master/LICENSE",
}
IDIOM_CONTENT_SOURCE = {
    "name": "crazywhalecc/idiom-database",
    "role": "definition and pinyin",
    "url": "https://github.com/crazywhalecc/idiom-database",
    "license": "MIT (see upstream data-provenance notice)",
    "license_url": "https://github.com/crazywhalecc/idiom-database/blob/master/LICENSE",
}


def positive_int(value: str) -> int:
    """argparse type for a strictly positive integer."""
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def atomic_write_json(path: Path, value: Any) -> None:
    """Write UTF-8 JSON beside the target and atomically replace it."""
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
        if temporary_name is not None:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
        raise


def sha256_file(path: Path) -> str:
    """Return a streaming SHA-256 digest for provenance metadata."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_sudoku_file(directory: Path, difficulty: str) -> Path:
    """Find the first supported filename for a Sudoku difficulty."""
    candidates = (
        directory / f"sudoku-{difficulty}.txt",
        directory / f"{difficulty}.txt",
        directory / f"sudoku_{difficulty}.txt",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    expected = ", ".join(candidate.name for candidate in candidates)
    raise FileNotFoundError(
        f"missing {difficulty!r} Sudoku input in {directory}; expected one of: {expected}"
    )


def parse_sudoku_file(path: Path, difficulty: str) -> list[dict[str, Any]]:
    """Parse and validate a Sudoku Exchange text file without solving it."""
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig", newline=None) as source:
        for line_number, raw_line in enumerate(source, 1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            match = SUDOKU_LINE_RE.fullmatch(line)
            if match is None:
                raise ValueError(f"{path}:{line_number}: invalid Sudoku Exchange record")

            source_puzzle = match.group("puzzle")
            source_id = match.group("source_id").lower()
            expected_source_id = hashlib.sha1(source_puzzle.encode("ascii")).hexdigest()[
                :12
            ]
            if source_id != expected_source_id:
                raise ValueError(
                    f"{path}:{line_number}: source hash {source_id!r} does not match "
                    f"puzzle hash {expected_source_id!r}"
                )
            puzzle = source_puzzle
            rating = float(match.group("rating"))
            if not math.isfinite(rating) or rating < 0:
                raise ValueError(f"{path}:{line_number}: invalid rating {rating!r}")
            records.append(
                {
                    "difficulty": difficulty,
                    "puzzle": puzzle,
                    "rating": rating,
                    "source_id": source_id,
                }
            )
    if not records:
        raise ValueError(f"{path}: no Sudoku records found")
    return records


def solve_unique_sudoku(puzzle: str) -> tuple[str | None, int]:
    """Return the first solution and a solution count capped at two."""
    if len(puzzle) != 81 or any(character not in "0123456789" for character in puzzle):
        return None, 0

    board = [int(character) for character in puzzle]
    row_masks = [0] * 9
    column_masks = [0] * 9
    box_masks = [0] * 9
    empty_positions: list[int] = []

    for index, value in enumerate(board):
        if value == 0:
            empty_positions.append(index)
            continue
        row, column = divmod(index, 9)
        box = (row // 3) * 3 + column // 3
        bit = 1 << (value - 1)
        if row_masks[row] & bit or column_masks[column] & bit or box_masks[box] & bit:
            return None, 0
        row_masks[row] |= bit
        column_masks[column] |= bit
        box_masks[box] |= bit

    solution_count = 0
    first_solution: str | None = None

    def search(depth: int) -> None:
        nonlocal first_solution, solution_count
        if solution_count >= 2:
            return
        if depth == len(empty_positions):
            solution_count += 1
            if first_solution is None:
                first_solution = "".join(str(value) for value in board)
            return

        best_offset = -1
        best_candidates = 0
        best_count = 10
        for offset in range(depth, len(empty_positions)):
            index = empty_positions[offset]
            row, column = divmod(index, 9)
            box = (row // 3) * 3 + column // 3
            candidates = FULL_DIGIT_MASK & ~(
                row_masks[row] | column_masks[column] | box_masks[box]
            )
            count = candidates.bit_count()
            if count == 0:
                return
            if count < best_count:
                best_offset = offset
                best_candidates = candidates
                best_count = count
                if count == 1:
                    break

        empty_positions[depth], empty_positions[best_offset] = (
            empty_positions[best_offset],
            empty_positions[depth],
        )
        index = empty_positions[depth]
        row, column = divmod(index, 9)
        box = (row // 3) * 3 + column // 3

        candidates = best_candidates
        while candidates and solution_count < 2:
            bit = candidates & -candidates
            candidates ^= bit
            value = bit.bit_length()
            board[index] = value
            row_masks[row] |= bit
            column_masks[column] |= bit
            box_masks[box] |= bit
            search(depth + 1)
            box_masks[box] ^= bit
            column_masks[column] ^= bit
            row_masks[row] ^= bit
            board[index] = 0

        empty_positions[depth], empty_positions[best_offset] = (
            empty_positions[best_offset],
            empty_positions[depth],
        )

    search(0)
    return first_solution, solution_count


def build_sudoku_bank(directory: Path, limit: int) -> dict[str, Any]:
    """Build a solved, unique Sudoku bank with an equal per-level limit."""
    directory = directory.resolve()
    if not directory.is_dir():
        raise NotADirectoryError(f"Sudoku input is not a directory: {directory}")

    selected: list[dict[str, Any]] = []
    input_files: dict[str, str] = {}
    input_sha256: dict[str, str] = {}
    for difficulty in DIFFICULTIES:
        source_path = find_sudoku_file(directory, difficulty)
        input_files[difficulty] = source_path.name
        input_sha256[difficulty] = sha256_file(source_path)
        candidates = parse_sudoku_file(source_path, difficulty)
        candidates.sort(key=lambda item: (item["rating"], item["source_id"], item["puzzle"]))

        seen_puzzles: set[str] = set()
        difficulty_records: list[dict[str, Any]] = []
        for candidate in candidates:
            if candidate["puzzle"] in seen_puzzles:
                continue
            seen_puzzles.add(candidate["puzzle"])
            solution, solution_count = solve_unique_sudoku(candidate["puzzle"])
            if solution_count != 1 or solution is None:
                raise ValueError(
                    f"{source_path}: puzzle {candidate['source_id']} has "
                    f"{solution_count if solution_count < 2 else 'multiple'} solution(s)"
                )
            difficulty_records.append(
                {
                    "difficulty": difficulty,
                    "puzzle": candidate["puzzle"],
                    "rating": candidate["rating"],
                    "solution": solution,
                    "source": f"sudoku-exchange:{candidate['source_id']}",
                    "source_id": candidate["source_id"],
                }
            )
            if len(difficulty_records) == limit:
                break

        if len(difficulty_records) < limit:
            raise ValueError(
                f"{source_path}: requested {limit} unique puzzles, found "
                f"{len(difficulty_records)}"
            )
        selected.extend(difficulty_records)

    selected.sort(
        key=lambda item: (
            DIFFICULTIES.index(item["difficulty"]),
            item["rating"],
            item["source"],
            item["puzzle"],
        )
    )
    counts = {
        difficulty: sum(record["difficulty"] == difficulty for record in selected)
        for difficulty in DIFFICULTIES
    }
    return {
        "schema_version": 1,
        "metadata": {
            "builder": "backend/scripts/build_external_puzzle_banks.py",
            "counts": counts,
            "input_files": input_files,
            "input_sha256": input_sha256,
            "per_difficulty_limit": limit,
            "source": SUDOKU_SOURCE,
        },
        "puzzles": selected,
    }


def select_idiom_member(archive: zipfile.ZipFile) -> str:
    """Select chinese_idiom.txt without extracting potentially unsafe paths."""
    names = [name for name in archive.namelist() if not name.endswith("/")]
    exact = [name for name in names if Path(name).name == "chinese_idiom.txt"]
    if len(exact) == 1:
        return exact[0]
    text_members = [name for name in names if name.lower().endswith(".txt")]
    if len(text_members) == 1:
        return text_members[0]
    raise ValueError(
        "JioNLP archive must contain chinese_idiom.txt (or exactly one .txt member)"
    )


def numeric_frequency(raw_value: str, location: str) -> int | float:
    """Parse JioNLP's integer-like frequency while allowing future decimals."""
    value = raw_value.strip().replace(",", "")
    if not value:
        return 0
    try:
        parsed = float(value)
    except ValueError as error:
        raise ValueError(f"{location}: invalid idiom frequency {raw_value!r}") from error
    if not math.isfinite(parsed) or parsed < 0:
        raise ValueError(f"{location}: invalid idiom frequency {raw_value!r}")
    return int(parsed) if parsed.is_integer() else parsed


def read_idiom_frequencies(path: Path) -> tuple[dict[str, int | float], str]:
    """Read ``word<TAB>frequency`` records from JioNLP's ZIP archive."""
    if not path.is_file():
        raise FileNotFoundError(f"JioNLP archive not found: {path}")
    frequencies: dict[str, int | float] = {}
    with zipfile.ZipFile(path) as archive:
        member = select_idiom_member(archive)
        with archive.open(member) as binary_source:
            for line_number, raw_line in enumerate(binary_source, 1):
                try:
                    line = raw_line.decode("utf-8-sig").strip()
                except UnicodeDecodeError as error:
                    raise ValueError(
                        f"{path}:{member}:{line_number}: expected UTF-8 text"
                    ) from error
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) != 2:
                    raise ValueError(
                        f"{path}:{member}:{line_number}: expected word<TAB>frequency"
                    )
                word = parts[0].strip()
                if not word:
                    raise ValueError(f"{path}:{member}:{line_number}: empty idiom")
                frequency = numeric_frequency(
                    parts[1], f"{path}:{member}:{line_number}"
                )
                previous = frequencies.get(word)
                if previous is None or frequency > previous:
                    frequencies[word] = frequency
    if not frequencies:
        raise ValueError(f"{path}:{member}: no idiom frequencies found")
    return frequencies, member


def normalized_text(value: Any) -> str:
    """Normalize scalar/list JSON text without inventing missing content."""
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        parts = [normalized_text(part) for part in value]
        return " ".join(part for part in parts if part)
    if not isinstance(value, (str, int, float)):
        return ""
    return " ".join(str(value).strip().split())


def idiom_json_records(payload: Any) -> Iterable[dict[str, Any]]:
    """Yield records from a list, common wrapper, or word-keyed object."""
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                yield item
        return
    if not isinstance(payload, dict):
        raise ValueError("idiom JSON root must be an array or object")

    for container_key in ("data", "idioms", "items", "records"):
        container = payload.get(container_key)
        if isinstance(container, list):
            for item in container:
                if isinstance(item, dict):
                    yield item
            return

    mapping_items = [
        (key, value) for key, value in payload.items() if isinstance(value, dict)
    ]
    if not mapping_items:
        raise ValueError("idiom JSON object contains no recognizable records")
    for key, value in mapping_items:
        record = dict(value)
        record.setdefault("word", key)
        yield record


def first_field(record: dict[str, Any], names: tuple[str, ...]) -> str:
    """Return the first non-empty normalized field from a JSON record."""
    for name in names:
        value = normalized_text(record.get(name))
        if value:
            return value
    return ""


def is_han_character(character: str) -> bool:
    """Match the backend runtime's deliberately narrow common-Han range."""
    return 0x4E00 <= ord(character) <= 0x9FFF


def is_four_han_idiom(word: str) -> bool:
    return len(word) == 4 and all(is_han_character(character) for character in word)


def read_idiom_content(path: Path) -> list[dict[str, str]]:
    """Read definitions and optional pinyin from an idiom JSON file."""
    if not path.is_file():
        raise FileNotFoundError(f"idiom content JSON not found: {path}")
    with path.open("r", encoding="utf-8-sig") as source:
        payload = json.load(source)

    content: list[dict[str, str]] = []
    for raw_record in idiom_json_records(payload):
        word = first_field(raw_record, ("word", "idiom", "name", "成语"))
        clue = first_field(
            raw_record,
            ("explanation", "definition", "meaning", "clue", "释义", "解释"),
        )
        # An answer appearing verbatim in its own clue turns the puzzle into a
        # giveaway. Short fragments are not useful as standalone clues either.
        if (
            not is_four_han_idiom(word)
            or len(clue) < 6
            or word in clue
        ):
            continue
        pinyin = first_field(raw_record, ("pinyin", "pronunciation", "拼音"))
        content.append({"word": word, "clue": clue, "pinyin": pinyin})
    if not content:
        raise ValueError(f"{path}: no four-character idioms with non-empty definitions")
    return content


def build_idiom_bank(
    frequency_zip: Path,
    content_json: Path | None,
    limit: int,
) -> dict[str, Any]:
    """Join JioNLP frequencies to real definitions, filter and deduplicate."""
    frequencies, archive_member = read_idiom_frequencies(frequency_zip.resolve())
    if content_json is None:
        raise ValueError(
            "--idiom-json is required: JioNLP chinese_idiom.zip contains only "
            "word frequencies and has no definitions or pinyin"
        )
    content_records = read_idiom_content(content_json.resolve())

    candidates_by_word: dict[str, list[dict[str, str]]] = {}
    for record in content_records:
        if record["word"] not in frequencies:
            continue
        candidates_by_word.setdefault(record["word"], []).append(record)

    idioms: list[dict[str, Any]] = []
    for word, candidates in candidates_by_word.items():
        # Prefer a pinyin-bearing, more informative clue; lexical tiebreakers
        # make the result independent of source JSON record order.
        candidates.sort(
            key=lambda item: (
                not bool(item["pinyin"]),
                -len(item["clue"]),
                item["clue"],
                item["pinyin"],
            )
        )
        selected = candidates[0]
        idioms.append(
            {
                "clue": selected["clue"],
                "frequency": frequencies[word],
                "pinyin": selected["pinyin"],
                "source_id": hashlib.sha256(word.encode("utf-8")).hexdigest()[:16],
                "word": word,
            }
        )

    idioms.sort(key=lambda item: (-item["frequency"], item["word"], item["clue"]))
    idioms = idioms[:limit]
    if not idioms:
        raise ValueError(
            "JioNLP frequencies and --idiom-json have no matching four-character "
            "idioms with non-empty definitions"
        )

    return {
        "schema_version": 1,
        "metadata": {
            "builder": "backend/scripts/build_external_puzzle_banks.py",
            "content_input_file": content_json.name,
            "count": len(idioms),
            "frequency_input_file": frequency_zip.name,
            "frequency_input_sha256": sha256_file(frequency_zip),
            "frequency_archive_member": archive_member,
            "limit": limit,
            "content_input_sha256": sha256_file(content_json),
            "sources": [JIONLP_SOURCE, IDIOM_CONTENT_SOURCE],
        },
        "idioms": idioms,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build verified external Sudoku and idiom JSON banks offline."
    )
    parser.add_argument(
        "--sudoku-dir",
        required=True,
        type=Path,
        help="directory containing sudoku-easy.txt/easy.txt and medium/hard equivalents",
    )
    parser.add_argument(
        "--idiom-zip",
        required=True,
        type=Path,
        help="JioNLP chinese_idiom.zip (word-frequency source)",
    )
    parser.add_argument(
        "--idiom-json",
        type=Path,
        help="idiom JSON with real definitions/pinyin (for example idiom-database)",
    )
    parser.add_argument(
        "--sudoku-output",
        type=Path,
        default=DEFAULT_SUDOKU_OUTPUT,
        help=f"output path (default: {DEFAULT_SUDOKU_OUTPUT})",
    )
    parser.add_argument(
        "--idiom-output",
        type=Path,
        default=DEFAULT_IDIOM_OUTPUT,
        help=f"output path (default: {DEFAULT_IDIOM_OUTPUT})",
    )
    parser.add_argument(
        "--sudoku-limit",
        type=positive_int,
        default=1000,
        help="records required per Sudoku difficulty (default: 1000)",
    )
    parser.add_argument(
        "--idiom-limit",
        type=positive_int,
        default=3000,
        help=(
            "maximum idiom records (default: 3000; the importer needs 2000 "
            "non-overlapping answers after filtering built-in content)"
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.idiom_json is None:
        raise ValueError(
            "--idiom-json is required: JioNLP chinese_idiom.zip contains only "
            "word frequencies and has no definitions or pinyin"
        )
    sudoku_bank = build_sudoku_bank(args.sudoku_dir, args.sudoku_limit)
    idiom_bank = build_idiom_bank(args.idiom_zip, args.idiom_json, args.idiom_limit)
    atomic_write_json(args.sudoku_output, sudoku_bank)
    atomic_write_json(args.idiom_output, idiom_bank)
    print(
        json.dumps(
            {
                "idiom_count": idiom_bank["metadata"]["count"],
                "idiom_output": str(args.idiom_output.resolve()),
                "sudoku_counts": sudoku_bank["metadata"]["counts"],
                "sudoku_output": str(args.sudoku_output.resolve()),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, json.JSONDecodeError, zipfile.BadZipFile) as error:
        raise SystemExit(f"error: {error}") from error
