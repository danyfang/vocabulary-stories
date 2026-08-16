import subprocess
import re

images = [
    "book/IMG20260814202143.jpg",
    "book/IMG20260814202146.jpg",
    "book/IMG20260814202152.jpg",
    "book/IMG20260814202156.jpg",
    "book/IMG20260814202159.jpg",
    "book/IMG20260814202205.jpg",
    "book/IMG20260814202208.jpg",
    "book/IMG20260814202214.jpg"
]

for img in images:
    print(f"=== {img} ===")
    res = subprocess.run(["tesseract", img, "stdout", "--psm", "3"], capture_output=True, text=True)
    text = res.stdout
    print(text)
    print("\n" + "="*40 + "\n")
