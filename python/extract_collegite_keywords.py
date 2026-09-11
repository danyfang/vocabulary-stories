import argparse
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


ENTRY_PATTERN = re.compile(r"(?<!\d)\d+\.\s+(.+?)(?=\s*\d+\.\s|\s*$)", re.MULTILINE)
WORD_PATTERN = re.compile(r"[^\W\d_]+(?:[-' ][^\W\d_]+)*")


def extract_keywords(pdf_path: Path) -> list[str]:
    with tempfile.NamedTemporaryFile(suffix=".xml") as xml_file:
        subprocess.run(
            ["pdftohtml", "-xml", "-hidden", "-q", str(pdf_path), xml_file.name],
            check=True,
        )
        root = ET.parse(xml_file.name).getroot()

    keywords = []
    for page in root.findall("page"):
        nodes = page.findall("text")
        for index, node in enumerate(nodes):
            if node.get("font") != "2" or node.find("b") is None:
                continue

            text = "".join(node.itertext()).strip()
            if index > 0:
                previous = nodes[index - 1]
                same_line = abs(int(previous.get("top")) - int(node.get("top"))) <= 2
                if previous.get("font") == "3" and "".join(previous.itertext()).strip() == "-" and same_line:
                    keywords[-1] += f"-{text}"
                    continue
            keywords.append(text)

    malformed = [keyword for keyword in keywords if WORD_PATTERN.fullmatch(keyword) is None]
    if malformed:
        raise ValueError(f"Malformed extracted keywords: {malformed}")

    return list(dict.fromkeys(keywords))


def format_blocks(keywords: list[str]) -> str:
    lines = []
    for block_start in range(0, len(keywords), 100):
        block = keywords[block_start : block_start + 100]
        columns = [block[start : start + 20] for start in range(0, len(block), 20)]
        for row in range(20):
            entries = []
            for column_index, column in enumerate(columns):
                if row < len(column):
                    entry = f"{row + 1}. {column[row]}"
                    if column_index < len(columns) - 1:
                        entry = f"{entry:<20}"
                    entries.append(entry)
            if entries:
                lines.append("".join(entries).rstrip())
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("word_list", type=Path)
    parser.add_argument("--append", action="store_true")
    parser.add_argument("--max-word-length", type=int)
    args = parser.parse_args()

    existing_text = args.word_list.read_text(encoding="utf-8")
    existing = {word.strip().casefold() for word in ENTRY_PATTERN.findall(existing_text)}
    keywords = extract_keywords(args.pdf)
    missing = [keyword for keyword in keywords if keyword.casefold() not in existing]
    if args.max_word_length is not None:
        missing = [keyword for keyword in missing if len(keyword) <= args.max_word_length]

    print(f"Extracted {len(keywords)} unique bold keywords; {len(missing)} are missing.")
    if not args.append:
        print("First missing:", ", ".join(missing[:20]))
        print("Last missing:", ", ".join(missing[-20:]))
        return

    if missing:
        separator = "\n" if existing_text.endswith("\n\n") else "\n\n"
        with args.word_list.open("a", encoding="utf-8") as word_list:
            word_list.write(separator + format_blocks(missing))


if __name__ == "__main__":
    main()