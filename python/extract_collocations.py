#!/usr/bin/env python3

import argparse
import glob
import json
import re
from collections import defaultdict
from pathlib import Path


HAN_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
LATIN_RE = re.compile(r"[A-Za-z]")
PRONUNCIATION_RE = re.compile(r"\s*[\[［【].*$")
TRAILING_PRONUNCIATION_RE = re.compile(r"\s+\S{1,30}[\]］】）)]\s*$")
SPACE_RE = re.compile(r"\s+")

MIN_ENGLISH_HEIGHT = 0.0144
MIN_CHINESE_HEIGHT = 0.0140
MAX_PAIR_GAP = 0.013
MAX_LINE_GAP = 0.009
MAX_X_DELTA = 0.09

CONFIRMED_TRANSLATIONS = {
    "Never abase yourself!": "不要自卑！",
    "stop in abeyance": "暂停/中止",
    "abide by the rules": "遵守规则",
}


def load_rows(patterns: list[str]) -> list[dict]:
    paths: list[str] = []
    for pattern in patterns:
        matches = glob.glob(pattern)
        paths.extend(matches or [pattern])

    rows_by_identity: dict[tuple, dict] = {}
    for path in sorted(set(paths)):
        with open(path, encoding="utf-8") as source:
            for line in source:
                if not line.strip():
                    continue
                row = json.loads(line)
                identity = (
                    row["page"],
                    row["x"],
                    row["y"],
                    row["w"],
                    row["h"],
                    row["text"],
                )
                rows_by_identity[identity] = row
    return list(rows_by_identity.values())


def column(row: dict) -> int:
    return 0 if row["x"] < 0.5 else 1


def is_english_heading(row: dict) -> bool:
    text = row["text"]
    return (
        row["h"] >= MIN_ENGLISH_HEIGHT
        and row["y"] >= 0.03
        and bool(LATIN_RE.search(text))
        and not text.startswith("List ")
        and "DoDown" not in text
    )


def is_chinese_heading(row: dict) -> bool:
    return (
        row["h"] >= MIN_CHINESE_HEIGHT
        and row["y"] >= 0.03
        and bool(HAN_RE.search(row["text"]))
    )


def vertical_gap(upper: dict, lower: dict) -> float:
    return upper["y"] - (lower["y"] + lower["h"])


def is_adjacent(upper: dict, lower: dict, max_gap: float) -> bool:
    gap = vertical_gap(upper, lower)
    return (
        -0.007 <= gap <= max_gap
        and abs(upper["x"] - lower["x"]) <= MAX_X_DELTA
        and column(upper) == column(lower)
    )


def clean_english(text: str) -> str:
    text = SPACE_RE.sub(" ", text.replace("|", " ")).strip()
    text = PRONUNCIATION_RE.sub("", text).strip()
    text = TRAILING_PRONUNCIATION_RE.sub("", text).strip()
    text = re.sub(r"\btakenaback\b", "taken aback", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return text


def clean_chinese(text: str) -> str:
    text = SPACE_RE.sub("", text).strip()
    text = PRONUNCIATION_RE.sub("", text).strip()
    text = re.sub(r"(?<=[\u3400-\u4dbf\u4e00-\u9fff])[A-Za-z][A-Za-z:;'.,\[\]［］()（）]*$", "", text)
    return text


def extract_entries(rows: list[dict]) -> dict[int, list[tuple[str, str]]]:
    by_page_column: dict[tuple[int, int], list[dict]] = defaultdict(list)
    for row in rows:
        by_page_column[(row["page"], column(row))].append(row)

    entries: dict[int, list[tuple[str, str]]] = defaultdict(list)
    for (page, page_column), page_rows in sorted(by_page_column.items()):
        del page_column
        ordered = sorted(page_rows, key=lambda row: (-row["y"], row["x"]))
        used_chinese: set[int] = set()

        for chinese_index, chinese in enumerate(ordered):
            if chinese_index in used_chinese or not is_chinese_heading(chinese):
                continue

            english_candidates = [
                (index, row)
                for index, row in enumerate(ordered)
                if index < chinese_index
                and is_english_heading(row)
                and is_adjacent(row, chinese, MAX_PAIR_GAP)
            ]
            if not english_candidates:
                continue

            closest_gap = min(
                abs(vertical_gap(row, chinese)) for _, row in english_candidates
            )
            closest_candidates = [
                item
                for item in english_candidates
                if abs(vertical_gap(item[1], chinese)) <= closest_gap + 0.004
            ]
            english_only = [
                item for item in closest_candidates if item[1].get("lang") == "en"
            ]
            bilingual = [
                item
                for item in closest_candidates
                if item[1].get("lang") != "en"
            ]
            english_index, english = min(
                english_only or bilingual,
                key=lambda item: abs(vertical_gap(item[1], chinese)),
            )
            if english_only and bilingual and not re.search(r"[\[［【]", english["text"]):
                marked_bilingual = [
                    item for item in bilingual if re.search(r"[\[［【]", item[1]["text"])
                ]
                if marked_bilingual:
                    english_index, english = min(
                        marked_bilingual,
                        key=lambda item: abs(vertical_gap(item[1], chinese)),
                    )

            english_lines = [english]
            scan_index = english_index - 1
            while scan_index >= 0:
                previous = ordered[scan_index]
                if (
                    is_english_heading(previous)
                    and previous.get("lang") == english.get("lang")
                    and is_adjacent(previous, english_lines[0], MAX_LINE_GAP)
                ):
                    english_lines.insert(0, previous)
                    scan_index -= 1
                    continue
                break

            chinese_lines = [chinese]
            used_chinese.add(chinese_index)
            scan_index = chinese_index + 1
            while scan_index < len(ordered):
                following = ordered[scan_index]
                if is_chinese_heading(following) and is_adjacent(
                    chinese_lines[-1], following, MAX_LINE_GAP
                ):
                    chinese_lines.append(following)
                    used_chinese.add(scan_index)
                    scan_index += 1
                    continue
                break

            english_text = clean_english(" ".join(row["text"] for row in english_lines))
            chinese_text = clean_chinese("".join(row["text"] for row in chinese_lines))
            if english_text and chinese_text:
                chinese_text = CONFIRMED_TRANSLATIONS.get(english_text, chinese_text)
                entries[page].append((english_text, chinese_text))

    return entries


def render_markdown(entries: dict[int, list[tuple[str, str]]], page_count: int) -> str:
    lines = ["# Collocations", ""]
    for page in range(1, page_count + 1):
        page_entries = entries.get(page, [])
        if not page_entries:
            continue
        lines.extend((f"## Page {page}", ""))
        seen: set[tuple[str, str]] = set()
        for english, chinese in page_entries:
            if (english, chinese) in seen:
                continue
            seen.add((english, chinese))
            lines.append(f"- **{english}** — {chinese}")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+")
    parser.add_argument("--output", required=True)
    parser.add_argument("--page-count", type=int, default=698)
    args = parser.parse_args()

    rows = load_rows(args.inputs)
    entries = extract_entries(rows)
    Path(args.output).write_text(
        render_markdown(entries, args.page_count),
        encoding="utf-8",
    )
    print(
        f"extracted {sum(map(len, entries.values()))} entries "
        f"from {len(entries)} pages"
    )


if __name__ == "__main__":
    main()