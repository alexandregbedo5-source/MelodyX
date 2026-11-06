with open("app/static/js/opensheetmusicdisplay.min.js", "r", encoding="utf-8") as f:
    js = f.read()

target = "s.graphicalVoiceEntries[0].parentVoiceEntry"
replacement = "(s.graphicalVoiceEntries[0]&&s.graphicalVoiceEntries[0].parentVoiceEntry)"
count = js.count(target)
if count > 0:
    js_patched = js.replace(target, replacement)
    with open("app/static/js/opensheetmusicdisplay.min.js", "w", encoding="utf-8") as f:
        f.write(js_patched)
    print(f"Successfully patched {count} occurrences in app/static/js/opensheetmusicdisplay.min.js")
else:
    print("Target already patched or not found")
