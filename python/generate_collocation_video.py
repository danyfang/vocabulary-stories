#!/usr/bin/env python3

import argparse
import asyncio
import re
import shutil
import subprocess
import tempfile
import textwrap
from pathlib import Path

import edge_tts


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "collocation.md"
DEFAULT_OUTPUT_DIRECTORY = Path.home() / "Videos" / "gre"
VOICE = "en-US-GuyNeural"
CHINESE_VOICE = "zh-CN-YunxiNeural"
SPEECH_RATE = "+5%"
TTS_RETRIES = 20
FRAME_SIZE = "1920x1080"
FRAME_RATE = 2
ENTRIES_PER_SLIDE = 5
BODY_FONT = Path("/System/Library/Fonts/HelveticaNeue.ttc")
CHINESE_FONT = Path("/System/Library/Fonts/STHeiti Medium.ttc")


def parse_lists(text: str) -> dict[int, list[tuple[str, str]]]:
    lists: dict[int, list[tuple[str, str]]] = {}
    current_list: int | None = None
    for line_number, line in enumerate(text.splitlines(), start=1):
        heading = re.fullmatch(r"## List (\d+)", line)
        if heading:
            current_list = int(heading.group(1))
            lists[current_list] = []
            continue
        entry = re.fullmatch(r"(?:-|\d+\.) (.+?) — (.+)", line)
        if not entry:
            continue
        if current_list is None:
            raise ValueError(f"Malformed entry at line {line_number}: {line}")
        english, chinese = entry.groups()
        lists[current_list].append((english.strip(), chinese.strip()))
    return lists


def wrap_entry(text: str, width: int) -> str:
    return "\n".join(
        textwrap.wrap(
            text,
            width=width,
            break_long_words=False,
            break_on_hyphens=False,
        )
    )


def ffmpeg_text_path(path: Path) -> str:
    return str(path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def probe_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


async def synthesize_entries(
    entries: list[tuple[str, str]], temporary_path: Path
) -> list[tuple[Path, Path]]:
    temporary_path.mkdir(parents=True, exist_ok=True)

    async def synthesize(text: str, voice: str, output_path: Path) -> None:
        for attempt in range(1, TTS_RETRIES + 1):
            try:
                await edge_tts.Communicate(text, voice, rate=SPEECH_RATE).save(
                    str(output_path)
                )
                if output_path.exists() and output_path.stat().st_size > 0:
                    return
            except edge_tts.exceptions.NoAudioReceived:
                if attempt == TTS_RETRIES:
                    raise
            await asyncio.sleep(min(attempt * 2, 30))

    audio_pairs = []
    for index, (english, chinese) in enumerate(entries, start=1):
        english_path = temporary_path / f"entry-{index}-en.mp3"
        chinese_path = temporary_path / f"entry-{index}-zh.mp3"
        await synthesize(english, VOICE, english_path)
        await synthesize(chinese, CHINESE_VOICE, chinese_path)
        audio_pairs.append((english_path, chinese_path))
    return audio_pairs


def assemble_slide_audio(
    audio_pairs: list[tuple[Path, Path]], output_path: Path, temporary_path: Path
) -> None:
    short_pause = temporary_path / "pause-short.mp3"
    long_pause = temporary_path / "pause-long.mp3"
    for duration, path in ((0.3, short_pause), (0.8, long_pause)):
        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "anullsrc=r=24000:cl=mono",
                "-t",
                str(duration),
                "-c:a",
                "libmp3lame",
                "-b:a",
                "48k",
                str(path),
            ],
            check=True,
        )

    sequence = []
    for english_path, chinese_path in audio_pairs:
        sequence.extend(
            [
                english_path,
                short_pause,
                chinese_path,
                short_pause,
                english_path,
                short_pause,
                english_path,
                short_pause,
                english_path,
                long_pause,
            ]
        )
    concat_path = temporary_path / "audio-segments.txt"
    concat_path.write_text(
        "".join(f"file '{path}'\n" for path in sequence), encoding="utf-8"
    )
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_path),
            "-c",
            "copy",
            str(output_path),
        ],
        check=True,
    )


