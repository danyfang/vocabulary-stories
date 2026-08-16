import re
with open('/Users/xuqiangfang/Documents/vocabulary/recite-zh.md', 'r', encoding='utf-8') as f:
    content = f.read()
headings = re.findall(r^(Story \d)$', content, re.MULTILINE)
nums = [int(x) for x in headings]
errors = []
if len(nums) != 180:
    errors.append(f"Expected 180 headings, found {len(nums)}")
for idx, val in enumerate(nums):
    expected_val = idx + 1
    if val != expected_val:
        errors.append(f"Sequence mismatch: expected Story {expected_val}, found Story {val}")
        break
matches = list(re.finditer(r'^Story (\d)$', content, re.MULTILINE))
for idx, match in enumerate(matches):
    story_lbl = match.group(1)
    start_pos = match.end()
    end_pos = matches[idx + 1].start() if idx + 1 < len(matches) else len(content)
    lines = [line.strip() for line in content[start_pos:end_pos].split('\n') if line.strip()]
    if len(lines) < 2:
        errors.append(f"Story story_lbl has fewer than 2 non-empty lines")
    else:
        title = lines[0]
        narrative = " ".join(lines[1:])
        if not title:
            errors.append(f"Story {story_lbl} has empty title")
        if not narrative:
            errors.append(f"Story {story_lbl} has empty narrative")
if errors:
    print("FAIL")
    for err in errors[:10]:
        print("-", err)
else:
    print("PASS")