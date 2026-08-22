#!/usr/bin/env python3

import argparse
import math
import re
import shutil
import subprocess
import tempfile
import textwrap
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path

from generate_recite_reader import parse_stories


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "recite.md"
AUDIO_DIRECTORY = ROOT / "stories"
DEFAULT_OUTPUT_DIRECTORY = Path.home() / "Downloads" / "video-stories"
STORIES_PER_BATCH = 5
FRAME_SIZE = "1920x1080"
FRAME_RATE = 2
BODY_FONT = Path("/System/Library/Fonts/Avenir Next.ttc")
TITLE_FONT = Path("/System/Library/Fonts/Supplemental/Georgia Bold.ttf")


@lru_cache
def find_batch_segments(
    batch: int,
) -> tuple[
    Path,
    tuple[tuple[float, float], ...],
    tuple[tuple[float, float], ...],
]:
    audio_path = AUDIO_DIRECTORY / f"story-unit-{batch:03d}.mp3"
    if not audio_path.exists():
        raise SystemExit(f"Missing audio file: {audio_path}")

    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(audio_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    duration = float(probe.stdout.strip())
    detection = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i",
            str(audio_path),
            "-af",
            "silencedetect=noise=-40dB:d=0.15",
            "-f",
            "null",
            "-",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    silence_starts = [
        float(value)
        for value in re.findall(r"silence_start: ([0-9.]+)", detection.stderr)
    ]
    silence_ends = [
        float(value)
        for value in re.findall(r"silence_end: ([0-9.]+)", detection.stderr)
    ]
    silences = list(zip(silence_starts, silence_ends, strict=True))
    if not silences:
        raise SystemExit(f"Could not detect story boundaries in {audio_path.name}")

    separators = [
        (start, end) for start, end in silences[1:] if end - start >= 2.8
    ]
    starts = [silences[0][1], *(end for _, end in separators)]
    ends = [start for start, _ in separators]
    segments = tuple(
        (start, ends[index] if index < len(ends) else duration)
        for index, start in enumerate(starts)
    )
    return audio_path, segments, tuple(silences)


def find_audio_segment(story_number: int) -> tuple[Path, float, float]:
    batch = math.ceil(story_number / STORIES_PER_BATCH)
    audio_path, segments, _ = find_batch_segments(batch)
    offset = (story_number - 1) % STORIES_PER_BATCH
    if offset >= len(segments):
        raise SystemExit(f"Could not find Story {story_number} in {audio_path.name}")
    start, end = segments[offset]
    return audio_path, start, end


def wrap_text(text: str, width: int = 70) -> list[str]:
    return textwrap.wrap(
        text,
        width=width,
        break_long_words=False,
        break_on_hyphens=False,
    )


def paginate(text: str, width: int = 70, lines_per_page: int = 7) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    pages: list[str] = []
    current_sentences: list[str] = []

    for sentence in sentences:
        candidate = " ".join([*current_sentences, sentence])
        if current_sentences and len(wrap_text(candidate, width)) > lines_per_page:
            pages.append("\n".join(wrap_text(" ".join(current_sentences), width)))
            current_sentences = []

        sentence_lines = wrap_text(sentence, width)
        if not current_sentences and len(sentence_lines) > lines_per_page:
            pages.extend(
                "\n".join(sentence_lines[index : index + lines_per_page])
                for index in range(0, len(sentence_lines), lines_per_page)
            )
        else:
            current_sentences.append(sentence)

    if current_sentences:
        pages.append("\n".join(wrap_text(" ".join(current_sentences), width)))
    return pages


def spoken_weight(text: str) -> int:
    return sum(len(word) for word in re.findall(r"[\w'-]+", text))


def find_page_times(
    story_number: int, pages: list[str], duration: float
) -> list[tuple[float, float]]:
    if len(pages) == 1:
        return [(0.0, duration)]

    batch = math.ceil(story_number / STORIES_PER_BATCH)
    _, _, batch_silences = find_batch_segments(batch)
    _, audio_start, audio_end = find_audio_segment(story_number)
    local_silences = [
        (start - audio_start, end - audio_start)
        for start, end in batch_silences
        if audio_start < start < audio_end
    ]

    intro_end = 0.0
    for index, (start, end) in enumerate(local_silences[:-1]):
        if end - start >= 1.5:
            intro_end = local_silences[index + 1][1]
            break

    page_weights = [spoken_weight(page) for page in pages]
    total_weight = sum(page_weights)
    boundaries = []
    cumulative_weight = 0
    for index, page in enumerate(pages[:-1]):
        cumulative_weight += page_weights[index]
        predicted = intro_end + (duration - intro_end) * cumulative_weight / total_weight
        if re.search(r"[.!?][\"']?$", page.rstrip()):
            nearby_pauses = [
                start
                for start, end in local_silences
                if end - start >= 0.45 and abs(start - predicted) <= 2.5
            ]
            if nearby_pauses:
                predicted = min(nearby_pauses, key=lambda start: abs(start - predicted))
        boundaries.append(predicted)

    starts = [0.0, *boundaries]
    ends = [*boundaries, duration]
    return list(zip(starts, ends, strict=True))


def ffmpeg_text_path(path: Path) -> str:
    return str(path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def generate_video(story: dict[str, str | int], output_path: Path) -> None:
    story_number = int(story["number"])
    audio_path, audio_start, audio_end = find_audio_segment(story_number)
    duration = audio_end - audio_start
    pages = paginate(str(story["story"]))
    page_times = find_page_times(story_number, pages, duration)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="story-video-") as temporary_directory:
        temporary_path = Path(temporary_directory)
        title_path = temporary_path / "title.txt"
        title_path.write_text(str(story["title"]), encoding="utf-8")
        page_paths = []
        for index, page in enumerate(pages, start=1):
            page_path = temporary_path / f"page-{index}.txt"
            page_path.write_text(page, encoding="utf-8")
            page_paths.append(page_path)

        filters = [
            "drawbox=x=0:y=0:w=1920:h=16:color=#b83b2d:t=fill",
            "drawbox=x=140:y=122:w=8:h=796:color=#b83b2d:t=fill",
            (
                f"drawtext=fontfile='{ffmpeg_text_path(BODY_FONT)}':"
                f"text='STORY {story_number:04d}':x=180:y=120:fontsize=28:"
                "fontcolor=#b83b2d"
            ),
            (
                f"drawtext=fontfile='{ffmpeg_text_path(TITLE_FONT)}':"
                f"textfile='{ffmpeg_text_path(title_path)}':x=180:y=174:fontsize=62:"
                "fontcolor=#18211f:line_spacing=10:expansion=none"
            ),
        ]
        for index, (page_path, (page_start, page_end)) in enumerate(
            zip(page_paths, page_times, strict=True)
        ):
            filters.append(
                f"drawtext=fontfile='{ffmpeg_text_path(BODY_FONT)}':"
                f"textfile='{ffmpeg_text_path(page_path)}':x=180:y=330:fontsize=42:"
                "fontcolor=#25312e:line_spacing=22:expansion=none:"
                f"enable='between(t,{page_start:.3f},{page_end:.3f})'"
            )
            if len(page_paths) > 1:
                filters.append(
                    f"drawtext=fontfile='{ffmpeg_text_path(BODY_FONT)}':"
                    f"text='{index + 1} / {len(page_paths)}':x=w-tw-180:y=h-105:"
                    "fontsize=24:fontcolor=#66706d:"
                    f"enable='between(t,{page_start:.3f},{page_end:.3f})'"
                )

        command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=#f5f2e9:s={FRAME_SIZE}:r={FRAME_RATE}:d={duration:.3f}",
            "-ss",
            f"{audio_start:.3f}",
            "-t",
            f"{duration:.3f}",
            "-i",
            str(audio_path),
            "-vf",
            ",".join(filters),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            "-shortest",
            str(output_path.with_suffix(".tmp.mp4")),
        ]
        subprocess.run(command, check=True)
        output_path.with_suffix(".tmp.mp4").replace(output_path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate narrated MP4 files from recite.md."
    )
    parser.add_argument("start", type=int, help="first story number")
    parser.add_argument("end", type=int, nargs="?", help="last story number")
    parser.add_argument("--output-directory", type=Path, default=DEFAULT_OUTPUT_DIRECTORY)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--jobs", type=int, default=1, help="parallel video encoders")
    args = parser.parse_args()

    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        parser.error("ffmpeg and ffprobe are required")
    if not BODY_FONT.exists() or not TITLE_FONT.exists():
        parser.error("required macOS fonts are unavailable")

    stories = parse_stories(SOURCE.read_text(encoding="utf-8"))
    end = args.end if args.end is not None else args.start
    if args.start > end:
        parser.error("start must not be greater than end")
    if args.jobs < 1:
        parser.error("jobs must be at least 1")
    selected = [story for story in stories if args.start <= story["number"] <= end]
    if len(selected) != end - args.start + 1:
        parser.error(f"Stories {args.start}-{end} were not all found in {SOURCE.name}")

    output_directory = args.output_directory.expanduser()
    pending = []
    skipped = 0
    for story in selected:
        story_number = int(story["number"])
        output_path = output_directory / f"story-{story_number:04d}.mp4"
        if output_path.exists() and output_path.stat().st_size > 0 and not args.overwrite:
            skipped += 1
            continue
        pending.append((story, output_path))

    def generate(item: tuple[dict[str, str | int], Path]) -> Path:
        story, output_path = item
        generate_video(story, output_path)
        return output_path

    print(f"Skipping {skipped} existing; generating {len(pending)} videos", flush=True)
    with ThreadPoolExecutor(max_workers=args.jobs) as executor:
        for index, output_path in enumerate(executor.map(generate, pending), start=1):
            if index % 25 == 0 or index == len(pending):
                print(f"[{index}/{len(pending)}] Generated through {output_path.name}", flush=True)


if __name__ == "__main__":
    main()