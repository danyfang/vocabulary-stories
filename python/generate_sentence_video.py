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
SOURCE = ROOT / "sentence.md"
DEFAULT_OUTPUT = Path.home() / "Video" / "sentences.mp4"
VOICE = "en-US-GuyNeural"
SPEECH_RATE = "+0%"
TTS_RETRIES = 20
PAUSE_SECONDS = 1.0
FRAME_SIZE = "1920x1080"
FRAME_RATE = 2
BODY_FONT = Path("/System/Library/Fonts/Avenir Next.ttc")
TITLE_FONT = Path("/System/Library/Fonts/Supplemental/Georgia Bold.ttf")
ENGLISH_PUNCTUATION = str.maketrans(
    {
        "（": "(",
        "）": ")",
        "，": ",",
        "：": ":",
        "；": ";",
        "？": "?",
    }
)


def normalize_english_punctuation(sentence: str) -> str:
    sentence = sentence.translate(ENGLISH_PUNCTUATION)
    sentence = re.sub(r"\s*([,;:])\s*", r"\1 ", sentence)
    sentence = re.sub(r"\s+([.!?])", r"\1", sentence)
    sentence = re.sub(r"\(\s+", "(", sentence)
    sentence = re.sub(r"\s+\)", ")", sentence)
    sentence = re.sub(r"\)(?=[A-Za-z])", ") ", sentence)
    return sentence.strip()


def parse_sentences(text: str) -> list[tuple[int, str]]:
    entries = [
        (int(number), normalize_english_punctuation(sentence))
        for number, sentence in re.findall(r"(?m)^(\d+)\. (.+)$", text)
    ]
    numbers = [number for number, _ in entries]
    if numbers != list(range(1, len(entries) + 1)):
        raise ValueError("sentence numbers must be consecutive and start at 1")
    if not entries:
        raise ValueError("no numbered sentences found")
    return entries


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


def sentence_layout(sentence: str) -> tuple[str, int, int]:
    layouts = ((56, 50, 8), (50, 58, 9), (44, 67, 10), (38, 78, 12), (34, 88, 14))
    for font_size, width, maximum_lines in layouts:
        lines = textwrap.wrap(
            sentence,
            width=width,
            break_long_words=False,
            break_on_hyphens=False,
        )
        if len(lines) <= maximum_lines:
            line_spacing = 16
            text_height = len(lines) * font_size + max(0, len(lines) - 1) * line_spacing
            return "\n".join(lines), font_size, max(245, (1080 - text_height) // 2)
    raise ValueError("sentence is too long to fit on one slide")


async def synthesize(sentence: str, output_path: Path) -> None:
    for attempt in range(1, TTS_RETRIES + 1):
        try:
            await edge_tts.Communicate(sentence, VOICE, rate=SPEECH_RATE).save(
                str(output_path)
            )
            if output_path.exists() and output_path.stat().st_size > 0:
                return
        except edge_tts.exceptions.NoAudioReceived:
            if attempt == TTS_RETRIES:
                raise
        await asyncio.sleep(min(attempt * 2, 30))
    raise RuntimeError(f"failed to synthesize sentence after {TTS_RETRIES} attempts")


def trim_speech(input_path: Path, output_path: Path) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(input_path),
            "-af",
            (
                "silenceremove=start_periods=1:start_duration=0.05:"
                "start_threshold=-45dB,areverse,"
                "silenceremove=start_periods=1:start_duration=0.05:"
                "start_threshold=-45dB,areverse"
            ),
            "-ar",
            "24000",
            "-ac",
            "1",
            "-c:a",
            "libmp3lame",
            "-b:a",
            "48k",
            str(output_path),
        ],
        check=True,
    )


