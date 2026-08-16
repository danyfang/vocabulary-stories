#!/usr/bin/env python3

import html
import json
import math
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "recite.md"
OUTPUT = ROOT / "recite-reader.html"
AUDIO_DIRECTORY = ROOT / "stories"
STORIES_PER_BATCH = 5


def parse_stories(source: str) -> list[dict[str, str | int]]:
    pattern = re.compile(
        r"^Story (?P<number>\d+)\n\n"
        r"(?P<vocabulary>.*?)\n\n"
        r"(?P<title>.*?)\n"
        r"(?P<story>.*?)(?=\n\nStory \d+\n|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    stories = []
    for match in pattern.finditer(source.strip()):
        stories.append(
            {
                "number": int(match["number"]),
                "title": match["title"].strip(),
                "story": " ".join(match["story"].split()),
            }
        )
    return stories


def build_audio_segments(story_count: int) -> dict[int, dict[str, float | str]]:
    segments = {}
    for batch in range(1, math.ceil(story_count / STORIES_PER_BATCH) + 1):
        path = AUDIO_DIRECTORY / f"story-unit-{batch:03d}.mp3"
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
            check=True,
            capture_output=True,
            text=True,
        )
        duration = float(probe.stdout.strip())
        detection = subprocess.run(
            ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "silencedetect=noise=-45dB:d=1.5", "-f", "null", "-"],
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
        separators = [
          (start, end)
          for start, end in silences[1:]
          if end - start >= 2.8
        ]
        starts = [silences[0][1], *(end for _, end in separators)]
        ends = [start for start, _ in separators]
        count = min(STORIES_PER_BATCH, story_count - (batch - 1) * STORIES_PER_BATCH)
        if len(starts) < count:
            raise SystemExit(f"Could not find all story boundaries in {path.name}")
        for offset in range(count):
            number = (batch - 1) * STORIES_PER_BATCH + offset + 1
            segments[number] = {
                "src": f"stories/{path.name}",
                "start": round(starts[offset], 3),
                "end": round(ends[offset] if offset < len(ends) else duration, 3),
            }
    return segments


def render(stories: list[dict[str, str | int]], audio_segments: dict) -> str:
    story_data = json.dumps(stories, ensure_ascii=False).replace("</", "<\\/")
    audio_data = json.dumps(audio_segments, ensure_ascii=False).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Recite Story Reader</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #18211f;
      --muted: #66706d;
      --paper: #f5f2e9;
      --surface: #fffef9;
      --line: #d8d4c8;
      --accent: #b83b2d;
      --accent-dark: #8d2c22;
      --focus: #126e82;
    }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{
      margin: 0;
      color: var(--ink);
      background:
        linear-gradient(rgba(24, 33, 31, .035) 1px, transparent 1px),
        var(--paper);
      background-size: 100% 28px;
      font-family: "Avenir Next", "Trebuchet MS", sans-serif;
    }}
    button, input, select {{ font: inherit; letter-spacing: 0; }}
    .toolbar {{
      position: sticky;
      top: 0;
      z-index: 10;
      display: grid;
      grid-template-columns: minmax(190px, 1fr) minmax(220px, 2fr) auto auto;
      gap: 12px;
      align-items: center;
      padding: 12px max(18px, calc((100vw - 1080px) / 2));
      border-bottom: 1px solid var(--line);
      background: rgba(245, 242, 233, .96);
      backdrop-filter: blur(10px);
    }}
    .brand {{ font-family: Georgia, serif; font-size: 21px; font-weight: 700; }}
    .search, .voice {{
      width: 100%;
      min-height: 40px;
      border: 1px solid #aaa69c;
      border-radius: 4px;
      background: var(--surface);
      color: var(--ink);
      padding: 8px 10px;
    }}
    .icon-button {{
      width: 40px;
      height: 40px;
      border: 1px solid #aaa69c;
      border-radius: 4px;
      background: var(--surface);
      color: var(--ink);
      cursor: pointer;
      font-size: 20px;
    }}
    .icon-button:hover {{ border-color: var(--accent); color: var(--accent); }}
    .icon-button:focus-visible, .play:focus-visible, input:focus-visible, select:focus-visible {{
      outline: 3px solid color-mix(in srgb, var(--focus) 35%, transparent);
      outline-offset: 2px;
    }}
    main {{ width: min(100% - 32px, 960px); margin: 30px auto 80px; }}
    .status {{ margin: 0 0 20px; color: var(--muted); font-size: 14px; }}
    .story {{
      display: grid;
      grid-template-columns: 76px minmax(0, 1fr);
      gap: 18px;
      padding: 24px 0;
      border-bottom: 1px solid var(--line);
    }}
    .number {{
      padding-top: 4px;
      color: var(--accent);
      font-family: Georgia, serif;
      font-size: 15px;
      font-weight: 700;
      text-align: right;
    }}
    .story-head {{ display: flex; align-items: flex-start; gap: 12px; }}
    h2 {{
      flex: 1;
      margin: 0;
      font-family: Georgia, serif;
      font-size: clamp(20px, 3vw, 27px);
      line-height: 1.2;
      letter-spacing: 0;
    }}
    .story p {{ margin: 13px 0 0; font-family: Georgia, serif; font-size: 18px; line-height: 1.7; }}
    .play {{
      flex: 0 0 auto;
      width: 42px;
      height: 42px;
      border: 0;
      border-radius: 50%;
      color: white;
      background: var(--accent);
      cursor: pointer;
      font-size: 18px;
    }}
    .play:hover {{ background: var(--accent-dark); }}
    .play[aria-pressed="true"] {{ background: var(--focus); }}
    .empty {{ padding: 80px 0; text-align: center; color: var(--muted); }}
    @media (max-width: 760px) {{
      .toolbar {{ grid-template-columns: 1fr auto auto; }}
      .brand {{ grid-column: 1 / -1; }}
      .voice {{ display: none; }}
      .story {{ grid-template-columns: 1fr; gap: 8px; }}
      .number {{ text-align: left; }}
      .story p {{ font-size: 17px; }}
    }}
  </style>
