import json

with open("scripts/glyphs.json", "r", encoding="utf-8") as f:
    raw = json.load(f)

def get_outline_str(snippet):
    start = snippet.find('o:"') + 3
    end = snippet.find('"', start)
    return snippet[start:end]

g_str = get_outline_str(raw["v83"])
f_str = get_outline_str(raw["v79"])

print("g_str length:", len(g_str))
print("f_str length:", len(f_str))

with open("scripts/clef_tokens_code.py", "w", encoding="utf-8") as out:
    out.write(f'_G_CLEF_PATH = """{g_str}"""\n\n')
    out.write(f'_F_CLEF_PATH = """{f_str}"""\n\n')

print("Saved clef_tokens_code.py")
