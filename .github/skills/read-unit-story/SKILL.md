---
name: read-unit-story
description: 'Read vocabulary unit short stories aloud with macOS say. Use when the user asks to read, speak, or play one or more unit stories from wordlist.txt.'
argument-hint: 'Unit number(s), for example: 12 13'
---

# Read Unit Story

Read one or more vocabulary-unit stories aloud from `wordlist.txt`.

## Procedure

1. Parse the requested unit numbers or inclusive range.
2. Run the bundled script with each unit number as a separate argument:

   ```bash
   .github/skills/read-unit-story/scripts/read-unit-story.sh 12 13
   ```

3. For a range, expand it before invoking the script:

   ```bash
   .github/skills/read-unit-story/scripts/read-unit-story.sh $(seq 12 19)
   ```

4. Report which unit stories were read aloud.

The script reads only each story's title and prose. It excludes unit headings,
vocabulary entries, Chinese translations, and separator lines. It joins wrapped
prose lines with spaces before invoking `say`, preventing artificial pauses. It
inserts a one-second pause after each title so the passage begins distinctly.
During continuous reading, it pauses for two seconds between unit stories.

## Validation

- Confirm every requested unit exists.
- Confirm every requested unit has a title and story.
- Confirm a one-second speech pause follows each title.
- Confirm a two-second speech pause separates consecutive unit stories.
- Do not edit `wordlist.txt` while reading it.
- If `say` is unavailable, report that macOS text-to-speech is required.