def render_slide(
    list_number: int,
    slide_number: int,
    slide_count: int,
    entries: list[tuple[str, str]],
    audio_path: Path,
    output_path: Path,
    temporary_path: Path,
) -> None:
    duration = probe_duration(audio_path)
    filters = [
        "drawbox=x=0:y=0:w=1920:h=18:color=#c94735:t=fill",
        "drawbox=x=116:y=112:w=10:h=856:color=#c94735:t=fill",
        (
            f"drawtext=fontfile='{ffmpeg_text_path(BODY_FONT)}':"
            f"text='GRE COLLOCATIONS  /  LIST {list_number:02d}':"
            "x=164:y=94:fontsize=28:fontcolor=#b43c2e"
        ),
        (
            f"drawtext=fontfile='{ffmpeg_text_path(BODY_FONT)}':"
            f"text='{slide_number} / {slide_count}':"
            "x=w-tw-140:y=98:fontsize=25:fontcolor=#68716d"
        ),
    ]

    row_height = 158
    for index, (english, chinese) in enumerate(entries):
        row_number = index + 1
        y = 190 + index * row_height
        english_path = temporary_path / f"slide-{slide_number}-en-{row_number}.txt"
        chinese_path = temporary_path / f"slide-{slide_number}-zh-{row_number}.txt"
        english_path.write_text(wrap_entry(english, 58), encoding="utf-8")
        chinese_path.write_text(wrap_entry(chinese, 29), encoding="utf-8")
        filters.extend(
            [
                (
                    f"drawtext=fontfile='{ffmpeg_text_path(BODY_FONT)}':"
                    f"text='{(slide_number - 1) * ENTRIES_PER_SLIDE + row_number:02d}':"
                    f"x=164:y={y + 5}:fontsize=24:fontcolor=#c94735"
                ),
                (
                    f"drawtext=fontfile='{ffmpeg_text_path(BODY_FONT)}':"
                    f"textfile='{ffmpeg_text_path(english_path)}':"
                    f"x=235:y={y}:fontsize=40:fontcolor=#18211f:line_spacing=8:expansion=none"
                ),
                (
                    f"drawtext=fontfile='{ffmpeg_text_path(CHINESE_FONT)}':"
                    f"textfile='{ffmpeg_text_path(chinese_path)}':"
                    f"x=1070:y={y + 4}:fontsize=34:fontcolor=#43504c:line_spacing=8:expansion=none"
                ),
                f"drawbox=x=164:y={y + 112}:w=1615:h=1:color=#d8d5cc:t=fill",
            ]
        )

    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=#f5f2e9:s={FRAME_SIZE}:r={FRAME_RATE}:d={duration:.3f}",
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
            str(output_path),
        ],
        check=True,
    )


def generate_video(
    list_number: int,
    entries: list[tuple[str, str]],
    output_path: Path,
) -> None:
    slides = [
        entries[index : index + ENTRIES_PER_SLIDE]
        for index in range(0, len(entries), ENTRIES_PER_SLIDE)
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path = output_path.parent / ".gre-video-cache" / output_path.stem
    cache_path.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="collocation-video-") as directory:
        temporary_path = Path(directory)
        segment_paths: list[Path] = []
        for slide_number, slide_entries in enumerate(slides, start=1):
            segment_path = cache_path / f"slide-{slide_number:03d}.mp4"
            if segment_path.exists() and segment_path.stat().st_size > 0:
                segment_paths.append(segment_path)
                print(
                    f"Reused slide {slide_number}/{len(slides)}",
                    flush=True,
                )
                continue
            audio_path = temporary_path / f"slide-{slide_number}.mp3"
            audio_pairs = asyncio.run(
                synthesize_entries(slide_entries, temporary_path / f"audio-{slide_number}")
            )
            assemble_slide_audio(
                audio_pairs, audio_path, temporary_path / f"audio-{slide_number}"
            )
            render_slide(
                list_number,
                slide_number,
                len(slides),
                slide_entries,
                audio_path,
                segment_path,
                temporary_path,
            )
            segment_paths.append(segment_path)
            print(f"Rendered slide {slide_number}/{len(slides)}", flush=True)

        concat_path = temporary_path / "segments.txt"
        concat_path.write_text(
            "".join(f"file '{path}'\n" for path in segment_paths), encoding="utf-8"
        )
        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_path),
                "-c",
                "copy",
                str(output_path),
            ],
            check=True,
        )
    shutil.rmtree(cache_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate narrated collocation videos.")
    parser.add_argument("list_number", type=int, help="first list number to render")
    parser.add_argument("end_list", type=int, nargs="?", help="last list number")
    parser.add_argument("--limit", type=int, help="render only the first N entries")
    parser.add_argument("--output-directory", type=Path, default=DEFAULT_OUTPUT_DIRECTORY)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        parser.error("ffmpeg and ffprobe are required")
    if not BODY_FONT.exists() or not CHINESE_FONT.exists():
        parser.error("required macOS fonts are unavailable")

    lists = parse_lists(SOURCE.read_text(encoding="utf-8"))
    end_list = args.end_list if args.end_list is not None else args.list_number
    if args.list_number > end_list:
        parser.error("list_number must not be greater than end_list")
    missing = [number for number in range(args.list_number, end_list + 1) if number not in lists]
    if missing:
        parser.error(f"Lists not found: {missing}")
    if args.limit is not None and args.list_number != end_list:
        parser.error("--limit can only be used with one list")
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be at least 1")

    output_directory = args.output_directory.expanduser()
    completed = 0
    skipped = 0
    for list_number in range(args.list_number, end_list + 1):
        entries = lists[list_number]
        if args.limit is not None:
            entries = entries[: args.limit]
        suffix = f"-sample-{len(entries)}" if args.limit is not None else ""
        output_path = output_directory / f"gre-list-{list_number:02d}{suffix}.mp4"
        if output_path.exists() and output_path.stat().st_size > 0 and not args.overwrite:
            skipped += 1
            print(f"Skipped existing {output_path}", flush=True)
            continue
        print(
            f"Generating List {list_number}/{end_list} ({len(entries)} entries)",
            flush=True,
        )
        generate_video(list_number, entries, output_path)
        completed += 1
        print(f"Generated {output_path}", flush=True)
    print(f"Completed {completed}; skipped {skipped}", flush=True)


if __name__ == "__main__":
    main()