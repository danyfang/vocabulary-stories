#!/usr/bin/env python3

import argparse
import asyncio
import math
import shutil
import subprocess
import tempfile
from pathlib import Path

import edge_tts

from generate_recite_reader import parse_stories


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "recite.md"
OUTPUT_DIRECTORY = ROOT / "stories"
VOICE = "en-US-GuyNeural"
STORIES_PER_BATCH = 5


async def synthesize_story(story: dict[str, str | int], output_path: Path) -> None:
    text = f"Story {story['number']}. {story['title']}. {story['story']}"
    await edge_tts.Communicate(text, VOICE).save(str(output_path))


def combine_stories(clip_paths: list[Path], output_path: Path, workdir: Path) -> None:
    leading_silence = workdir / "leading-silence.wav"
    separator_silence = workdir / "separator-silence.wav"
    for path, duration in ((leading_silence, 2), (separator_silence, 3)):
        subprocess.run(
            [
                "ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                "anullsrc=r=24000:cl=mono", "-t", str(duration), str(path),
            ],
            check=True,
        )

    inputs = [leading_silence]
    for index, clip_path in enumerate(clip_paths):
        inputs.append(clip_path)
        if index < len(clip_paths) - 1:
            inputs.append(separator_silence)

    command = ["ffmpeg", "-loglevel", "error", "-y"]
    for path in inputs:
        command.extend(["-i", str(path)])
    normalized = ";".join(
        f"[{index}:a]aresample=24000,aformat=sample_fmts=fltp:channel_layouts=mono[a{index}]"
        for index in range(len(inputs))
    )
    streams = "".join(f"[a{index}]" for index in range(len(inputs)))
    command.extend(
        [
            "-filter_complex", f"{normalized};{streams}concat=n={len(inputs)}:v=0:a=1[out]",
            "-map", "[out]", "-codec:a", "libmp3lame", "-q:a", "2", str(output_path),
        ]
    )
    subprocess.run(command, check=True)


async def generate_batch(
    stories: list[dict[str, str | int]], batch: int, force: bool
) -> None:
    output_path = OUTPUT_DIRECTORY / f"story-unit-{batch:03d}.mp3"
    if output_path.exists() and not force:
        print(f"Skipping existing {output_path.name}", flush=True)
        return

    start = (batch - 1) * STORIES_PER_BATCH
    batch_stories = stories[start : start + STORIES_PER_BATCH]
    with tempfile.TemporaryDirectory() as temporary_directory:
        workdir = Path(temporary_directory)
        clip_paths = [workdir / f"story-{story['number']}.mp3" for story in batch_stories]
        await asyncio.gather(
            *(synthesize_story(story, path) for story, path in zip(batch_stories, clip_paths))
        )
        combine_stories(clip_paths, output_path, workdir)
    print(
        f"Generated {output_path.name}: Stories {batch_stories[0]['number']}-{batch_stories[-1]['number']}",
        flush=True,
    )


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-batch", type=int, default=1)
    parser.add_argument("--end-batch", type=int)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if not shutil.which("ffmpeg"):
        parser.error("ffmpeg is required")
    stories = parse_stories(SOURCE.read_text(encoding="utf-8"))
    batch_count = math.ceil(len(stories) / STORIES_PER_BATCH)
    end_batch = args.end_batch or batch_count
    if not 1 <= args.start_batch <= end_batch <= batch_count:
        parser.error(f"batch range must be between 1 and {batch_count}")

    OUTPUT_DIRECTORY.mkdir(exist_ok=True)
    for batch in range(args.start_batch, end_batch + 1):
        await generate_batch(stories, batch, args.force)


if __name__ == "__main__":
    asyncio.run(main())