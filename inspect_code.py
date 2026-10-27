import re

code = open('piece-detail.js', encoding='utf-8').read()
# Find all occurrences of fileFolder
matches = [m.start() for m in re.finditer(r'fileFolder', code)]
for idx in matches:
    print("--- MATCH ---")
    start = max(0, idx - 100)
    end = min(len(code), idx + 200)
    print(code[start:end])

