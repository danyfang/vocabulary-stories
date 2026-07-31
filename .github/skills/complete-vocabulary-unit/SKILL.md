---
name: complete-vocabulary-unit
description: 'Add concise Chinese translations and a titled story using every listed word in vocabulary units. Use when completing, translating, or writing a story for units in wordlist1.txt.'
argument-hint: 'Unit number(s), for example: 12 13'
user-invocable: true
---

# Complete Vocabulary Unit

Complete one or more bare vocabulary units in `wordlist1.txt` by translating
their words into Chinese and writing a titled short story for each unit.

## Procedure

1. Read each requested unit through the next `Unit N` heading or end of file,
   plus one nearby completed unit. Use the current file, not prior excerpts.
2. Preserve every listed English word or phrase exactly unless the user asks
   for a spelling correction.
3. Ensure each unit begins with this exact 72-character separator immediately
   before its heading:

   ```text
   ------------------------------------------------------------------------
   Unit N
   ```

4. Add concise, idiomatic Chinese meanings in this format:

   ```text
   word — 常见释义；另一常见释义
   ```

5. After the vocabulary entries, add a specific title and an original short
   story. Keep the unit compact: do not insert blank lines anywhere.
6. Use every listed word or phrase naturally in the story. Prefer the exact
   listed form; inflect it only when normal grammar requires it.
7. Make the story coherent and interesting rather than a sequence of example
   sentences. Keep it compact and do not explain the vocabulary in the story.
8. Wrap prose lines at no more than 72 characters.
9. Edit only the requested units and any missing separator immediately before
   them. Preserve unrelated text and user changes.

## Validation

After editing, perform focused checks for every requested unit:

- Its heading is immediately preceded by exactly 72 dashes.
- Every vocabulary entry has a Chinese translation after ` — `.
- Every listed English word or phrase occurs in its story, case-insensitively.
- No line exceeds 72 characters and no blank lines exist.
- The unit has exactly one non-generic title and one coherent story.
- No vocabulary from adjacent units was accidentally included.

Run file diagnostics after the content checks. Report whether vocabulary
coverage, separators, compact formatting, and diagnostics passed.