</head>
<body>
  <header class="toolbar">
    <div class="brand">Recite Reader</div>
    <input id="search" class="search" type="search" placeholder="Search story number, title, or text" aria-label="Search stories">
    <div class="voice" title="Same voice as the story-unit MP3 files">Voice: Guy Neural</div>
    <button id="pause" class="icon-button" type="button" title="Pause or resume" aria-label="Pause or resume">Ⅱ</button>
    <button id="stop" class="icon-button" type="button" title="Stop reading" aria-label="Stop reading">■</button>
  </header>
  <main>
    <p id="status" class="status"></p>
    <section id="stories" aria-live="polite"></section>
  </main>
  <script id="story-data" type="application/json">{story_data}</script>
  <script id="audio-data" type="application/json">{audio_data}</script>
  <script>
    const stories = JSON.parse(document.getElementById('story-data').textContent);
    const audioSegments = JSON.parse(document.getElementById('audio-data').textContent);
    const list = document.getElementById('stories');
    const status = document.getElementById('status');
    const search = document.getElementById('search');
    const pauseButton = document.getElementById('pause');
    const stopButton = document.getElementById('stop');
    const audio = new Audio();
    let activeButton = null;
    let activeSegment = null;
    let monitor = null;

    function escapeHtml(value) {{
      return value.replace(/[&<>\"']/g, character => ({{
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
      }})[character]);
    }}

    function render(query = '') {{
      const needle = query.trim().toLowerCase();
      const filtered = stories.filter(item => !needle ||
        String(item.number).includes(needle) ||
        item.title.toLowerCase().includes(needle) ||
        item.story.toLowerCase().includes(needle));
      status.textContent = `${{filtered.length.toLocaleString()}} of ${{stories.length.toLocaleString()}} stories`;
      list.innerHTML = filtered.length ? filtered.map(item => `
        <article class="story" id="story-${{item.number}}">
          <div class="number">Story ${{item.number}}</div>
          <div>
            <div class="story-head">
              <h2>${{escapeHtml(item.title)}}</h2>
              <button class="play" type="button" data-story="${{item.number}}" aria-label="Read Story ${{item.number}}: ${{escapeHtml(item.title)}}" aria-pressed="false" title="Read story">▶</button>
            </div>
            <p>${{escapeHtml(item.story)}}</p>
          </div>
        </article>`).join('') : '<p class="empty">No stories match your search.</p>';
    }}

    function resetActiveButton() {{
      if (activeButton) {{
        activeButton.textContent = '▶';
        activeButton.setAttribute('aria-pressed', 'false');
      }}
      activeButton = null;
      activeSegment = null;
      if (monitor) cancelAnimationFrame(monitor);
      monitor = null;
      pauseButton.textContent = 'Ⅱ';
    }}

    function stopReading() {{
      audio.pause();
      resetActiveButton();
    }}

    async function readStory(number, button) {{
      const segment = audioSegments[number];
      if (!segment) return;
      stopReading();
      if (!audio.src.endsWith(segment.src)) {{
        audio.src = segment.src;
        await new Promise((resolve, reject) => {{
          audio.addEventListener('loadedmetadata', resolve, {{ once: true }});
          audio.addEventListener('error', reject, {{ once: true }});
        }});
      }}
      audio.currentTime = segment.start;
      activeSegment = segment;
      activeButton = button;
      button.textContent = '■';
      button.setAttribute('aria-pressed', 'true');
      await audio.play();
      const watch = () => {{
        if (!activeSegment) return;
        if (audio.currentTime >= activeSegment.end || audio.ended) {{
          stopReading();
          return;
        }}
        monitor = requestAnimationFrame(watch);
      }};
      monitor = requestAnimationFrame(watch);
    }}

    list.addEventListener('click', event => {{
      const button = event.target.closest('.play');
      if (!button) return;
      if (button === activeButton) {{
        stopReading();
      }} else {{
        readStory(Number(button.dataset.story), button);
      }}
    }});
    search.addEventListener('input', () => {{ stopReading(); render(search.value); }});
    stopButton.addEventListener('click', stopReading);
    pauseButton.addEventListener('click', () => {{
      if (!activeSegment) return;
      if (audio.paused) {{
        audio.play();
        pauseButton.textContent = 'Ⅱ';
      }} else {{
        audio.pause();
        pauseButton.textContent = '▶';
      }}
    }});
    window.addEventListener('beforeunload', stopReading);
    render();
  </script>
</body>
</html>
"""


def main() -> None:
    stories = parse_stories(SOURCE.read_text(encoding="utf-8"))
    expected = list(range(1, 1318))
    actual = [story["number"] for story in stories]
    if actual != expected:
        raise SystemExit(f"Expected Stories 1-1317, got {len(stories)} entries")
    segments = build_audio_segments(len(stories))
    if sorted(segments) != expected:
      raise SystemExit(f"Expected audio for Stories 1-1317, got {len(segments)}")
    OUTPUT.write_text(render(stories, segments), encoding="utf-8")
    print(f"Generated {OUTPUT.name} with {len(stories)} stories")


if __name__ == "__main__":
    main()