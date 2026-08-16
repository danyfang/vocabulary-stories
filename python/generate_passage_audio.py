import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


def parse_passages(book_path: Path) -> dict[int, tuple[str, str]]:
    text = book_path.read_text()
    matches = list(re.finditer(r"^## (\d+)\. (.+)$", text, re.MULTILINE))
    passages = {}

    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = " ".join(
            line.strip()
            for line in text[match.end() : end].splitlines()
            if line.strip()
        )
        passages[int(match.group(1))] = (match.group(2), body)

    return passages


def generate_batch(
    passages: dict[int, tuple[str, str]], start: int, output_path: Path
) -> None:
    spoken_passages = []
    for number in range(start, start + 4):
        title, body = passages[number]
        spoken_passages.append(
            f"Passage {number}. {title}. [[slnc 1000]] {body}"
        )

    spoken_text = " [[slnc 2000]] ".join(spoken_passages)
    with tempfile.NamedTemporaryFile(suffix=".aiff", delete=False) as audio_file:
        aiff_path = audio_file.name

    try:
        subprocess.run(["say", "-o", aiff_path, spoken_text], check=True)
        subprocess.run(
            [
                "ffmpeg",
                "-loglevel",
                "error",
                "-y",
                "-i",
                aiff_path,
                "-codec:a",
                "libmp3lame",
                "-q:a",
                "2",
                str(output_path),
            ],
            check=True,
        )
    finally:
        os.unlink(aiff_path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("start", type=int, nargs="?", default=41)
    parser.add_argument("end", type=int, nargs="?", default=200)
    args = parser.parse_args()

    if (args.start - 1) % 4 != 0 or args.end % 4 != 0 or args.start > args.end:
        parser.error("range must contain complete four-passage batches")
    if not shutil.which("say") or not shutil.which("ffmpeg"):
        parser.error("macOS say and ffmpeg are required")

    root = Path(__file__).resolve().parent
    passages = parse_passages(root / "book.md")
    missing = [number for number in range(args.start, args.end + 1) if number not in passages]
    if missing:
        parser.error(f"missing passages: {missing}")

    output_dir = root / "book"
    output_dir.mkdir(exist_ok=True)
    for start in range(args.start, args.end + 1, 4):
        unit = (start - 1) // 4 + 1
        output_path = output_dir / f"passage-unit-{unit:02d}.mp3"
        generate_batch(passages, start, output_path)
        print(f"Generated unit {unit:02d}: passages {start}-{start + 3}", flush=True)


if __name__ == "__main__":
    main()