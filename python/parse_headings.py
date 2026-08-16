import re

with open("book.md", "r", encoding="utf-8") as f:
    lines = f.readlines()

headings = []
malformed = []
empty_bodies = []

current_heading = None
current_body_lines = []

for idx, line in enumerate(lines, 1):
    # Check for malformed or valid headings
    if line.startswith("## "):
        match = re.match(r"^## ([0-9]+)\. (.+)$", line.strip())
        if match:
            if current_heading:
                # check if body is empty
                body_content = "".join(current_body_lines).strip()
                if not body_content:
                    empty_bodies.append((current_heading[0], current_heading[1]))
            num = int(match.group(1))
            title = match.group(2)
            headings.append((num, title, idx))
            current_heading = (num, title, idx)
            current_body_lines = []
        else:
            malformed.append((idx, line.strip()))
    else:
        if current_heading:
            current_body_lines.append(line)

#################################eading:
    b    b    b    b    b    b    b    b    b    rip()
    if not body_content:
        empty_bo        emptycu        empng[0], c        empty_bo     pr        empty_bo   s foun        empty_bo        emptycu    )}"        empty_bo        emptycu        e}")
        empty_bo        empt_bo        empty_bo        empt_bo        empty_bo        empt_bo[0] for h in heading        empty_bo        empt []
        empty_bo        empt_bo                  empty_bo        empt_bo                  empty_bo      ge(1, 201) if n not in seen]
extra = [n fextra = [n fextra = [n fextra = [n fextra = [n fextra = [n fextra = [n fextra = ssextra = [n fextra = [n fextra = ut of range: {extra}")