def assemble_audio(speech_path: Path, output_path: Path, temporary_path: Path) -> None:
    pause_path = temporary_path / "pause.mp3"
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
            str(PAUSE_SECONDS),
            "-c:a",
            "libmp3lame",
            "-b:a",
            "48k",
            str(pause_path),
        ],
        check=True,
    )
    concat_path = temporary_path / "audio-segments.txt"
    concat_path.write_text(
        "".join(
            f"file '{path}'\n"
            for path in (pause_path, speech_path, pause_path, speech_path)
        ),
        encoding="utf-8",
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


def render_segment(
    number: int,
    sentence: str,
    sentence_count: int,
    audio_path: Path,
    output_path: Path,
    temporary_path: Path,
) -> None:
    duration = probe_duration(audio_path)
    wrapped_sentence, font_size, text_y = sentence_layout(sentence)
    sentence_path = temporary_path / "sentence.txt"
    sentence_path.write_text(wrapped_sentence, encoding="utf-8")
    progress_width = round(1570 * number / sentence_count)
    filters = [
        "drawbox=x=0:y=0:w=1920:h=18:color=#c64b3c:t=fill",
        "drawbox=x=128:y=118:w=8:h=832:color=#16756f:t=fill",
        (
            f"drawtext=fontfile='{ffmpeg_text_path(BODY_FONT)}':"
            f"text='SENTENCE {number:03d}':x=180:y=112:fontsize=30:fontcolor=#16756f"
        ),
        (
            f"drawtext=fontfile='{ffmpeg_text_path(BODY_FONT)}':"
            f"text='{number} / {sentence_count}':x=w-tw-180:y=116:"
            "fontsize=26:fontcolor=#68716d"
        ),
        (
            f"drawtext=fontfile='{ffmpeg_text_path(TITLE_FONT)}':"
            f"textfile='{ffmpeg_text_path(sentence_path)}':x=220:"
            f"y={text_y}:fontsize={font_size}:fontcolor=#18211f:"
            "line_spacing=16:expansion=none"
        ),
        "drawbox=x=180:y=948:w=1570:h=4:color=#d6d9d5:t=fill",
        f"drawbox=x=180:y=948:w={progress_width}:h=4:color=#c64b3c:t=fill",
        (
            f"drawtext=fontfile='{ffmpeg_text_path(BODY_FONT)}':"
            "text='GUY NEURAL  ·  TWO READINGS':x=180:y=980:"
            "fontsize=22:fontcolor=#68716d"
        ),
    ]
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
            f"color=c=#f5f3ed:s={FRAME_SIZE}:r={FRAME_RATE}:d={duration:.3f}",
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


def generate_video(sentences: list[tuple[int, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path = output_path.parent / ".sentence-video-cache"
    cache_path.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="sentence-video-") as directory:
        temporary_path = Path(directory)
        segment_paths: list[Path] = []
        for index, (number, sentence) in enumerate(sentences, start=1):
            segment_path = cache_path / f"sentence-{number:03d}.mp4"
            if segment_path.exists() and segment_path.stat().st_size > 0:
                segment_paths.append(segment_path)
                print(f"Reused sentence {number}/{len(sentences)}", flush=True)
                continue

            sentence_temporary_path = temporary_path / f"sentence-{number:03d}"
            sentence_temporary_path.mkdir()
            raw_speech_path = sentence_temporary_path / "raw-speech.mp3"
            speech_path = sentence_temporary_path / "speech.mp3"
            audio_path = sentence_temporary_path / "audio.mp3"
            asyncio.run(synthesize(sentence, raw_speech_path))
            trim_speech(raw_speech_path, speech_path)
            assemble_audio(speech_path, audio_path, sentence_temporary_path)
            render_segment(
                number,
                sentence,
                len(sentences),
                audio_path,
                segment_path,
                sentence_temporary_path,
            )
            segment_paths.append(segment_path)
            print(f"Rendered sentence {index}/{len(sentences)}", flush=True)

        concat_path = temporary_path / "segments.txt"
        concat_path.write_text(
            "".join(f"file '{path}'\n" for path in segment_paths), encoding="utf-8"
        )
        temporary_output = output_path.with_suffix(".tmp.mp4")
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
                "-movflags",
                "+faststart",
                str(temporary_output),
            ],
            check=True,
        )
        temporary_output.replace(output_path)
    shutil.rmtree(cache_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a narrated sentence video.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, help="render only the first N sentences")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        parser.error("ffmpeg and ffprobe are required")
    if not BODY_FONT.exists() or not TITLE_FONT.exists():
        parser.error("required macOS fonts are unavailable")
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be at least 1")

    sentences = parse_sentences(SOURCE.read_text(encoding="utf-8"))
    if args.limit is not None:
        sentences = sentences[: args.limit]
    output_path = args.output.expanduser()
    if output_path.exists() and output_path.stat().st_size > 0 and not args.overwrite:
        print(f"Skipped existing {output_path}")
        return

    generate_video(sentences, output_path)
    print(f"Generated {output_path}")


if __name__ == "__main__":
    main()