---
name: complete-vocabulary-unit
description: 'Correct misspellings, add concise Chinese translations, and write a titled story using every listed word in vocabulary units. Use when completing, translating, correcting, or writing a story for units in wordlist.md.'
argument-hint: 'Unit number(s), for example: 12 13'
user-invocable: true
---

# Complete Vocabulary Unit

Complete one or more bare vocabulary units in `wordlist.md` by correcting
misspellings, translating the words into Chinese, and writing a titled short
story for each unit.

## Procedure

1. Read each requested unit through the next `Unit N` heading or end of file,
   plus one nearby completed unit. Use the current file, not prior excerpts.
2. Check every listed English word or phrase for spelling before translating
   it. Correct clear misspellings in the vocabulary entries first. Verify an
   unfamiliar form before changing it so that rare, archaic, regional,
   technical, and deliberately nonstandard terms are preserved. If the
   intended correction is genuinely ambiguous, ask the user rather than
   guessing.
3. Use each corrected spelling consistently in its Chinese translation entry
   and throughout the story. Do not retain a misspelling as a plot device.
4. Begin each unit directly with its heading in this format:

   ```text
   Unit N
   ```

5. Add concise, idiomatic Chinese meanings in this format:

   ```text
   word — 常见释义；另一常见释义
   ```

6. After the vocabulary entries, add a specific title on its own line, then an
   original short story on the next line. Keep the entire story on exactly one
   physical line, regardless of its length.
7. Use every corrected word or phrase naturally in the story. Prefer the exact
   listed form; inflect it only when normal grammar requires it.
8. Make the story coherent and interesting rather than a sequence of example
   sentences. Keep it compact and do not explain the vocabulary in the story.
9. Vary settings and plots by checking nearby completed stories. Avoid ledgers,
   audits, missing payments, financial fraud, and accounting investigations
   unless a listed word specifically requires that context.
10. Preserve the compact file layout: unit heading, each vocabulary entry,
   title, and story must each occupy one line, with no blank lines or dashed
   separator lines anywhere.
11. Edit only the requested units. Preserve unrelated text and user changes.

## Validation

After editing, perform focused checks for every requested unit:

- It begins directly with a `Unit N` heading and has no dashed separator line.
- Clear misspellings were corrected before translation and story composition.
- Corrected spellings match across vocabulary entries and story occurrences.
- Every vocabulary entry has a Chinese translation after ` — `.
- Every listed English word or phrase occurs in its story, case-insensitively.
- The heading, each vocabulary entry, title, and story each occupy exactly one
   physical line, and no blank lines exist.
- The unit has exactly one non-generic title and one coherent story.
- Its setting and plot do not repeat nearby stories unnecessarily.
- No vocabulary from adjacent units was accidentally included.

Run file diagnostics after the content checks. Report whether vocabulary
coverage, compact formatting, and diagnostics passed.
